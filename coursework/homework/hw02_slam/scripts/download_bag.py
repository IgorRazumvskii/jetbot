"""Fetch one course bag from the public ZIP using HTTP byte ranges."""

import argparse
from contextlib import contextmanager
import io
import json
from pathlib import Path, PurePosixPath
import struct
import sys
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zipfile import ZIP_DEFLATED, ZipFile
import zlib

API = "https://cloud-api.yandex.net/v1/disk/public/resources"
PUBLIC_URL = "https://disk.yandex.ru/d/Ze3yVF2UNOq6Aw"
LOCAL_HEADER = struct.Struct("<4s5H3I2H")
MIB = 1024 * 1024


def public_archive():
    query = urlencode({"public_key": PUBLIC_URL})
    with urlopen(f"{API}?{query}", timeout=25) as response:
        size = json.load(response)["size"]
    with urlopen(f"{API}/download?{query}", timeout=25) as response:
        url = json.load(response)["href"]
    return RemoteArchive(url, size)


class RemoteArchive(io.RawIOBase):
    def __init__(self, url, size):
        self.url = url
        self.size = size
        self.position = 0

    @contextmanager
    def byte_range(self, offset, length):
        last = offset + length - 1
        request = Request(self.url, headers={"Range": f"bytes={offset}-{last}"})
        with urlopen(request, timeout=40) as response:
            if (response.status != 206 or
                    response.headers.get("Content-Range") != f"bytes {offset}-{last}/{self.size}"):
                raise OSError("Yandex Disk did not return the requested byte range")
            yield response

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=io.SEEK_SET):
        self.position = (0, self.position, self.size)[whence] + offset
        return self.position

    def read(self, size=-1):
        available = self.size - self.position
        count = available if size < 0 else min(size, available)
        if count <= 0:
            return b""
        with self.byte_range(self.position, count) as response:
            data = response.read()
        if len(data) != count:
            raise OSError("Incomplete ZIP directory or header")
        self.position += count
        return data

    def payload_offset(self, member):
        self.seek(member.header_offset)
        header = LOCAL_HEADER.unpack(self.read(LOCAL_HEADER.size))
        if header[0] != b"PK\x03\x04" or member.compress_type != ZIP_DEFLATED:
            raise ValueError("Expected a deflated ZIP member")
        if member.flag_bits & 1:
            raise ValueError("Encrypted ZIP members are unsupported")
        name_size, extra_size = header[-2:]
        return member.header_offset + LOCAL_HEADER.size + name_size + extra_size


def progress(done, total, started, origin=0):
    speed = (done - origin) / max(time.monotonic() - started, 0.001)
    fraction = done / total
    filled = int(fraction * 28)
    bar = "=" * filled + " " * (28 - filled)
    eta = round((total - done) / speed)
    print(
        f"\r[{bar}] {fraction:6.1%}  {done / MIB:6.1f}/{total / MIB:.1f} MiB  "
        f"{speed / MIB:5.1f} MiB/s  ETA {eta:4d}s",
        end="", flush=True, file=sys.stderr,
    )


def download(archive, member, target):
    offset = archive.payload_offset(member)
    partial = target.with_suffix(".deflate.part")
    total = member.compress_size
    done = partial.stat().st_size if partial.exists() else 0
    if done > total:
        raise OSError(f"Invalid partial download size in {partial}")

    if done < total:
        origin = done
        started = time.monotonic()
        reported = started - 1
        try:
            with archive.byte_range(offset + done, total - done) as response, partial.open("ab") as output:
                while block := response.read(MIB):
                    output.write(block)
                    done += len(block)
                    now = time.monotonic()
                    if now - reported >= 0.15 or done == total:
                        progress(done, total, started, origin)
                        reported = now
        finally:
            print(file=sys.stderr)
    if done != total:
        raise OSError(f"Incomplete download. Run the command again to resume at byte {done}.")

    inflator = zlib.decompressobj(-zlib.MAX_WBITS)
    size = 0
    checksum = 0
    temporary = target.with_suffix(".db3.part")
    with partial.open("rb") as source, temporary.open("wb") as output:
        while block := source.read(MIB):
            data = inflator.decompress(block)
            output.write(data)
            size += len(data)
            checksum = zlib.crc32(data, checksum)
    if not inflator.eof or size != member.file_size or checksum != member.CRC:
        raise OSError(f"ZIP integrity check failed for {partial}")
    temporary.replace(target)
    partial.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--segment", type=int, default=0, help="zero-based segment index")
    parser.add_argument("--list", action="store_true", help="show segment names and sizes")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "bags")
    args = parser.parse_args()
    archive = public_archive()
    with ZipFile(archive) as directory:
        bags = sorted(
            (entry for entry in directory.infolist() if entry.filename.endswith(".db3")),
            key=lambda entry: entry.filename,
        )
        if args.list:
            for i, member in enumerate(bags):
                print(f"{i}  {PurePosixPath(member.filename).parent.name}  {member.compress_size / MIB:.1f} MiB")
            return
        if not 0 <= args.segment < len(bags):
            parser.error(f"--segment must be between 0 and {len(bags) - 1}")
        member = bags[args.segment]
        source = PurePosixPath(member.filename)
        metadata = directory.read(str(source.parent / "metadata.yaml"))
        output = args.output / source.parent.name
        output.mkdir(parents=True, exist_ok=True)
        target = output / source.name
        if not target.is_file():
            download(archive, member, target)
        elif target.stat().st_size != member.file_size:
            raise OSError(f"Existing bag has the wrong size: {target}")
        (output / "metadata.yaml").write_bytes(metadata)
        print(output)


if __name__ == "__main__":
    main()

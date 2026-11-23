#!/usr/bin/env bash
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
target=${JETBOT_SSH_TARGET:-jetbot@192.168.50.206}
if [[ -n ${JETBOT_CONTROL_PATH:-} ]]; then
    socket=$JETBOT_CONTROL_PATH
else
    session=$(mktemp -d "${TMPDIR:-/tmp}/jetbot-teleop.XXXXXX")
    socket=$session/ssh.sock
    trap '/usr/bin/ssh -S "$socket" -O exit "$target" 2>/dev/null || true; rmdir "$session" 2>/dev/null || true' EXIT
    /usr/bin/ssh -M -S "$socket" -o ControlPersist=1m -o ConnectTimeout=6 -fN "$target"
fi
python3 "$here/panel.py" --robot "$target" --control-path "$socket" "$@"

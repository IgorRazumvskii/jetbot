#!/bin/bash
# Подключает хостовые NVIDIA-библиотеки (OpenGL/EGL/Vulkan/CUDA) внутри контейнера.
#
# Зачем: Docker на хосте установлен через snap, а snap-демон не видит хостовый
# /usr (у него свой корень из core-снапа), поэтому штатный nvidia-container-toolkit
# (--gpus all / CDI) падает. Хостовая ФС доступна демону как /var/lib/snapd/hostfs,
# её lib-каталог монтируется в контейнер в $NVIDIA_HOST_LIBS, а этот скрипт
# делает симлинки на библиотеки текущей версии драйвера и обновляет ld-кэш.
set -euo pipefail

SRC="${NVIDIA_HOST_LIBS:-/host/lib}"
DST=/usr/lib/x86_64-linux-gnu

if [ ! -e /dev/nvidiactl ] || [ ! -d "$SRC" ]; then
    echo "[gpu] NVIDIA не проброшена — используется программный рендеринг (Mesa)"
    exit 0
fi

glcore=$(ls "$SRC"/libnvidia-glcore.so.* 2>/dev/null | head -n1 || true)
if [ -z "$glcore" ]; then
    echo "[gpu] в $SRC нет libnvidia-glcore.so.* — пропускаю настройку NVIDIA"
    exit 0
fi
VER="${glcore##*.so.}"

shopt -s nullglob
for f in "$SRC"/lib*nvidia*.so."$VER" \
         "$SRC"/libcuda.so."$VER" "$SRC"/libnvcuvid.so."$VER" "$SRC"/libnvoptix.so."$VER" \
         "$SRC"/libnvidia-egl-*.so.*; do
    ln -sf "$f" "$DST/$(basename "$f")"
done

# glvnd (EGL) и Vulkan-loader ищут вендорские библиотеки через json-описания
mkdir -p /usr/share/glvnd/egl_vendor.d /usr/share/vulkan/icd.d
cat > /usr/share/glvnd/egl_vendor.d/10_nvidia.json <<'EOF'
{
    "file_format_version" : "1.0.0",
    "ICD" : { "library_path" : "libEGL_nvidia.so.0" }
}
EOF
cat > /usr/share/vulkan/icd.d/nvidia_icd.json <<'EOF'
{
    "file_format_version" : "1.0.1",
    "ICD": { "library_path": "libGLX_nvidia.so.0", "api_version" : "1.3" }
}
EOF

# ldconfig создаст soname-симлинки (libGLX_nvidia.so.0 -> ...so.$VER и т.п.)
ldconfig
echo "[gpu] NVIDIA $VER подключена"

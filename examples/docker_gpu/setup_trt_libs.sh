#!/usr/bin/env bash
# setup_trt_libs.sh — bareun-trt 컨테이너에 마운트할 /trt_libs 디렉토리 준비
#
# WSL2 (Ubuntu) 환경에서 실행. 다음을 호스트의 ~/trt_libs_for_bareun/ 으로 복사한다:
#   - CUDA 12 / cuDNN 9 라이브러리 (NVIDIA pip wheel 또는 시스템 설치본)
#   - TensorRT 10 라이브러리 (apt install libnvinfer10)
#
# 사용:
#   bash setup_trt_libs.sh
#   # → docker run 시 -v /home/<user>/trt_libs_for_bareun:/trt_libs:ro 로 마운트

set -e
TLD="$HOME/trt_libs_for_bareun"
mkdir -p "$TLD"

# 1) CUDA 12 / cuDNN 9 — NVIDIA pip wheel 우선 (vllm/torch 등의 의존성)
PKG_CANDIDATES=(
    "$HOME/vllm-env/lib/python3.12/site-packages/nvidia"
    "$HOME/.venv/lib/python3.12/site-packages/nvidia"
    "$HOME/.venv/lib/python3.11/site-packages/nvidia"
)
for PKG in "${PKG_CANDIDATES[@]}"; do
    if [ -d "$PKG" ]; then
        echo "[setup] CUDA libs from: $PKG"
        for sub in cublas cuda_runtime cudnn cufft curand cusparse cusolver nvjitlink cuda_nvrtc cuda_cupti; do
            d="$PKG/$sub/lib"
            if [ -d "$d" ]; then
                for so in "$d"/*.so*; do
                    [ -e "$so" ] || continue
                    cp -L --preserve=mode,timestamps "$so" "$TLD/" 2>/dev/null || true
                done
            fi
        done
        break
    fi
done

# 2) TensorRT 10 — 시스템 apt 설치본
if [ -d "/usr/lib/x86_64-linux-gnu" ]; then
    echo "[setup] TensorRT libs from /usr/lib/x86_64-linux-gnu/"
    for so in /usr/lib/x86_64-linux-gnu/libnvinfer*.so.10* /usr/lib/x86_64-linux-gnu/libnvonnxparser*.so.10*; do
        [ -f "$so" ] || continue
        cp -L --preserve=mode,timestamps "$so" "$TLD/" 2>/dev/null || true
    done
fi

echo "[setup] === Total files in $TLD ==="
ls "$TLD" | wc -l
echo "[setup] === Required libs check ==="
for req in libcublasLt.so.12 libcublas.so.12 libcudart.so.12 libcudnn.so.9 libnvJitLink.so.12; do
    if ls "$TLD/$req"* >/dev/null 2>&1; then
        echo "  ✓ $req"
    else
        echo "  ✗ $req — 누락"
    fi
done
echo "[setup] done. Total size: $(du -sh "$TLD" | cut -f1)"

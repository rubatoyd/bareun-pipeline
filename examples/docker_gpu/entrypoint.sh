#!/usr/bin/env bash
# bareun-gpu 컨테이너 entrypoint
#
# 호스트에서 마운트된 /trt_libs 의 TensorRT/cuDNN/CUDA12 라이브러리에 대해
# 버전 부착 파일(.so.10.16.1 등)이 있으면 짧은 이름(.so.10) 심링크를 만든다.
# /trt_libs 가 RO 마운트인 경우 ln 실패는 무시한다 (이미 정확한 이름이면 OK).

TRT=/trt_libs

# TensorRT 10.x.y → libnvinfer.so.10 / libnvinfer_plugin.so.10 등의 짧은 이름 보장
for f in "$TRT"/libnvinfer.so.10.*.* "$TRT"/libnvinfer_plugin.so.10.*.*; do
    [ -f "$f" ] || continue
    short=$(basename "$f" | sed 's/\.[0-9]*\.[0-9]*$//')
    [ -e "$TRT/$short" ] || ln -s "$f" "$TRT/$short" 2>/dev/null || true
done
# CUDA 12 라이브러리 짧은 이름 (libcublasLt.so.12 등)
for prefix in libcublas libcublasLt libnvJitLink libcudart libcudnn; do
    for f in "$TRT"/$prefix.so.12.*; do
        [ -f "$f" ] || continue
        short=$(basename "$f" | sed 's/\.[0-9]*\.[0-9]*$//')
        [ -e "$TRT/$short" ] || ln -s "$f" "$TRT/$short" 2>/dev/null || true
    done
done

echo "[entrypoint] TRT libs in $TRT:"
ls "$TRT"/ 2>/dev/null | head -30

exec /bareun/bin/bareun "$@"

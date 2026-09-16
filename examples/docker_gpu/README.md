# Docker GPU 셋업 예제

bareun 서버를 GPU 가속 Docker 컨테이너로 운영하는 참고 예제입니다.

## 환경 요구

- Windows 10/11 + WSL2 (Ubuntu) + Docker Desktop, 또는 Linux + Docker
- NVIDIA GPU + 최신 드라이버
- NVIDIA Container Toolkit (`docker run --gpus all` 동작 필수)
- WSL2의 경우 `nvidia-smi`가 컨테이너 안에서도 동작하는지 확인:
  ```bash
  docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
  ```

## 파일 구성

| 파일 | 역할 |
|---|---|
| `Dockerfile.bareun-gpu` | bareun-trt:latest 빌드 (베이스 `bareunai/bareun-gpu:latest`) |
| `entrypoint.sh` | `/trt_libs/*.so.X.Y.Z` 짧은 이름 심링크 + `bareun` 실행 |
| `bareun-tensorrt.json` | TensorRT FP16 + LayerNorm FP32 폴백 설정 (권장) |
| `bareun-cpu.json` | CPU 전용 설정 (검증/디버깅용) |
| `setup_trt_libs.sh` | 호스트 `~/trt_libs_for_bareun/` 에 CUDA12/cuDNN9/TRT10 라이브러리 모음 |

## 1. 이미지 빌드

```bash
cd examples/docker_gpu
docker build -f Dockerfile.bareun-gpu -t bareun-trt:latest .
```

## 2. /trt_libs 준비 (WSL2 환경)

bareun-trt 베이스에 포함된 시스템 CUDA가 11.2이므로 onnxruntime 1.23.0이 요구하는 CUDA 12 / cuDNN 9 라이브러리를 호스트에서 마운트해야 합니다. TensorRT 10도 동일하게 호스트 마운트.

```bash
# WSL2 안에서 실행. NVIDIA pip wheel(vllm 등) + 시스템 TRT를 ~/trt_libs_for_bareun/ 으로 복사
bash setup_trt_libs.sh
```

다음 라이브러리가 모두 ✓ 표시되어야 합니다:

```
✓ libcublasLt.so.12
✓ libcublas.so.12
✓ libcudart.so.12
✓ libcudnn.so.9
✓ libnvJitLink.so.12
```

TensorRT가 시스템에 없다면 `sudo apt install libnvinfer10 libnvonnxparser10` 등으로 설치 후 재실행.

## 3. 컨테이너 실행

bareun 서버는 사용 시 최초 1회 [bareun.ai](https://bareun.ai)에서 발급받은 API 키로 제품 등록이 필요합니다 (브라우저 `http://localhost:5656/`).

```bash
docker run -d --name bareun \
    --gpus all \
    -p 5656:5656 \
    -v "$(pwd)/bareun-tensorrt.json:/bareun/config/bareun.json:ro" \
    -v "$HOME/trt_libs_for_bareun:/trt_libs:ro" \
    -e BAREUN_MODEL_MANIFEST_URL="https://storage.googleapis.com/bareun-deploy/serve/default/T260803-68E78F/manifest.json" \n    --restart unless-stopped \
    bareun-trt:latest
```

> **`BAREUN_MODEL_MANIFEST_URL` 은 TensorRT EP 사용 시 필수입니다.** 기본 모델(T260817 이후)은
> TensorRT 10.16.1 에서 임포트되지 않습니다. 아래 **7. 모델 호환성** 을 참조하세요.
> CPU EP 로만 쓸 경우 생략해도 됩니다.

PowerShell 등 Windows 호스트에서 실행하는 경우 `$HOME` 대신 `\\wsl$\Ubuntu\home\<user>\trt_libs_for_bareun` 경로를 사용하거나, WSL bash로 위 명령을 실행하세요.

## 4. 동작 확인

### 4-1. EP 활성화 로그

```bash
docker logs bareun | grep -E "execution provider|enabled"
# TensorRT execution provider enabled  ← 이 메시지가 보여야 GPU 가속 활성
```

### 4-2. 명사 추출 정확성 (sm_120 환경에서 특히 중요)

```python
from bareun_pipeline import BareunPipeline
pipeline = BareunPipeline.from_env()
sample = ["우리 민족에게 통일은 더 이상의 희망 사항이 아니라 목적에 닥친 구체적인 현실이다."]
print(pipeline.run(sample)[0].nouns)
```

기대값: `민족, 통일, 이상, 희망, 사항, 목적, 구체적, 현실` (또는 유사). 만약 `대비하ㄴ`, `에미`, `있조저` 등 비실재 한국어 음절이 섞여 나온다면 EP 호환성 문제이므로 `bareun-cpu.json`으로 우선 폴백하고 EP 설정을 재검토하세요.

## 5. 권장 EP 매트릭스

| GPU 아키텍처 | Compute Capability | 권장 EP |
|---|---|---|
| Pascal | sm_61 | `cuda` |
| Volta | sm_70 | `cuda` 또는 `tensorrt` |
| Turing | sm_75 | `cuda` 또는 `tensorrt` |
| Ampere (RTX 30, A100) | sm_80, sm_86 | `cuda` 또는 `tensorrt` |
| Ada Lovelace (RTX 40) | sm_89 | `cuda` 또는 `tensorrt` |
| **Hopper / Blackwell (H100, B200, RTX 50)** | **sm_90, sm_100, sm_120** | **`tensorrt`** |

Blackwell 환경에서는 `cuda` EP가 ONNX 시퀀스 라벨링 모델에서 부정확한 추론을 유발해 비실재 한국어 음절을 명사 추출 결과에 포함시키는 사례가 관찰됩니다. TensorRT EP 사용 시에는 sm 아키텍처별 builder resource(`libnvinfer_builder_resource_smXXX.so.10.x.y`)가 `/usr/lib/x86_64-linux-gnu/`에 설치되어 있어야 하며, `setup_trt_libs.sh`가 이를 자동 복사합니다.

## 6. 트러블슈팅

### `Failed to load library libonnxruntime_providers_cuda.so` / `libcublasLt.so.12: cannot open`

호스트에서 `setup_trt_libs.sh`를 다시 실행해 누락 라이브러리를 채우거나, NVIDIA 공식 wheel을 새로 설치 후 재실행:

```bash
pip install --user nvidia-cublas-cu12 nvidia-cudnn-cu12 nvidia-cuda-runtime-cu12 \
                  nvidia-cufft-cu12 nvidia-curand-cu12 nvidia-cusparse-cu12 \
                  nvidia-cusolver-cu12 nvidia-nvjitlink-cu12 --break-system-packages
bash setup_trt_libs.sh
```

### `cannot find license file /bareun/var/license.pem`

서버 시작 직후 잠깐 표시될 수 있으나, API 키만 등록되면 정상 동작합니다. 첫 실행 시 브라우저로 `http://localhost:5656/` 접속 → 발급받은 API 키 등록.

### `Assertion failed: ... kINT32` / `Non-zero zero point is not supported`

모델 호환성 문제입니다. **7. 모델 호환성** 을 참조해 `BAREUN_MODEL_MANIFEST_URL` 로
`T260803-68E78F` 를 고정하세요.

### CUDA EP 로 바꿨더니 결과가 깨짐 (Blackwell)

sm_120 에서 `cuda` EP 는 사용할 수 없습니다. 실측(300 발화)에서 **100% 불일치**했고
`삽읩`, `아닣라`, `합잇` 같은 비실재 음절이 출력됐습니다. 속도는 3.09배 빨라지지만
결과가 무의미합니다. TensorRT 가 막히면 CUDA 가 아니라 **CPU 로 폴백**하십시오.

### 첫 요청이 2분 넘게 걸림

TensorRT 엔진 빌드입니다(실측 125초). 입력 shape 별로 빌드되며 `trt_engine_cache_enable`
로 캐시됩니다. `/bareun/var` 를 named volume 으로 마운트하지 않으면 컨테이너를 새로 만들
때마다 재빌드합니다.

### Docker Desktop(Windows): 컨테이너가 `Created` 에서 멈춤

마운트 소스 파일이 없으면 Docker 가 **디렉토리로 자동 생성**합니다. 이후
`not a directory: Are you trying to mount a directory onto a file` 오류가 납니다.
해당 경로를 지우고 파일을 만든 뒤 다시 실행하세요.

### 컨테이너 내부 `/trt_libs` 가 비어 보임

PowerShell 등 Windows 호스트에서 docker 실행 시 WSL 경로(`/home/...`)는 `docker-desktop` 배포 기준으로 해석되어 비게 보입니다. WSL bash 내부에서 `docker run` 명령을 직접 실행하거나, `\\wsl$\Ubuntu\home\<user>\trt_libs_for_bareun` UNC 경로를 사용하세요.

## 7. 모델 호환성 — TensorRT EP 사용 시 반드시 확인

bareun 서버는 기동 시 모델 카탈로그에서 최신 모델을 내려받습니다.
**2026-08-17 발행 `T260817-F05693` 부터 WSD 가 독립 모델(`sense-model.onnx`, KoELECTRA)로
분리되었고, 이 모델은 비대칭 양자화를 써서 TensorRT 10.16.1 의 ONNX 파서가 임포트하지
못합니다.**

```
[6] Assertion failed: shiftIsAllZeros(zeroPoint): Non-zero zero point is not supported.
[8] Assertion failed: (output_tensor_ptr->getType() != nvinfer1::DataType::kINT32 || ...)
```

`seg-model.onnx` 와 `tag-model.onnx` 는 정상 로드되고 **`sense-model.onnx` 에서만 실패**하므로,
로그에 `TensorRT execution provider enabled` 가 보여도 서버는 요청마다 죽습니다
(클라이언트에는 `End of TCP stream` 으로 나타납니다).

### 검증된 조합 (2026-09-16, RTX 5060 Ti / sm_120 / TRT 10.16.1 / 서버 v3.1.0)

| 모델 | 구성 | TensorRT | 비고 |
|---|---|---|---|
| `T260803-68E78F` | `tag-sense-model.onnx` (병합) | 정상 | **권장** |
| `T260806-AFD6C8` | 미검증 | ? | |
| `T260815-BDEB57` | 미검증 | ? | |
| `T260817-F05693` | `sense-model.onnx` (독립·양자화) | 실패 | 서버 기본값 |
| `T260914-535CAD` | — | — | 서버 3.2.0 이상 필요 |

병합형 모델은 별도 WSD 모델이 없어 **동음이의어 판별 품질이 낮습니다.**
형태소·품사만 필요하면 문제가 없지만, WSD 가 필요하면 CPU EP 를 쓰십시오.

### 성능·정확도 실측 (300 발화, 한국어 커뮤니티 텍스트)

| 항목 | 값 |
|---|---|
| 첫 실행 (엔진 빌드) | 125.1s |
| **캐시 후** | **0.41s** (CPU 1.60s 대비 **3.86배**) |
| VRAM | 약 2.6GB |
| CPU EP 와의 형태소 열 불일치 | 4 / 301 (1.33%) |

불일치는 전부 경계 판단 차이(`기대하 아` / `기대 하 아`, `참교사` / `참 교사`)였고
비실재 음절은 관찰되지 않았습니다.

엔진 캐시는 `trtEngineCachePath`(기본 `${BAREUN_ROOT}/var/trt_cache`)에 쌓이므로
**`/bareun/var` 를 named volume 으로 마운트**해야 재기동 시 재빌드를 피할 수 있습니다.

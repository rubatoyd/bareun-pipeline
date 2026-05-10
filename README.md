# bareun-pipeline

[바른(bareun)](https://bareun.ai) 한국어 형태소 분석기를 위한 비동기 배치 파이프라인.

텍스트 리스트를 받아 **명사**와 **형태소 시퀀스**를 반환하며, 사용자 사전 등록도 지원합니다.

## 특징

- **비동기 배치 처리** — asyncio + ThreadPoolExecutor로 대용량(43K건+) 빠르게 처리
- **복합명사 자동 결합** — 연속 NNG/NNP, XPN/XSN 패턴 결합
- **사용자 사전 관리** — 도메인별 고유명사·복합명사 등록/조회/테스트
- **간단한 API** — `pipeline.run(texts)` 한 줄로 분석 완료
- **환경 변수 지원** — `.env` 파일로 API 키/서버 주소 관리

## 요구 사항

| 항목 | 조건 |
|------|------|
| Python | 3.11 이상 |
| bareun 서버 | WSL2 또는 로컬 설치, 기본 포트 5656 |
| httpx | 0.27 이상 (자동 설치) |

## 설치

```bash
pip install bareun-pipeline

# JSON 파싱 속도 향상 (선택)
pip install "bareun-pipeline[fast]"
```

또는 소스에서:

```bash
git clone https://github.com/rubato103/bareun-pipeline.git
cd bareun-pipeline
pip install -e .
```

## 빠른 시작

### 1. 환경 변수 설정

```bash
cp .env.example .env
# .env 파일에 BAREUN_API_KEY 입력
```

### 2. 기본 사용

```python
from bareun_pipeline import BareunPipeline

pipeline = BareunPipeline.from_env()  # .env 자동 로드

texts = [
    "청소년 정책 개발을 위한 연구가 진행됐다.",
    "학교폭력 예방 교육이 전국에서 실시됐다.",
]

results = pipeline.run(texts)

for r in results:
    print(r.noun_list)    # ["청소년", "정책", "개발", "연구"]
    print(r.nouns)        # "청소년, 정책, 개발, 연구"
    print(r.morphemes)    # "청소년/NNG+정책/NNG+개발/NNG|..."
```

### 3. API 키 직접 전달

```python
pipeline = BareunPipeline(
    host    = "http://localhost:5656",
    api_key = "koba-...",
    batch_size  = 50,   # 배치당 문장 수
    max_workers = 8,    # 동시 요청 수
)
```

### 4. 비동기 사용

```python
import asyncio
from bareun_pipeline import BareunPipeline

async def main():
    pipeline = BareunPipeline.from_env()
    results  = await pipeline.run_async(texts)
    return results

asyncio.run(main())
```

### 5. 사용자 사전

```python
from bareun_pipeline import DictManager

dm = DictManager(host="http://localhost:5656", api_key="koba-...")

# 사전 등록
dm.register(
    domain      = "my-domain",
    np_set      = ["청소년참여위원회", "학교폭력대책위원회"],
    cp_set      = ["학교폭력예방", "청소년상담복지"],
    cp_caret_set= ["학교^폭력"],   # 분리 지정
)

# 등록된 사전 목록
dm.list_domains()

# 단문 테스트
dm.test(domain="my-domain", text="청소년참여위원회에서 학교폭력예방 정책을 논의했다.")
```

### 6. 사전 적용 분석

```python
results = pipeline.run(texts, custom_dict_names=["my-domain"])
```

### 7. 토픽 모델용 옵션 (연속 결합 OFF + cp_set 사후 결합)

토픽 모델링 등 어휘 변별력이 중요한 용례에서는 연속 NNG/NNP 자동 결합을 끄고, 의미 보존이 필요한 복합명사는 도메인 사전(cp_set)에 명시 등록하는 정책을 권장합니다. bareun 서버의 cp_set은 입력 텍스트의 띄어쓰기 양상에 따라 부분적으로만 적용되므로, 클라이언트 측 사후 결합 옵션을 함께 사용하면 일관된 결합을 보장할 수 있습니다.

```python
CP = {"다문화교육", "다문화사회", "한국사회", "사회통합"}

results = pipeline.run(
    texts,
    custom_dict_names=["multicultural-edu"],
    combine_consecutive_nominals=False,   # 연속 NNG/NNP 자동 결합 OFF
    post_combine_pairs=CP,                 # 인접 명사 쌍이 cp에 있으면 결합
)
```

## 명사 추출 규칙

bareun 형태소 태그 기준 결합 우선순위:

| 패턴 | 예시 | 결과 | 비고 |
|------|------|------|------|
| XPN + NNG/NNP + XSN | 비+자살+적 | 비자살적 | 항상 적용 |
| XPN + NNG/NNP | 비+자살 | 비자살 | 항상 적용 |
| NNG/NNP + XSN | 사회+적 | 사회적 | 항상 적용 |
| 연속 NNG/NNP | 사회+공헌 | **사회공헌** | `combine_consecutive_nominals=True` (기본) |
| NNB/SL 단독 | 수, CNN | 수, CNN | 항상 적용 |

> 연속 NNG/NNP 자동 결합은 `combine_consecutive_nominals` 파라미터로 제어합니다. 토픽 모델 입력 등 어휘 변별력이 중요한 용례에서는 `False`를 권장하며, 의미 보존이 필요한 복합명사는 `post_combine_pairs`(클라이언트 후처리) 또는 bareun 서버의 cp_set(사용자 사전)에 명시 등록합니다.

## BatchResult API

```python
batch = pipeline.run(texts)

len(batch)              # 문서 수
batch.error_count       # API 오류 건수

batch[0].nouns          # "청소년, 정책"  (문자열)
batch[0].noun_list      # ["청소년", "정책"]  (리스트)
batch[0].morphemes      # 원시 형태소 시퀀스

batch.noun_strings()    # 전체 nouns 문자열 리스트
batch.noun_lists()      # 전체 noun_list(of list) 리스트
```

## CSV 배치 처리 예시

`examples/batch_csv.py` 참고:

```python
import pandas as pd
from bareun_pipeline import BareunPipeline

pipeline = BareunPipeline.from_env()
df       = pd.read_csv("articles.csv")
results  = pipeline.run(df["text"].tolist())

df["nouns"] = [r.nouns for r in results]
df.to_csv("results.csv", index=False, encoding="utf-8-sig")
```

## bareun 서버 설치 (WSL2)

공식 문서: https://bareun.ai/docs

```bash
# WSL2 내에서 설치
curl -fsSL https://bareun.ai/install.sh | bash
bareun start
```

서버 동작 확인:

```powershell
# Windows PowerShell
curl http://localhost:5656/start/
```

## GPU 가속 사용 시 주의사항

bareun 서버는 ONNX Runtime 1.23.0을 사용하며 다양한 Execution Provider(CUDA, TensorRT, DirectML 등)를 지원합니다. 본 패키지는 클라이언트일 뿐이지만, 서버 측 EP 선택은 분석 출력에 직결되므로 다음 사항을 유의해 주세요.

| GPU 환경 | 권장 EP | 비고 |
|---|---|---|
| Pascal/Volta/Turing/Ampere/Ada (sm_61~89) | `cuda` 또는 `tensorrt` | 일반적으로 안정 |
| **Blackwell (sm_100, sm_120)** | **`tensorrt` 권장** | `cuda` EP에서 비실재 한국어 음절이 명사 추출 결과에 섞이는 사례 확인 |

EP 변경 후에는 5~50문서 단위로 출력 검증을 권장합니다. 자모(ㄴ/ㅁ/ㅂ 등) 자체는 정상적인 형태소 출력(어미 ETM 등)일 수 있으나, **단어 중간에 자모가 박힌 형태(예: "대비하ㄴ", "에미", "있조저")가 명사 추출 결과에 보인다면 EP 호환성 문제**일 가능성이 높습니다.

```python
from bareun_pipeline import BareunPipeline
pipeline = BareunPipeline.from_env()
sample = ["우리 민족에게 통일은 더 이상의 희망 사항이 아니라 목적에 닥친 구체적인 현실이다."]
print(pipeline.run(sample)[0].nouns)  # 비실재 음절 포함 여부 확인
```

Docker 기반 GPU 셋업 예제는 `examples/docker_gpu/` 참고.

## 라이선스

MIT

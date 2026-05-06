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

## 명사 추출 규칙

bareun 형태소 태그 기준 결합 우선순위:

| 패턴 | 예시 | 결과 |
|------|------|------|
| XPN + NNG/NNP + XSN | 비+자살+적 | 비자살적 |
| XPN + NNG/NNP | 비+자살 | 비자살 |
| NNG/NNP + XSN | 사회+적 | 사회적 |
| 연속 NNG/NNP | 사회+공헌 | **사회공헌** |
| NNB/SL 단독 | 수, CNN | 수, CNN |

> 연속 NNG/NNP 자동 결합은 bareun 전용 동작입니다.

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

## 라이선스

MIT

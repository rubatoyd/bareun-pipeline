"""
basic_nouns.py — bareun-pipeline 기본 사용 예제

실행:
    python examples/basic_nouns.py
    python examples/basic_nouns.py --host http://localhost:5656
"""
import argparse
from bareun_pipeline import BareunPipeline


def main():
    parser = argparse.ArgumentParser(description="bareun 명사 추출 기본 예제")
    parser.add_argument("--host",    default=None, help="bareun 서버 주소")
    parser.add_argument("--api-key", default=None, dest="api_key", help="API 키")
    args = parser.parse_args()

    # API 키를 직접 전달하거나 .env 파일에서 자동 로드
    if args.host or args.api_key:
        pipeline = BareunPipeline(
            host    = args.host    or "http://localhost:5656",
            api_key = args.api_key or "",
        )
    else:
        pipeline = BareunPipeline.from_env()

    texts = [
        "청소년 정책 개발을 위한 연구가 전국적으로 진행됐다.",
        "학교폭력 예방 교육이 전국 초·중·고교에서 실시됐다.",
        "여성가족부는 청소년상담복지센터 운영 예산을 확대하기로 했다.",
    ]

    print("=" * 50)
    print("  bareun 명사 추출 예제")
    print("=" * 50)

    results = pipeline.run(texts)

    for i, (text, result) in enumerate(zip(texts, results), 1):
        print(f"\n[{i}] 원문: {text}")
        print(f"    명사: {result.noun_list}")

    print(f"\n전체 {len(results)}건 처리 완료")
    if results.error_count:
        print(f"오류: {results.error_count}건")


if __name__ == "__main__":
    main()

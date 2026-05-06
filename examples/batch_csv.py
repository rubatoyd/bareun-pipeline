"""
batch_csv.py — CSV 파일 배치 분석 예제

실행:
    python examples/batch_csv.py --input articles.csv --output results.csv
    python examples/batch_csv.py --input articles.csv --text-col content --id-col id
    python examples/batch_csv.py --input articles.csv --n 5000 --dict my-domain
"""
import argparse
import sys
import time
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("[ERROR] pandas 필요: pip install pandas")
    sys.exit(1)

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

from bareun_pipeline import BareunPipeline


def main():
    parser = argparse.ArgumentParser(description="bareun CSV 배치 분석")
    parser.add_argument("--input",    required=True,       help="입력 CSV 파일 경로")
    parser.add_argument("--output",   default=None,        help="출력 CSV 파일 경로 (기본: results_<timestamp>.csv)")
    parser.add_argument("--text-col", default=None,        dest="text_col", help="텍스트 컬럼명 (기본: 자동 감지)")
    parser.add_argument("--id-col",   default=None,        dest="id_col",   help="ID 컬럼명 (기본: 첫 번째 컬럼)")
    parser.add_argument("--n",        type=int, default=0, help="분석 건수 (0=전체)")
    parser.add_argument("--dict",     default=None,        help="사용자 사전 도메인 이름")
    parser.add_argument("--batch",    type=int, default=50, help="배치 크기 (기본: 50)")
    parser.add_argument("--workers",  type=int, default=8,  help="동시 요청 수 (기본: 8)")
    args = parser.parse_args()

    # ── 데이터 로드 ──────────────────────────────────────────────────────────
    in_path = Path(args.input)
    if not in_path.exists():
        print(f"[ERROR] 파일 없음: {in_path}")
        sys.exit(1)

    df = pd.read_csv(in_path, encoding="utf-8-sig", low_memory=False)
    print(f"[데이터] {in_path.name}  {len(df):,}건 로드")

    text_col = args.text_col or ("text" if "text" in df.columns else df.columns[-1])
    id_col   = args.id_col   or ("id"   if "id"   in df.columns else df.columns[0])

    df = df[df[text_col].notna() & (df[text_col].str.strip().str.len() >= 5)].copy()
    if args.n > 0:
        df = df.head(args.n)

    texts   = df[text_col].fillna("").tolist()
    doc_ids = df[id_col].astype(str).tolist()
    print(f"  분석 대상: {len(texts):,}건  (text_col={text_col!r}, id_col={id_col!r})")

    # ── 진행 표시 ────────────────────────────────────────────────────────────
    pbar = tqdm(total=len(texts), unit="docs") if HAS_TQDM else None

    def progress_cb(done: int, total: int):
        if pbar:
            pbar.n = done
            pbar.refresh()

    # ── 파이프라인 실행 ──────────────────────────────────────────────────────
    pipeline = BareunPipeline.from_env(batch_size=args.batch, max_workers=args.workers)
    dict_names = [args.dict] if args.dict else None

    import asyncio
    t0     = time.time()
    # progress_cb를 전달하기 위해 run_async 직접 호출
    batch  = asyncio.run(
        _run_with_progress(pipeline, texts, dict_names, progress_cb)
    )
    elapsed = round(time.time() - t0, 2)

    if pbar:
        pbar.close()

    # ── 저장 ─────────────────────────────────────────────────────────────────
    from datetime import datetime
    out_name = args.output or f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    out_path = Path(out_name)

    result_df = pd.DataFrame({
        "doc_id":    doc_ids,
        "nouns":     batch.noun_strings(),
        "morphemes": [r.morphemes for r in batch],
    })
    result_df.to_csv(out_path, index=False, encoding="utf-8-sig")

    speed = round(len(texts) / elapsed, 1)
    print(f"\n[완료] {elapsed}초 ({speed} docs/sec)  오류: {batch.error_count}건")
    print(f"[저장] {out_path}  ({len(result_df):,}건)")


async def _run_with_progress(pipeline, texts, dict_names, progress_cb):
    """진행 콜백을 client에 직접 전달."""
    from bareun_pipeline.client import BareunClient
    from bareun_pipeline.pipeline import BatchResult, AnalysisResult

    client = pipeline._client
    noun_strs, morph_strs, errors = await client.analyze_async(
        texts, dict_names, progress_cb=progress_cb
    )
    return BatchResult(
        results=[AnalysisResult(nouns=n, morphemes=m)
                 for n, m in zip(noun_strs, morph_strs)],
        error_count=errors,
    )


if __name__ == "__main__":
    main()

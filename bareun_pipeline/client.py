"""
client.py — bareun REST API 비동기 HTTP 클라이언트
"""
from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Callable

import httpx

try:
    import orjson
    def _loads(b: bytes): return orjson.loads(b)
except ImportError:
    import json
    def _loads(b: bytes): return json.loads(b)  # type: ignore[misc]

from .extractor import extract_nouns, post_combine_pairs as _post_combine


def _parse_response(
    raw_bytes: bytes,
    batch_len: int,
    combine_consecutive_nominals: bool = True,
    post_combine_pairs: frozenset | set | None = None,
) -> tuple[list[str], list[str]]:
    """JSON 응답 바이트 → (noun_strings, morpheme_strings). 스레드풀에서 실행.

    Args:
        raw_bytes: bareun API 원시 응답 바이트
        batch_len: 요청한 배치 크기 (응답 누락 보정용)
        combine_consecutive_nominals: 연속 NNG/NNP 자동 결합 여부 (기본 True)
        post_combine_pairs: 인접 명사 쌍 사후 결합 대상 cp_set (None=비활성)
    """
    data       = _loads(raw_bytes)
    nouns_out: list[str]  = []
    morphs_out: list[str] = []

    for sent in data.get("sentences", []):
        nouns: list[str]       = []
        token_strs: list[str]  = []

        for token in sent.get("tokens", []):
            tok_forms: list[tuple[str, str]] = []
            morph_parts: list[str]           = []

            for morph in token.get("morphemes", []):
                form = morph.get("text", {}).get("content", "")
                tag  = morph.get("tag", "")
                if form and tag:
                    morph_parts.append(f"{form}/{tag}")
                    tok_forms.append((form, tag))

            if morph_parts:
                token_strs.append("+".join(morph_parts))
            if tok_forms:
                nouns.extend(extract_nouns(
                    tok_forms,
                    combine_consecutive_nominals=combine_consecutive_nominals,
                ))

        # 사후 결합 (cp_set) 적용 — 결합 후 중복 제거
        if post_combine_pairs:
            nouns = _post_combine(nouns, post_combine_pairs)
        nouns_out.append(", ".join(dict.fromkeys(nouns)))
        morphs_out.append("|".join(token_strs))

    while len(nouns_out) < batch_len:
        nouns_out.append("")
        morphs_out.append("")

    return nouns_out, morphs_out


class BareunClient:
    """
    bareun REST API 비동기 클라이언트.

    Args:
        host:        bareun 서버 주소 (기본: http://localhost:5656)
        api_key:     bareun API 키
        batch_size:  한 번에 전송할 문장 수 (기본: 50)
        max_workers: 동시 HTTP 요청 수 (기본: 8)
        timeout:     요청 타임아웃 초 (기본: 120)
    """

    def __init__(
        self,
        host: str       = "http://localhost:5656",
        api_key: str    = "",
        batch_size: int = 50,
        max_workers: int = 8,
        timeout: float  = 120.0,
    ) -> None:
        self.host        = host.rstrip("/")
        self.api_key     = api_key
        self.batch_size  = batch_size
        self.max_workers = max_workers
        self.timeout     = timeout

    async def analyze_async(
        self,
        texts: list[str],
        custom_dict_names: list[str] | None = None,
        progress_cb: Callable[[int, int], None] | None = None,
        combine_consecutive_nominals: bool = True,
        post_combine_pairs: frozenset | set | None = None,
    ) -> tuple[list[str], list[str], int]:
        """
        비동기 배치 형태소 분석.

        Args:
            texts:             분석할 텍스트 리스트
            custom_dict_names: 적용할 사용자 사전 도메인 이름 목록
            progress_cb:       진행 콜백 fn(done, total)
            combine_consecutive_nominals: 연속 NNG/NNP 자동 결합 여부 (기본 True)
            post_combine_pairs: 인접 명사 쌍 사후 결합 대상 복합명사 집합 (None=비활성)

        Returns:
            (noun_strings, morpheme_strings, error_count)
            - noun_strings:    각 문서의 명사 (쉼표 구분 문자열)
            - morpheme_strings: 각 문서의 형태소 시퀀스 (파이프·플러스 구분)
            - error_count:     API 오류로 처리 실패한 문서 수
        """
        noun_strs   = [""] * len(texts)
        morph_strs  = [""] * len(texts)
        error_count = [0]
        done_docs   = [0]
        total       = len(texts)
        sem         = asyncio.Semaphore(self.max_workers)
        loop        = asyncio.get_running_loop()

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "api-key": self.api_key,
        }
        limits = httpx.Limits(
            max_keepalive_connections=self.max_workers,
            max_connections=self.max_workers + 4,
        )

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            async with httpx.AsyncClient(
                base_url=self.host,
                headers=headers,
                limits=limits,
                timeout=httpx.Timeout(self.timeout),
            ) as client:

                async def _one_batch(start: int) -> None:
                    batch   = texts[start : start + self.batch_size]
                    payload: dict = {
                        "sentences":     batch,
                        "language":      "ko-KR",
                        "encoding_type": "UTF8",
                    }
                    if custom_dict_names:
                        payload["custom_dict_names"] = custom_dict_names

                    raw: bytes | None = None
                    try:
                        async with sem:
                            r = await client.post(
                                "/bareun.LanguageService/AnalyzeSyntaxList",
                                json=payload,
                            )
                            r.raise_for_status()
                            raw = r.content
                    except Exception as exc:
                        error_count[0] += len(batch)
                        print(f"  [ERR] batch {start}~{start+len(batch)-1}: {exc}", flush=True)

                    if raw is not None:
                        n_strs, m_strs = await loop.run_in_executor(
                            executor,
                            _parse_response,
                            raw,
                            len(batch),
                            combine_consecutive_nominals,
                            post_combine_pairs,
                        )
                        for idx, (ns, ms) in enumerate(zip(n_strs, m_strs)):
                            noun_strs[start + idx]  = ns
                            morph_strs[start + idx] = ms

                    done_docs[0] += len(batch)
                    if progress_cb:
                        progress_cb(done_docs[0], total)

                await asyncio.gather(
                    *[_one_batch(i) for i in range(0, total, self.batch_size)]
                )

        return noun_strs, morph_strs, error_count[0]

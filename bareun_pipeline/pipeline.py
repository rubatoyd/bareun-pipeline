"""
pipeline.py — bareun 형태소 분석 파이프라인 (고수준 API)
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path

from .client import BareunClient


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


@dataclass
class AnalysisResult:
    """한 문서의 분석 결과."""

    nouns: str       # 명사 (쉼표 구분 문자열)
    morphemes: str   # 형태소 시퀀스 (파이프·플러스 구분 원시 문자열)

    @property
    def noun_list(self) -> list[str]:
        """명사를 파이썬 리스트로 반환."""
        return [n.strip() for n in self.nouns.split(",") if n.strip()]


@dataclass
class BatchResult:
    """배치 분석 전체 결과."""

    results: list[AnalysisResult] = field(default_factory=list)
    error_count: int = 0

    def __len__(self) -> int:
        return len(self.results)

    def __iter__(self):
        return iter(self.results)

    def __getitem__(self, idx):
        return self.results[idx]

    def noun_strings(self) -> list[str]:
        """전체 문서의 명사 문자열 리스트 반환."""
        return [r.nouns for r in self.results]

    def noun_lists(self) -> list[list[str]]:
        """전체 문서의 명사 리스트(of list) 반환."""
        return [r.noun_list for r in self.results]


class BareunPipeline:
    """
    bareun 형태소 분석 파이프라인.

    텍스트 리스트를 받아 명사와 형태소 시퀀스를 반환한다.
    내부적으로 비동기 배치 처리를 사용하므로 43K건도 수 분 내 처리 가능.

    Args:
        host:        bareun 서버 주소 (기본: http://localhost:5656)
        api_key:     bareun API 키
        batch_size:  한 번에 전송할 문장 수 (기본: 50)
        max_workers: 동시 HTTP 요청 수 (기본: 8)
        timeout:     요청 타임아웃 초 (기본: 120)

    Example::

        pipeline = BareunPipeline(host="http://localhost:5656", api_key="koba-...")

        results = pipeline.run(["청소년 정책 뉴스 기사...", "다른 기사..."])
        for r in results:
            print(r.noun_list)   # ["청소년", "정책", ...]
            print(r.morphemes)   # "청소년/NNG+정책/NNG|..."
    """

    def __init__(
        self,
        host: str        = "http://localhost:5656",
        api_key: str     = "",
        batch_size: int  = 50,
        max_workers: int = 8,
        timeout: float   = 120.0,
    ) -> None:
        self._client = BareunClient(
            host=host,
            api_key=api_key,
            batch_size=batch_size,
            max_workers=max_workers,
            timeout=timeout,
        )

    @classmethod
    def from_env(cls, env_file: str | Path | None = None, **kwargs) -> "BareunPipeline":
        """
        환경 변수 또는 .env 파일에서 설정을 읽어 파이프라인을 생성한다.

        Args:
            env_file: .env 파일 경로 (생략 시 현재 디렉토리 → 홈 디렉토리 순으로 탐색)
            **kwargs: BareunPipeline 생성자 인수 (host, api_key 등 오버라이드 가능)

        Example::

            pipeline = BareunPipeline.from_env()
            pipeline = BareunPipeline.from_env(".env", batch_size=100)
        """
        if env_file:
            _load_dotenv(Path(env_file))
        else:
            for candidate in (Path(".env"), Path.home() / ".env"):
                if candidate.exists():
                    _load_dotenv(candidate)
                    break

        host    = kwargs.pop("host",    os.environ.get("BAREUN_HOST",    "http://localhost:5656"))
        api_key = kwargs.pop("api_key", os.environ.get("BAREUN_API_KEY", ""))
        return cls(host=host, api_key=api_key, **kwargs)

    def run(
        self,
        texts: list[str],
        custom_dict_names: list[str] | None = None,
    ) -> BatchResult:
        """
        동기 배치 분석.

        Args:
            texts:             분석할 텍스트 리스트
            custom_dict_names: 적용할 사용자 사전 도메인 이름 목록

        Returns:
            BatchResult (list[AnalysisResult] + error_count)
        """
        return asyncio.run(self.run_async(texts, custom_dict_names))

    async def run_async(
        self,
        texts: list[str],
        custom_dict_names: list[str] | None = None,
    ) -> BatchResult:
        """
        비동기 배치 분석. asyncio 이벤트 루프 안에서 직접 await 가능.

        Example::

            results = await pipeline.run_async(texts)
        """
        noun_strs, morph_strs, errors = await self._client.analyze_async(
            texts, custom_dict_names
        )
        return BatchResult(
            results=[
                AnalysisResult(nouns=n, morphemes=m)
                for n, m in zip(noun_strs, morph_strs)
            ],
            error_count=errors,
        )

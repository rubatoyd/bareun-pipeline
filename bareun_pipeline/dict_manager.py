"""
dict_manager.py — bareun 사용자 사전 관리
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx

from .pipeline import _load_dotenv


class DictManager:
    """
    bareun 사용자 사전(CustomDictionary) 관리 클라이언트.

    Args:
        host:    bareun 서버 주소 (기본: http://localhost:5656)
        api_key: bareun API 키

    Example:
        dm = DictManager(host="http://localhost:5656", api_key="koba-...")

        # 사전 등록
        dm.register(
            domain="my-domain",
            np_set=["청소년참여위원회", "학교폭력대책위원회"],
            cp_set=["학교폭력예방"],
        )

        # 등록 확인
        dm.list_domains()

        # 단문 테스트
        dm.test(domain="my-domain", text="청소년참여위원회에서 정책을 논의했다.")
    """

    ENDPOINT_UPDATE = "/bareun.CustomDictionaryService/UpdateCustomDictionary"
    ENDPOINT_LIST   = "/bareun.CustomDictionaryService/GetCustomDictionaryList"
    ENDPOINT_SYNTAX = "/bareun.LanguageService/AnalyzeSyntax"

    @classmethod
    def from_env(cls, env_file: str | Path | None = None, **kwargs) -> "DictManager":
        """환경 변수 또는 .env 파일에서 설정을 읽어 생성한다."""
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

    def __init__(
        self,
        host: str    = "http://localhost:5656",
        api_key: str = "",
        timeout: float = 30.0,
    ) -> None:
        self.host    = host.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._headers = {
            "Content-Type": "application/json; charset=utf-8",
            "api-key": api_key,
        }

    def _post(self, endpoint: str, payload: dict) -> dict:
        resp = httpx.post(
            f"{self.host}{endpoint}",
            json=payload,
            headers=self._headers,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _word_list(words: list[str]) -> dict:
        return {"items": {w: 1 for w in words}, "type": "WORD_LIST"}

    def register(
        self,
        domain: str,
        np_set: list[str] | None        = None,
        cp_set: list[str] | None        = None,
        cp_caret_set: list[str] | None  = None,
        vv_set: list[str] | None        = None,
        va_set: list[str] | None        = None,
    ) -> None:
        """
        bareun 서버에 사용자 사전을 등록(갱신)한다.

        Args:
            domain:       사전 도메인 이름 (영문 slug 권장, 예: "youth-policy")
            np_set:       고유명사 목록
            cp_set:       복합명사 목록
            cp_caret_set: 복합명사 분리 지정 목록 (예: "학교^폭력")
            vv_set:       동사 목록
            va_set:       형용사 목록
        """
        wl = self._word_list
        payload = {
            "domain_name": domain,
            "dict": {
                "domain_name":  domain,
                "np_set":       wl(np_set       or []),
                "cp_set":       wl(cp_set       or []),
                "cp_caret_set": wl(cp_caret_set or []),
                "vv_set":       wl(vv_set       or []),
                "va_set":       wl(va_set       or []),
            },
        }
        self._post(self.ENDPOINT_UPDATE, payload)
        total = sum(len(x) for x in [np_set or [], cp_set or [], cp_caret_set or [],
                                     vv_set or [], va_set or []])
        print(f"[DictManager] '{domain}' 등록 완료 (총 {total}개 단어)")

    def list_domains(self) -> list[dict]:
        """서버에 등록된 사전 목록을 반환한다."""
        data  = self._post(self.ENDPOINT_LIST, {})
        dicts = data.get("customDicts", data.get("custom_dicts", []))
        if dicts:
            print(f"[DictManager] 등록된 사전 {len(dicts)}개:")
            for d in dicts:
                print(f"  - {d}")
        else:
            print("[DictManager] 서버에 등록된 사전 없음")
        return dicts

    def test(self, domain: str, text: str) -> list[dict]:
        """
        등록된 사전을 적용하여 단일 문장을 분석하고 결과를 출력한다.

        Returns:
            [{"form": "청소년참여위원회", "tag": "NNP", "in_custom_dict": True}, ...]
        """
        data    = self._post(
            self.ENDPOINT_SYNTAX,
            {
                "document":          {"content": text, "language": "ko-KR"},
                "encoding_type":     "UTF8",
                "custom_dict_names": [domain],
            },
        )
        results = []
        print(f"\n[DictManager] 분석: {text}\n")
        for sent in data.get("sentences", []):
            for token in sent.get("tokens", []):
                for m in token.get("morphemes", []):
                    form       = m.get("text", {}).get("content", "")
                    tag        = m.get("tag", "")
                    in_custom  = m.get("outOfVocab", "") == "IN_CUSTOM_DICT"
                    marker     = " ◀ 사전" if in_custom else ""
                    print(f"  {form}/{tag}{marker}")
                    results.append({"form": form, "tag": tag, "in_custom_dict": in_custom})
        return results

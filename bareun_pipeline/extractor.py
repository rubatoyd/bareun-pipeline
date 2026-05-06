"""
extractor.py — bareun 형태소 시퀀스에서 명사 추출
"""
import re
from collections.abc import Sequence

_DEUL        = re.compile(r"들$")
_COMBINE     = frozenset({"NNG", "NNP"})
_SKIP_XSN    = frozenset({"들", "님", "씨", "분", "치", "짜리", "째"})


def extract_nouns(tok_forms: Sequence[tuple[str, str]]) -> list[str]:
    """
    bareun 형태소 시퀀스 → 중복 없는 명사 리스트.

    Args:
        tok_forms: [(형태, 품사태그), ...] — bareun morphemes 리스트

    Returns:
        명사 문자열 리스트 (순서 유지, 중복 제거)

    결합 우선순위:
      1. XPN + NNG/NNP + XSN  → 비+자살+적 → 비자살적
      2. XPN + NNG/NNP        → 비+자살    → 비자살
      3. NNG/NNP + XSN        → 사회+적    → 사회적
      4. 연속 NNG/NNP          → 사회+공헌  → 사회공헌
      5. NNB, SL 단독
      6. XSN 단독 (조사 형 제외)
    """
    sub     = _DEUL.sub
    combine = _COMBINE
    skip    = _SKIP_XSN
    nouns: list[str] = []
    i, n = 0, len(tok_forms)

    while i < n:
        form, tag = tok_forms[i]

        if tag == "XPN" and i + 2 < n:
            f1, t1 = tok_forms[i + 1]
            f2, t2 = tok_forms[i + 2]
            if t1 in combine and t2 == "XSN":
                nouns.append(form + f1 + ("" if f2 in skip else f2))
                i += 3
                continue

        if tag == "XPN" and i + 1 < n:
            f1, t1 = tok_forms[i + 1]
            if t1 in combine:
                nouns.append(form + f1)
                i += 2
                continue

        if tag in combine and i + 1 < n:
            f1, t1 = tok_forms[i + 1]
            if t1 == "XSN":
                nouns.append(form if f1 in skip else form + f1)
                i += 2
                continue

        if tag in combine:
            j = i + 1
            while j < n and tok_forms[j][1] in combine:
                j += 1
            nouns.append("".join(tok_forms[k][0] for k in range(i, j)))
            i = j
            continue

        if tag in {"NNB", "SL"}:
            nouns.append(form)
        elif tag == "XSN" and form not in skip:
            nouns.append(form)

        i += 1

    result = []
    for noun in nouns:
        noun = sub("", noun).strip()
        if noun:
            result.append(noun)
    return list(dict.fromkeys(result))

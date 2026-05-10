"""
extractor.py — bareun 형태소 시퀀스에서 명사 추출
"""
import re
from collections.abc import Sequence

_DEUL        = re.compile(r"들$")
_COMBINE     = frozenset({"NNG", "NNP"})
_SKIP_XSN    = frozenset({"들", "님", "씨", "분", "치", "짜리", "째"})


def extract_nouns(
    tok_forms: Sequence[tuple[str, str]],
    combine_consecutive_nominals: bool = True,
) -> list[str]:
    """
    bareun 형태소 시퀀스 → 중복 없는 명사 리스트.

    Args:
        tok_forms: [(형태, 품사태그), ...] — bareun morphemes 리스트
        combine_consecutive_nominals: True(기본)면 연속 NNG/NNP를 자동 결합한다
            (예: 사회+공헌 → 사회공헌). False면 각 명사를 분리 유지한다.
            토픽 모델 입력 등 어휘 변별력이 중요한 용례에서는 False를 권장하며,
            의미 단위 보존이 필요한 복합명사는 bareun cp_set 등록으로 명시한다.

    Returns:
        명사 문자열 리스트 (순서 유지, 중복 제거)

    결합 우선순위:
      1. XPN + NNG/NNP + XSN  → 비+자살+적 → 비자살적
      2. XPN + NNG/NNP        → 비+자살    → 비자살
      3. NNG/NNP + XSN        → 사회+적    → 사회적
      4. 연속 NNG/NNP          → 사회+공헌  → 사회공헌  (combine_consecutive_nominals=True 시)
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
            if combine_consecutive_nominals:
                j = i + 1
                while j < n and tok_forms[j][1] in combine:
                    j += 1
                nouns.append("".join(tok_forms[k][0] for k in range(i, j)))
                i = j
                continue
            else:
                nouns.append(form)
                i += 1
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


def post_combine_pairs(nouns: list[str], cp_set: set[str]) -> list[str]:
    """
    인접 명사 쌍이 cp_set에 등록된 복합명사라면 결합한다.

    bareun 서버의 사용자 사전 cp_set은 입력 텍스트에서 공백 없이 붙은 경우에만
    결합되는 한계가 있어, 클라이언트 측에서 후처리로 의미 단위 보존을 보장한다.

    중복 제거는 호출자가 결합 이후 단계에서 일괄 처리한다 (조합 기회 보존).

    Args:
        nouns: 추출 명사 리스트 (중복 가능, 순서 유지)
        cp_set: 결합 대상 복합명사 집합

    Returns:
        결합이 적용된 명사 리스트 (중복 미제거)

    예) ['다문화', '학생'] + cp_set={'다문화학생'} → ['다문화학생']
    """
    if not cp_set:
        return nouns
    result: list[str] = []
    i, n = 0, len(nouns)
    while i < n:
        if i + 1 < n:
            combined = nouns[i] + nouns[i + 1]
            if combined in cp_set:
                result.append(combined)
                i += 2
                continue
        result.append(nouns[i])
        i += 1
    return result

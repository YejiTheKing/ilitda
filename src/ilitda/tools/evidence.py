"""verify_evidence: LLM이 근거로 든 문장이 원문에 실제로 있는지 확인한다.

LLM은 근거를 지어낼 수 있다. 근거 문장이 원문에 없으면 그 단계는 안내하지 않고 '확인 필요'로 돌린다.
"""
import re
from difflib import SequenceMatcher


def _squash(s):
    return re.sub(r"[\s··,.:;()\[\]|\-_~※*]", "", s).lower()


def find_quote(quote, text, min_ratio=0.85):
    """인용문이 원문에 있으면 (True, 일치율). 공백·구두점 차이는 무시하고, 약간의 오타는 허용한다."""
    q, t = _squash(quote), _squash(text)
    if not q:
        return False, 0.0
    if q in t:
        return True, 1.0
    # 부분 일치: 인용문 길이의 창을 원문 위로 옮기며 가장 비슷한 곳을 찾는다
    best = 0.0
    step = max(1, len(q) // 4)
    for i in range(0, max(1, len(t) - len(q) + 1), step):
        r = SequenceMatcher(None, q, t[i:i + len(q)]).ratio()
        if r > best:
            best = r
            if best >= 0.98:
                break
    return best >= min_ratio, round(best, 2)


def verify_evidence(steps, documents):
    """각 단계의 근거를 검사해 status를 매긴다.

    steps: [{"order", "action", "evidence": [{"doc": 파일명, "quote": 인용문}]}]
    돌려주는 값: 검사 결과가 붙은 steps 사본. status는 'ok' 또는 'unverified'.
    """
    by_name = {d["name"]: d["text"] for d in documents}
    out = []
    for s in steps:
        checked = []
        for ev in s.get("evidence", []):
            text = by_name.get(ev.get("doc", ""))
            if text is None:
                checked.append(ev | {"found": False, "ratio": 0.0, "why": "그런 파일이 없음"})
                continue
            found, ratio = find_quote(ev.get("quote", ""), text)
            checked.append(ev | {"found": found, "ratio": ratio, "why": "" if found else "원문에 없는 문장"})
        ok = any(c["found"] for c in checked)
        out.append(s | {"evidence": checked, "status": "ok" if ok else "unverified"})
    return out

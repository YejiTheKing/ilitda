"""버전 묶기, 최신본 판별, 변경점 비교.

파일 수정 날짜는 쓰지 않는다. 문서 이름과 내용만으로 판단한다.
판별 근거를 함께 돌려주고, 근거가 약하면 '확인 필요'로 표시한다.
"""
import re
import unicodedata
from difflib import SequenceMatcher

# 파일 이름에서 버전 표시를 떼어 내 같은 문서 계열인지 본다
NAME_NOISE = re.compile(
    r"[\s_\-()\[\]]*(복사본|copy|사본|수정|최종|최신|final|new|old|rev\.?\s*\d+|v\d+(\.\d+)?|\d{4}[.\-]?\d{0,2}[.\-]?\d{0,2}|\(\d+\))",
    re.I,
)
DATE = re.compile(r"((?:19|20)\d{2})\s*[.\-/년]\s*(0?[1-9]|1[0-2])(?:\s*[.\-/월]\s*(0?[1-9]|[12]\d|3[01])?)?")
VERSION_MARK = re.compile(r"(개정|수정|변경|rev\.?\s*\d+|v\d+(\.\d+)?|version|ver\.?\s*\d+)", re.I)
# 사람이 의도적으로 매긴 개정번호. 있으면 가장 먼저 믿는다
REVISION_IN_TEXT = re.compile(
    r"(?:개정\s*번호|개정\s*차수|개정|리비전|버전|version|ver|rev)\s*[:：.]?\s*(?:v|제)?\s*(\d+(?:\.\d+)*)\s*(?:차|판|호)?|"
    r"제\s*(\d+)\s*차\s*개정|(?<![A-Za-z0-9])v(\d+(?:\.\d+)+)(?![0-9])",
    re.I,
)
REVISION_IN_NAME = re.compile(r"(?:^|[_\s\-(])(?:v|ver|rev|r)\.?\s*(\d+(?:\.\d+)*)(?=$|[_\s\-).])", re.I)


def stem(name):
    base = unicodedata.normalize("NFC", name).rsplit(".", 1)[0]
    base = NAME_NOISE.sub("", base)
    return re.sub(r"[\s_\-]+", "", base).lower()


def norm_lines(text):
    out = []
    for ln in text.splitlines():
        ln = re.sub(r"\s+", " ", ln).strip()
        if len(ln) >= 2:
            out.append(ln)
    return out


def _shingles(text, k=4):
    t = re.sub(r"\s+", "", text)
    return {t[i:i + k] for i in range(max(0, len(t) - k + 1))}


def similarity(a, b):
    sa, sb = _shingles(a), _shingles(b)
    return len(sa & sb) / len(sa | sb) if sa and sb else 0.0


def dates_in(text):
    out = []
    for m in DATE.finditer(text):
        y, mo = int(m.group(1)), int(m.group(2))
        if 2000 <= y <= 2100:
            out.append((y, mo))
    return out


def revision_number(text, name="", head_lines=15):
    """문서가 스스로 밝힌 개정번호. 본문 앞부분을 먼저 보고, 없으면 파일 이름을 본다. 없으면 None."""
    head = "\n".join(norm_lines(text)[:head_lines])
    for m in REVISION_IN_TEXT.finditer(head):
        num = m.group(1) or m.group(2) or m.group(3)
        if num:
            return tuple(int(x) for x in num.split("."))
    m = REVISION_IN_NAME.search(unicodedata.normalize("NFC", name).rsplit(".", 1)[0])
    if m:
        return tuple(int(x) for x in m.group(1).split("."))
    return None


BLANK = re.compile(r"_{3,}|□|\[\s*\]|\(\s*\)|20__|__년|__월")


def doc_role(text):
    """'form'(빈 양식) 또는 'record'(작성된 기록). 빈칸 표시가 많으면 양식으로 본다."""
    blanks = len(BLANK.findall(text))
    lines = max(1, len(norm_lines(text)))
    return "form" if blanks >= 2 and blanks / lines >= 0.15 else "record"


def group_versions(documents, threshold=0.35):
    """같은 문서 계열끼리 묶는다. 이름 줄기가 같거나 내용이 충분히 비슷하면 같은 계열.

    빈 양식과 그 양식으로 작성한 기록은 내용이 비슷해도 다른 계열이다.
    작성된 기록이 양식의 '최신본'으로 뽑히는 일을 막기 위해서다.
    """
    n = len(documents)
    parent = list(range(n))
    for d in documents:
        d["role"] = doc_role(d["text"])

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    reasons = {}
    for i in range(n):
        for j in range(i + 1, n):
            a, b = documents[i], documents[j]
            if a["role"] != b["role"]:
                continue
            same_stem = stem(a["name"]) == stem(b["name"]) and stem(a["name"])
            sim = similarity(a["text"], b["text"])
            if same_stem or sim >= threshold:
                parent[find(i)] = find(j)
                reasons[(i, j)] = "이름 줄기 동일" if same_stem else f"내용 유사도 {sim:.2f}"
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    families = []
    for members in groups.values():
        families.append({
            "members": [documents[i] for i in members],
            "why": [reasons[k] for k in reasons if k[0] in members and k[1] in members],
        })
    return families


def pick_latest(family):
    """계열 하나에서 최신본을 고른다. {"latest", "ranked", "evidence", "confident"}.

    판별 순서: ① 문서가 밝힌 개정번호(모든 버전에 있을 때) ② 내용 속 가장 최근 날짜
    ③ 개정·수정 표시 개수 ④ 다른 버전에 없는 내용의 양 ⑤ 문서 내부 저장 횟수.
    전부 같으면 확정하지 않는다.
    """
    members = family["members"]
    if len(members) == 1:
        return {"latest": members[0], "ranked": members, "evidence": ["버전이 하나뿐"], "confident": True}

    scores = []
    for d in members:
        text = d["text"]
        lines = set(norm_lines(text))
        latest_date = max(dates_in(text), default=(0, 0))
        marks = len(VERSION_MARK.findall(text))
        # 다른 버전에는 없는 줄의 수에서 반대 경우를 뺀 값. 양수면 내용이 더해진 쪽
        added = sum(len(lines - set(norm_lines(o["text"]))) - len(set(norm_lines(o["text"])) - lines)
                    for o in members if o is not d)
        revision = int((d.get("meta") or {}).get("revision") or 0)
        scores.append({"doc": d, "rev": revision_number(text, d.get("name", "")), "date": latest_date,
                       "marks": marks, "added": added, "revision": revision})

    # 개정번호는 모든 버전이 밝히고 있을 때만 쓴다. 일부에만 있으면 비교가 안 된다
    revs = [s["rev"] for s in scores]
    use_rev = all(r is not None for r in revs) and len(set(revs)) > 1
    for s_ in scores:
        s_["rev_key"] = s_["rev"] if use_rev else (0,)

    ranked = sorted(scores, key=lambda s: (s["rev_key"], s["date"], s["marks"], s["added"], s["revision"]), reverse=True)
    top, second = ranked[0], ranked[1]
    evidence = []
    if use_rev and top["rev"] > second["rev"]:
        evidence.append(f"문서가 밝힌 개정번호 {'.'.join(map(str, top['rev']))} (다음 버전은 {'.'.join(map(str, second['rev']))})")
    elif any(r is not None for r in revs) and not use_rev:
        evidence.append("개정번호가 일부 버전에만 있어 비교에 쓰지 않음")
    if top["date"] > second["date"]:
        other = f"{second['date'][0]}.{second['date'][1]:02d}" if second["date"] > (0, 0) else "날짜 없음"
        evidence.append(f"내용 속 가장 최근 날짜 {top['date'][0]}.{top['date'][1]:02d} (다음 버전은 {other})")
    if top["marks"] > second["marks"]:
        evidence.append(f"개정·수정 표시 {top['marks']}곳")
    if top["added"] > second["added"]:
        evidence.append(f"다른 버전에 없는 내용 {top['added']}줄 추가")
    if top["revision"] > second["revision"]:
        evidence.append(f"문서 내부 저장 횟수 {top['revision']}")
    confident = (top["rev_key"], top["date"], top["marks"], top["added"]) != (second["rev_key"], second["date"], second["marks"], second["added"])
    if not confident:
        evidence.append("판별 근거 부족: 책임자 확인 필요")
    return {"latest": top["doc"], "ranked": [s["doc"] for s in ranked], "evidence": evidence, "confident": confident}


# "항목: 값" 또는 표의 "항목 | 값" 꼴. 양식의 칸 단위 비교에 쓴다
FIELD = re.compile(r"^\s*([^:：|]{1,30}?)\s*[:：]\s*(.*?)\s*$")
FIELD_NOISE = {"문서명", "제목", "개정", "개정번호", "비고"}


def fields_of(text):
    """줄에서 (항목, 값) 쌍을 뽑는다. 같은 항목이 여러 번 나오면 번호를 붙인다."""
    out, seen = {}, {}
    for ln in norm_lines(text):
        m = FIELD.match(ln)
        if m:
            key, value = m.group(1).strip(), m.group(2).strip()
        elif " | " in ln:
            key, value = ln.split(" | ", 1)
            key, value = key.strip(), value.strip()
        else:
            continue
        if not key or key in FIELD_NOISE or len(key) > 30:
            continue
        seen[key] = seen.get(key, 0) + 1
        out[key if seen[key] == 1 else f"{key}#{seen[key]}"] = value
    return out


def _is_field_line(ln):
    return bool(FIELD.match(ln)) or " | " in ln


def diff_versions(old, new):
    """구버전과 최신본의 차이.

    양식의 칸("항목: 값")은 항목 단위로 비교해 field를 채운다. 그 밖의 줄은 줄 단위로 비교한다.
    [{"kind": added|removed|changed, "field": 항목 또는 None, "old", "new"}]
    """
    changes = []
    fo, fn = fields_of(old["text"]), fields_of(new["text"])
    for key in list(fo) + [k for k in fn if k not in fo]:
        a, b = fo.get(key), fn.get(key)
        if a == b:
            continue
        kind = "changed" if a is not None and b is not None else ("removed" if b is None else "added")
        name = key.split("#")[0]
        changes.append({"kind": kind, "field": name,
                        "old": f"{name}: {a}" if a is not None else None,
                        "new": f"{name}: {b}" if b is not None else None})

    a_lines = [ln for ln in norm_lines(old["text"]) if not _is_field_line(ln)]
    b_lines = [ln for ln in norm_lines(new["text"]) if not _is_field_line(ln)]
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a_lines, b_lines, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        if tag == "replace":
            for o, n in zip(a_lines[i1:i2], b_lines[j1:j2]):
                changes.append({"kind": "changed", "field": None, "old": o, "new": n})
            for o in a_lines[i1 + (j2 - j1):i2]:
                changes.append({"kind": "removed", "field": None, "old": o, "new": None})
            for n in b_lines[j1 + (i2 - i1):j2]:
                changes.append({"kind": "added", "field": None, "old": None, "new": n})
        elif tag == "delete":
            changes.extend({"kind": "removed", "field": None, "old": o, "new": None} for o in a_lines[i1:i2])
        elif tag == "insert":
            changes.extend({"kind": "added", "field": None, "old": None, "new": n} for n in b_lines[j1:j2])
    return changes

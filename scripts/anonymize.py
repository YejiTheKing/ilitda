"""실제 자료의 회사명·사람 이름을 가명으로 바꾼 사본을 만든다.

사용:
  1) 후보 뽑기:  .venv/bin/python scripts/anonymize.py data/real/AS처리 --scan
     → data/real/AS처리_비식별/치환표.json 에 회사명처럼 보이는 낱말 목록이 생긴다. 열어서 바꿀 이름을 적는다.
  2) 적용:       .venv/bin/python scripts/anonymize.py data/real/AS처리
     → 치환표를 적용하고 전화번호·주소·계좌 등 형식 정보를 가린 사본을 같은 폴더에 .txt로 만든다.

원본은 건드리지 않는다. 사본 폴더도 저장소에는 올라가지 않는다(data/real 제외).
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "src"))

from ilitda.safety.mask import mask  # noqa: E402
from ilitda.tools.parse import UnreadableError, parse_document  # noqa: E402

COMPANY = re.compile(r"[가-힣A-Za-z0-9&]{1,12}\s?(?:\(주\)|\(유\)|㈜|주식회사|산업|FNT|테크|정밀|전자|상사|기계|시스템|물산|건설|엔지니어링|공업)")
HANJA = re.compile(r"[一-鿿]{2,}(?:\([^)]*\))?")
PERSON = re.compile(r"(?:담당자|담당|작성자|승인|대표|부장|과장|대리|사원|기사)\s*[:：]?\s*([가-힣]{2,4})(?=\s|$|\||,)")


def read_all(folder):
    docs = []
    for p in sorted(Path(folder).iterdir()):
        if p.is_file() and not p.name.startswith("."):
            try:
                docs.append(parse_document(p, allowed=[Path(folder).resolve().parent]))
            except UnreadableError as e:
                print(f"건너뜀: {p.name} ({e})")
    return docs


def scan(folder, out):
    found = {}
    for d in read_all(folder):
        for pat, kind in ((COMPANY, "회사"), (HANJA, "한자 상호"), (PERSON, "사람")):
            for m in pat.finditer(d["text"]):
                token = (m.group(1) if pat is PERSON else m.group(0)).strip()
                found.setdefault(token, {"kind": kind, "files": set()})["files"].add(d["name"])
    table = {t: {"kind": v["kind"], "files": sorted(v["files"]), "replace_with": ""} for t, v in sorted(found.items())}
    out.mkdir(parents=True, exist_ok=True)
    (out / "치환표.json").write_text(json.dumps(table, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"후보 {len(table)}개 → {out / '치환표.json'} (replace_with에 가명을 적고, 바꾸지 않을 것은 비워 두기)")


def apply(folder, out):
    table = json.loads((out / "치환표.json").read_text(encoding="utf-8"))
    repl = {k: v["replace_with"] for k, v in table.items() if v.get("replace_with")}
    # 긴 이름부터 바꿔야 짧은 이름이 긴 이름의 일부를 먼저 바꾸는 일이 없다
    order = sorted(repl, key=len, reverse=True)
    total = {}
    for d in read_all(folder):
        text = d["text"]
        for k in order:
            text = text.replace(k, repl[k])
        text, counts = mask(text)
        for c, n in counts.items():
            total[c] = total.get(c, 0) + n
        stem = Path(d["name"]).stem
        for k in order:  # 파일 이름의 실명도 바꾼다
            stem = stem.replace(k, repl[k])
        target = out / (stem + ".txt")
        target.write_text(text, encoding="utf-8")
        print(f"{d['name']} → {target.name}")
    print(f"가명 치환 {len(repl)}종, 형식 가림 {total}")
    print("사본을 열어 남은 실명·주소가 없는지 눈으로 확인하세요.")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    folder = Path(args[0]) if args else None
    if not folder or not folder.is_dir():
        print(__doc__)
        return 1
    out = folder.parent / (folder.name + "_비식별")
    if "--scan" in sys.argv:
        scan(folder, out)
    else:
        apply(folder, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""변경점 탐지율과 오탐 수를 잰다.

사용:
  .venv/bin/python scripts/evaluate_changes.py                       # data/eval/seeded + gold.json 채점
  .venv/bin/python scripts/evaluate_changes.py <폴더> --detect-only  # 정답 없이 탐지 목록만 출력 (블라인드 평가용)

채점 대상 폴더에는 '양식 쌍'이 있어야 한다. 최신본은 pick_latest가 고르고, 나머지와 비교한다.
LLM은 쓰지 않는다. 코드만으로 되는 부분(F1)의 성능이다.
"""
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "src"))

from ilitda.runlog import RunLog  # noqa: E402
from ilitda.tools.ingest import ingest  # noqa: E402
from ilitda.tools.versions import diff_versions, group_versions, pick_latest  # noqa: E402


def detect(folder):
    docs = ingest(folder, RunLog(root=tempfile.mkdtemp()), allowed=[Path(folder).resolve().parent.parent])["documents"]
    out = []
    for fam in group_versions(docs):
        if len(fam["members"]) < 2:
            continue
        picked = pick_latest(fam)
        for old in picked["ranked"][1:]:
            for c in diff_versions(old, picked["latest"]):
                out.append({"latest": picked["latest"]["name"], "old": old["name"], "field": c["field"],
                            "kind": c["kind"], "old_text": c["old"], "new_text": c["new"]})
    return out


def main():
    args = sys.argv[1:]
    detect_only = "--detect-only" in args
    folder = next((a for a in args if not a.startswith("--")), None)

    if detect_only:
        changes = detect(folder)
        print(json.dumps(changes, ensure_ascii=False, indent=1))
        print(f"\n탐지 {len(changes)}건 (항목 단위 {sum(1 for c in changes if c['field'])}, 줄 단위 {sum(1 for c in changes if not c['field'])})",
              file=sys.stderr)
        return 0

    base = Path(folder or "data/eval/seeded")
    gold = json.loads((base / "gold.json").read_text(encoding="utf-8"))
    changed = detect(base / "changed")
    unchanged = detect(base / "unchanged")

    gold_fields = {g["field"] for g in gold["changed_fields"]}
    found_fields = {c["field"] for c in changed if c["field"]}
    hit = gold_fields & found_fields
    missed = gold_fields - found_fields
    false_fields = found_fields - gold_fields
    # 줄 단위로만 잡힌 것 중 정답 항목 이름이 들어 있으면 부분 적중으로 따로 센다
    line_only = [c for c in changed if not c["field"]]
    partial = {g for g in missed if any(g in (c["old_text"] or "") or g in (c["new_text"] or "") for c in line_only)}

    result = {
        "dataset": gold["description"], "evaluated_at": datetime.now().isoformat(timespec="seconds"),
        "gold_changes": len(gold_fields), "detected_field_changes": len(found_fields),
        "hits": len(hit), "recall": round(len(hit) / len(gold_fields), 3) if gold_fields else None,
        "missed": sorted(missed), "partial_by_line": sorted(partial),
        "false_positive_fields": sorted(false_fields),
        "line_level_changes_in_changed_pair": len(line_only),
        "unchanged_pair_detected": len(unchanged), "unchanged_pair_expected": gold["unchanged_pair_expected_changes"],
        "unchanged_pair_items": [c["new_text"] or c["old_text"] for c in unchanged],
    }
    out = Path("docs/테스트결과") / f"{datetime.now():%Y-%m-%d}_변경점평가.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))
    print(f"\n기록: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

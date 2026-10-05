"""책임자가 화면에서 답한 내용과 테스터 피드백을 한곳에 모아 보여준다.

사용: .venv/bin/python scripts/export_answers.py            # 화면에 출력
      .venv/bin/python scripts/export_answers.py --json 파일  # JSON으로 저장 (제출용 실행의 답변 파일로 쓸 수 있음)

- 답변: runs/memory.sqlite (업무별·주제별, 답한 사람, 시각)
- 피드백: runs/feedback/*.json
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)


def answers():
    db = Path("runs/memory.sqlite")
    if not db.exists():
        return []
    rows = sqlite3.connect(str(db)).execute(
        "SELECT task, topic, question, answer, answered_by, answered_at FROM answers ORDER BY answered_at").fetchall()
    return [dict(zip(("task", "topic", "question", "answer", "answered_by", "answered_at"), r)) for r in rows]


def feedback():
    out = []
    for p in sorted(Path("runs/feedback").glob("*.json")):
        out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


def main():
    a, f = answers(), feedback()
    if "--json" in sys.argv:
        target = Path(sys.argv[sys.argv.index("--json") + 1])
        replies = {}
        for r in a:
            replies.setdefault(r["task"], {})[r["topic"]] = r["answer"]
        target.write_text(json.dumps({"answers": a, "replies_by_task": replies, "feedback": f}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"저장: {target} (답변 {len(a)}건, 피드백 {len(f)}건)")
        return
    print(f"책임자 답변 {len(a)}건")
    for r in a:
        print(f"  [{r['answered_at'][:16]}] {r['task'][:24]} | {r['topic']}\n      Q: {r['question'][:70]}\n      A: {r['answer'][:90]} ({r['answered_by']})")
    print(f"\n테스터 피드백 {len(f)}건")
    for e in f:
        acc = f", 정확도 {e['accuracy']}/5" if e.get("accuracy") else ""
        print(f"  [{e['date']}] {e['name']} ({e['org']}) {e['minutes']}분, 사용 의향 {e['intent']}/5{acc}, 내 파일 {'예' if e.get('own_files') else '아니요'}")
        if e.get("good"):
            print(f"      좋았던 점: {e['good'][:80]}")
        if e.get("bad"):
            print(f"      불편한 점: {e['bad'][:80]}")


if __name__ == "__main__":
    main()

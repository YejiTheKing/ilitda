"""실행 목록을 알아보기 쉽게 보여준다.

사용: .venv/bin/python scripts/list_runs.py                 # 전체 목록
      .venv/bin/python scripts/list_runs.py --fill           # 요약이 없는 옛 실행에 로그로부터 요약 만들기
      .venv/bin/python scripts/list_runs.py --archive 2026-10-03   # 그 날짜 이전 실행을 runs/_archive/로 옮김
"""
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
RUNS = Path("runs")
STATUS = {"goal": "목표 해석", "planned": "계획", "read": "자료 읽음", "no_documents": "자료 없음", "versions": "버전 정리",
          "procedure": "절차 복원", "answered": "확인 완료", "checklist": "체크리스트", "handover": "수행 확인",
          "pending_approval": "승인 보류", "completed": "인계 완료"}


def summary_from_log(d):
    """요약 파일이 없는 옛 실행은 로그에서 대충 뽑는다."""
    info = {}
    try:
        entries = [json.loads(l) for l in (d / "log.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    except OSError:
        return info
    for e in entries:
        m = re.match(r"목표 해석: 업무 '(.+?)', 신규자 (.+?), 책임자 (.+)", e["title"])
        if m:
            info.update(task=m.group(1), newcomer=m.group(2), owner=m.group(3))
        if e["title"] == "scan_folder":
            f = (e.get("inputs") or {}).get("folder", "")
            info["folder"] = f
            info["source"] = "업로드" if "uploads" in f else ("실제" if "real" in f else "가상")
        if e["title"].startswith("테스터가 파일"):
            info["source"] = "업로드"
        m = re.match(r"절차 (\d+)단계, 충돌 (\d+)건, 빈틈 (\d+)건", e["title"])
        if m:
            info.update(steps=int(m.group(1)), questions=int(m.group(2)) + int(m.group(3)))
        if e["title"] == "인계 완료 판정":
            info["status"] = "completed"
        elif e["title"].startswith("책임자 확인 요청") and info.get("status") != "completed":
            info["status"] = "procedure"
        elif e["kind"] == "error" and "한도" in str(e.get("detail")):
            info["status"] = "한도 도달"
    return info


def load(d):
    p = d / "summary.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return summary_from_log(d)


def main():
    runs = sorted((d for d in RUNS.iterdir() if d.is_dir() and d.name[:4].isdigit()), reverse=True)
    if "--fill" in sys.argv:
        n = 0
        for d in runs:
            if not (d / "summary.json").exists():
                info = summary_from_log(d)
                if info:
                    (d / "summary.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
                    n += 1
        print(f"요약 생성 {n}개")
    if "--archive" in sys.argv:
        cutoff = sys.argv[sys.argv.index("--archive") + 1].replace("-", "")
        dest = RUNS / "_archive"
        dest.mkdir(exist_ok=True)
        moved = 0
        for d in runs:
            if d.name[:8] < cutoff:
                shutil.move(str(d), str(dest / d.name))
                moved += 1
        print(f"{cutoff} 이전 실행 {moved}개를 {dest}로 옮김 (화면 목록에서 사라지고, 파일은 보관됨)")
        return
    print(f"{'실행 ID':<24} {'시각':<12} {'자료':<5} {'업무':<22} {'단계':>4} {'질문':>4} {'상태':<8} 공개")
    for d in runs:
        i = load(d)
        when = f"{d.name[4:6]}/{d.name[6:8]} {d.name[9:11]}:{d.name[11:13]}"
        print(f"{d.name:<24} {when:<12} {i.get('source', '?'):<5} {(i.get('task') or '-')[:20]:<22} "
              f"{str(i.get('steps', '')):>4} {str(i.get('questions', '')):>4} {STATUS.get(i.get('status'), i.get('status') or '-'):<8} "
              f"{'예' if i.get('public') else ''}")


if __name__ == "__main__":
    main()

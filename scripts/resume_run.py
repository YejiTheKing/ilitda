"""멈춘 실행을 명령줄에서 이어 간다 (대본 답변 사용).

사용: .venv/bin/python scripts/resume_run.py <실행 ID> <replies.json>
멈춤이 길어지면(5분) 어디서 멈췄는지 스택을 runs/_resume_trace.log에 남긴다.
"""
import faulthandler
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "src"))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
from ilitda.agent.runner import Runner  # noqa: E402
from ilitda.cli import _answer_from_file  # noqa: E402

run_id, replies_path = sys.argv[1], sys.argv[2]
replies = json.load(open(replies_path, encoding="utf-8"))
trace = open("runs/_resume_trace.log", "a")
faulthandler.dump_traceback_later(300, repeat=True, file=trace)

r = Runner(run_id=run_id, llm_mode="live")
try:
    pending = r._pending()
    print("멈춤:", pending and pending["type"], flush=True)
    if pending is None and r.state().get("status") not in ("completed", "no_documents", None):
        print("멈춤 없이 끊긴 실행 → 저장된 자리부터 이어 감", flush=True)
        pending = r.retry()
        print("→", pending and pending["type"], flush=True)
    same = 0
    while pending and pending["type"] != "error":
        reply = _answer_from_file(pending, replies)
        before = pending["type"]
        pending = r.resume(reply)
        print("→", pending and pending["type"], flush=True)
        same = same + 1 if pending and pending["type"] == before else 0
        if same >= 3:
            print("[중단] 같은 멈춤이 반복됨"); break
    state = r.state()
    print("상태:", state.get("status"))
    print("지표:", json.dumps(state.get("metrics", {}), ensure_ascii=False))
finally:
    r.close()

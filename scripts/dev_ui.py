"""화면 개발·확인용 서버 (파이썬 래퍼). 기본 공개 모드, MODE=private 이면 비공개 모드.

    .venv/bin/python scripts/dev_ui.py
"""
import os
import sys
from pathlib import Path

os.chdir(Path(__file__).resolve().parents[1])
if os.environ.get("MODE", "public") == "public":
    os.environ["ILITDA_PUBLIC"] = "1"
    os.environ["ILITDA_ALLOWED_DIRS"] = "data/sample,runs/uploads"
    os.environ.setdefault("ILITDA_MAX_LIVE_CALLS_PER_DAY", "80")
else:
    os.environ.pop("ILITDA_PUBLIC", None)
    os.environ.pop("ILITDA_MAX_LIVE_CALLS_PER_DAY", None)
    os.environ["ILITDA_ALLOWED_DIRS"] = "data/sample,data/real,runs/uploads"

from streamlit.web import cli  # noqa: E402

port = os.environ.get("PORT", "8504")
sys.argv = ["streamlit", "run", "src/ilitda/ui/app.py", "--server.port", port, "--server.headless", "true"]
sys.exit(cli.main())

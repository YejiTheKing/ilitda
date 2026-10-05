#!/bin/bash
# 실제 업무용(비공개) 실행. 이 PC에서만 접속되고 공개 링크가 아니다.
#   실행: scripts/run_private.sh        (끝낼 때는 Ctrl+C)
# - 실제 자료 폴더(data/real)와 가명 사본, 올린 파일을 모두 쓸 수 있다
# - 이전 실행 목록이 모두 보이고, 호출 한도가 없다 (비용은 본인 책임)
# - 테스터용 안내·피드백 화면은 없다
set -e
cd "$(dirname "$0")/.."
PORT=${PORT:-8502}
unset ILITDA_PUBLIC ILITDA_MAX_LIVE_CALLS_PER_DAY
export ILITDA_ALLOWED_DIRS=data/sample,data/real,runs/uploads
pkill -f "server.port $PORT" 2>/dev/null || true
echo "실제 업무용 화면: http://localhost:$PORT  (이 PC에서만 열립니다)"
exec .venv/bin/streamlit run src/ilitda/ui/app.py --server.port "$PORT" --server.headless true

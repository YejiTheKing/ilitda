#!/bin/bash
# 시연영상 촬영용 서버. 비공개(실제용) 화면을 쓰되, 기억·응답 저장소는 영상 전용으로 따로 둔다.
#   실행:      scripts/video_demo.sh            (끝낼 때는 Ctrl+C)
#   처음부터:  scripts/video_demo.sh --reset    (영상용 기억·캐시를 지워 1회차가 다시 실제 호출이 되게)
# - 공용 기억(runs/memory.sqlite)과 공용 캐시(runs/_llm_cache)는 건드리지 않는다
# - 1회차 실행은 실제 API 호출(로그에 토큰·초), 같은 파일로 2회차를 돌리면 답변 재사용 + 🔁 재생이 보인다
# - 8502(실제용)·8503(공개 테스트)은 그대로 둔다
set -e
cd "$(dirname "$0")/.."
PORT=${PORT:-8505}
MEM=runs/_memory_video.sqlite
CACHE=runs/_llm_cache_video
if [ "$1" = "--reset" ]; then
  rm -f "$MEM"; rm -rf "$CACHE"
  echo "영상용 기억·캐시를 지웠습니다. 다음 실행은 실제 호출입니다."
fi
unset ILITDA_PUBLIC ILITDA_MAX_LIVE_CALLS_PER_DAY
export ILITDA_ALLOWED_DIRS=data/sample,runs/uploads
export ILITDA_MEMORY_PATH="$MEM"
export ILITDA_LLM_CACHE="$CACHE"
pkill -f "server.port $PORT" 2>/dev/null || true
echo "촬영용 화면: http://localhost:$PORT   (기억 $MEM · 캐시 $CACHE)"
exec .venv/bin/streamlit run src/ilitda/ui/app.py --server.port "$PORT" --server.headless true

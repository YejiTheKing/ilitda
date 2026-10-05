#!/bin/bash
# 온라인 테스터용 공개 링크를 연다.
#   실행: scripts/public_demo.sh        (끝낼 때는 Ctrl+C)
# - 가상 자료와 테스터가 올린 파일만 보이고(data/real 숨김), 남의 실행은 보이지 않으며, 하루 AI 호출 한도가 걸린다
# - cloudflared가 있으면 그것을, 없으면 설치 없이 되는 ssh 터널(localhost.run)을 쓴다
# - 공개 주소는 터미널에 https://... 꼴로 뜬다. 테스터에게 그 주소를 보낸다
# - 이 PC가 켜져 있는 동안만 열려 있다 (caffeinate가 잠들지 않게 막는다). 주소는 다시 켜면 바뀐다
set -e
cd "$(dirname "$0")/.."
PORT=${PORT:-8503}
export ILITDA_PUBLIC=1
export ILITDA_ALLOWED_DIRS=data/sample,runs/uploads
export ILITDA_MAX_LIVE_CALLS_PER_DAY=${ILITDA_MAX_LIVE_CALLS_PER_DAY:-80}

mkdir -p runs
pkill -f "server.port $PORT" 2>/dev/null || true
.venv/bin/streamlit run src/ilitda/ui/app.py --server.port "$PORT" --server.headless true > runs/_public_ui.log 2>&1 &
UI=$!
caffeinate -i -w $UI &
trap 'kill $UI 2>/dev/null; exit 0' INT TERM
sleep 4
echo "공개 모드 화면이 떴습니다 (내부 주소 http://localhost:$PORT)."
echo "아래에 뜨는 https:// 주소를 테스터에게 보내세요. 끝낼 때는 Ctrl+C."
echo

if command -v cloudflared >/dev/null; then
  cloudflared tunnel --url "http://localhost:$PORT"
else
  # 설치 없이 되는 무료 터널. 느리거나 끊길 수 있다. 끊기면 이 스크립트를 다시 실행한다
  ssh -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes \
      -R 80:localhost:$PORT nokey@localhost.run
fi

#!/bin/bash
# 공개 테스트 링크 감시·자동 재연결.
#   실행: nohup scripts/tunnel_watchdog.sh > runs/_tunnel_watchdog.log 2>&1 &
#   현재 주소: cat runs/_public_url.txt
# - 8503 화면은 건드리지 않고 cloudflared 터널만 연다
# - 1분마다 바깥에서 주소가 열리는지 확인하고, 안 열리면(주소 만료·530) 터널을 다시 연다
# - 주소가 바뀌면 runs/_public_url.txt를 갱신한다
cd "$(dirname "$0")/.."
PORT=${PORT:-8503}
METRICS=${METRICS:-127.0.0.1:20245}
URLFILE=runs/_public_url.txt
mkdir -p runs

start_tunnel() {
  pkill -f "cloudflared tunnel --url http://localhost:$PORT" 2>/dev/null
  sleep 1
  cloudflared tunnel --url "http://localhost:$PORT" --metrics "$METRICS" > runs/_tunnel.log 2>&1 &
  TPID=$!
  for i in $(seq 1 20); do
    sleep 2
    H=$(curl -s -m 3 "http://$METRICS/quicktunnel" | sed -nE 's/.*"hostname":"([^"]+)".*/\1/p')
    [ -n "$H" ] && break
  done
  [ -z "$H" ] && { echo "$(date '+%F %T') 주소를 받지 못함"; return 1; }
  for i in $(seq 1 12); do
    sleep 5
    [ "$(curl -s -o /dev/null -w '%{http_code}' -m 15 "https://$H/")" = "200" ] && break
  done
  echo "https://$H" > "$URLFILE"
  echo "$(date '+%F %T') 새 주소: https://$H"
}

check() {
  H=$(sed 's#https://##' "$URLFILE" 2>/dev/null)
  [ -z "$H" ] && return 1
  kill -0 "$TPID" 2>/dev/null || return 1
  [ "$(curl -s -o /dev/null -w '%{http_code}' -m 20 "https://$H/")" = "200" ]
}

trap 'kill $TPID 2>/dev/null; exit 0' INT TERM
start_tunnel
FAILS=0
while true; do
  sleep 60
  if check; then
    FAILS=0
  else
    FAILS=$((FAILS+1))
    echo "$(date '+%F %T') 접속 실패 $FAILS회"
    if [ $FAILS -ge 2 ]; then   # 일시적 오류는 넘기고, 2분 연속 실패면 재연결
      start_tunnel
      FAILS=0
    fi
  fi
done

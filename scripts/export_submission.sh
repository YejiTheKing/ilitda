#!/bin/bash
# 제출용 소스코드 꾸러미 만들기. 비밀키·실제 자료·개인 기록을 빼고, 가상 자료·저장 응답·시연 실행 로그는 넣는다.
#   실행: scripts/export_submission.sh            → docs/제출물/일잇다_소스코드.zip 과 export/일잇다 폴더(깃허브에 올릴 내용)
set -e
cd "$(dirname "$0")/.."
OUT=export/일잇다
rm -rf export; mkdir -p "$OUT"
rsync -a --exclude '.git' --exclude '.venv' --exclude '__pycache__' --exclude '*.pyc' --exclude '.env' --exclude '.DS_Store' \
  --exclude 'data/real' --exclude 'runs' --exclude 'poc' --exclude 'idea' --exclude 'export' --exclude '.claude' --exclude '*.egg-info' \
  --exclude 'docs/제출물/_근거' --exclude '~$*' --exclude '*_2안.*' --exclude '*.zip' --exclude 'docs/제출물/*.mov' --exclude 'docs/제출물/*.mp4' --exclude 'docs/제출물/04_시연영상_대본.md' \
  --exclude 'docs/제출물/06_사용자검증_확인서.md' --exclude 'docs/제출물/07_제출_체크리스트.md' --exclude 'docs/08_*' --exclude '08_*' --exclude '원문' --exclude 'docs/테스트결과/전후비교_프로토콜.md' \
  ./ "$OUT/"
# 저장 응답(재생용)과 시연 실행 로그만 골라 넣는다
mkdir -p "$OUT/runs/_llm_cache" "$OUT/runs/20261006-045149-4c4a0e"
cp runs/_llm_cache/* "$OUT/runs/_llm_cache/" 2>/dev/null || true
cp runs/20261006-045149-4c4a0e/log.jsonl runs/20261006-045149-4c4a0e/summary.json "$OUT/runs/20261006-045149-4c4a0e/"
.venv/bin/python scripts/filter_cache_for_submission.py "$OUT/runs/_llm_cache"   # 가상 자료 실행분만 남긴다
# README는 제출용 판본으로 바꾼다 (내부 일정·전략 메모 대신 실행·구조 안내)
cp docs/README_제출용.md "$OUT/README.md"; rm -f "$OUT/docs/README_제출용.md"
# 제출 저장소에는 저장 응답(재생용)과 시연 실행 로그가 들어가야 하므로 runs/ 무시 규칙을 지운다
sed -i '' '/^runs\/$/d' "$OUT/.gitignore"
# 비밀키·실제 자료 흔적 검사
KEY="sk-ant"; KEY="$KEY-"
if grep -rIl --exclude=export_submission.sh "$KEY" "$OUT" >/dev/null 2>&1; then echo "!! API 키가 들어 있습니다"; grep -rIl --exclude=export_submission.sh "$KEY" "$OUT"; exit 1; fi
# 실명·회사명 검사: 패턴은 저장소 밖 runs/_private_patterns.txt(한 줄에 하나)에서 읽는다
if [ -f runs/_private_patterns.txt ]; then
  PAT=$(paste -sd'|' runs/_private_patterns.txt)
  HITS=$(grep -rIlE "$PAT" "$OUT" | wc -l | tr -d ' ')
  echo "실명·회사명 검색: ${HITS}건"; [ "$HITS" = "0" ] || { grep -rIlE "$PAT" "$OUT"; exit 1; }
fi
rm -f docs/제출물/일잇다_소스코드.zip
(cd export && zip -qr "../docs/제출물/일잇다_소스코드.zip" "일잇다")
echo "만듦: docs/제출물/일잇다_소스코드.zip ($(du -h docs/제출물/일잇다_소스코드.zip | cut -f1)) · 폴더 $OUT"

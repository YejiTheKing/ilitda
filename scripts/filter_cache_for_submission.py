"""제출 꾸러미의 저장 응답(runs/_llm_cache)에서 가상 자료 실행분만 남긴다.

실명·회사명 같은 비공개 패턴은 저장소 밖 파일(runs/_private_patterns.txt, 한 줄에 하나)에서 읽는다. 코드에는 적지 않는다.
    .venv/bin/python scripts/filter_cache_for_submission.py export/일잇다/runs/_llm_cache
"""
import json, os, re, sys
from pathlib import Path

SAMPLE = re.compile(r"가온정밀|한빛테크|박신입|이대표|견적서 양식|출장비 정산|지출결의서|비품 구매|구매요청서|김신입|박팀장|안팀장|1\+1은")
private = Path(os.environ.get("ILITDA_PRIVATE_PATTERNS", "runs/_private_patterns.txt"))
words = [w.strip() for w in private.read_text(encoding="utf-8").splitlines() if w.strip()] if private.exists() else []
REAL = re.compile("|".join(map(re.escape, words))) if words else None
cache = Path(sys.argv[1])
keep = drop = 0
for f in sorted(cache.glob("*.json")):
    raw = f.read_text(encoding="utf-8")
    d = json.loads(raw)
    body = json.dumps(d.get("user", ""), ensure_ascii=False) + json.dumps(d.get("output", ""), ensure_ascii=False)
    if SAMPLE.search(body) and not (REAL and REAL.search(raw)):
        keep += 1
    else:
        f.unlink(); drop += 1
print(f"저장 응답 유지 {keep} · 제거 {drop}" + ("" if words else " (비공개 패턴 파일 없음: 실명 검사 생략)"))

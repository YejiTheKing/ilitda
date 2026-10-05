"""실행 로그.

에이전트가 어떤 단계에서 어떤 도구를 어떤 순서로 썼는지 남긴다.
한 번의 실행이 runs/<실행 ID>/log.jsonl 파일 하나가 되고, 화면은 이 파일을 읽어 보여준다.
"""
import json
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

RUNS_DIR = Path("runs")

# 로그 종류. 주관사가 확인하는 6요소와 맞춘다.
KINDS = ("goal", "plan", "reasoning", "tool", "memory", "feedback", "human", "error")


class RunLog:
    def __init__(self, run_id=None, root=RUNS_DIR):
        self.run_id = run_id or datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        self.dir = Path(root) / self.run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "log.jsonl"
        existing = self.read()
        self._seq = len(existing)
        # 사람 확인으로 멈췄다가 이어 갈 때 LangGraph는 그 노드를 처음부터 다시 실행한다.
        # 같은 내용이 두 번 적히지 않도록 이미 적은 (종류, 제목, 내용)을 기억한다.
        self._seen = {self._key(e["kind"], e["title"], e.get("detail"),
                                {k: v for k, v in e.items() if k not in ("seq", "time", "kind", "title", "detail", "seconds")})
                      for e in existing}

    @staticmethod
    def _key(kind, title, detail, extra):
        return (kind, title, json.dumps([detail, extra], ensure_ascii=False, sort_keys=True, default=str))

    def add(self, kind, title, detail=None, **extra):
        if kind not in KINDS:
            raise ValueError(f"알 수 없는 로그 종류: {kind}")
        key = self._key(kind, title, detail, {k: v for k, v in extra.items() if k != "seconds"})
        if key in self._seen:
            return None
        self._seen.add(key)
        self._seq += 1
        entry = {
            "seq": self._seq,
            "time": datetime.now().isoformat(timespec="seconds"),
            "kind": kind,
            "title": title,
            "detail": detail,
            **extra,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        return entry

    @contextmanager
    def tool(self, name, **inputs):
        """도구 호출 하나를 기록한다. 결과 요약은 call["result"]에 넣는다."""
        call = {"result": None}
        started = time.perf_counter()
        try:
            yield call
        except Exception as e:
            self.add("error", f"{name} 실패", str(e), tool=name, inputs=inputs,
                     seconds=round(time.perf_counter() - started, 3))
            raise
        self.add("tool", name, call["result"], tool=name, inputs=inputs,
                 seconds=round(time.perf_counter() - started, 3))

    def summarize(self, **fields):
        """실행 폴더에 요약(summary.json)을 남긴다. 목록에서 무슨 실행인지 알아보기 위한 것."""
        path = self.dir / "summary.json"
        data = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                data = {}
        data.update({k: v for k, v in fields.items() if v is not None})
        data["updated"] = datetime.now().isoformat(timespec="seconds")
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        return data

    def summary(self):
        path = self.dir / "summary.json"
        try:
            return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except ValueError:
            return {}

    def read(self):
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

"""기억 저장소.

책임자의 답변을 저장해 두고, 다음 실행에서 같은 질문을 다시 하지 않는다.
실행 상태 자체는 LangGraph 체크포인트가 저장하고, 여기는 실행을 넘어 남는 지식만 둔다.
"""
import re
import sqlite3
from difflib import SequenceMatcher
from datetime import datetime
from pathlib import Path

DB_PATH = Path("runs/memory.sqlite")


def _norm(s):
    return re.sub(r"[\s?？.。,]", "", s).lower()


class Memory:
    def __init__(self, path=DB_PATH):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)   # 화면이 에이전트를 다른 스레드에서 돌린다
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS answers (task TEXT, topic_key TEXT, topic TEXT, question TEXT, "
            "answer TEXT, answered_by TEXT, answered_at TEXT, PRIMARY KEY (task, topic_key))"
        )
        self.conn.commit()

    def recall(self, task, topic, question=""):
        """같은 업무에서 같은 주제의 답을 찾는다.

        LLM이 실행마다 주제 문구를 조금씩 다르게 쓰므로, 정확히 같은 키가 없으면
        주제나 질문이 충분히 비슷한 기록을 찾는다. 비슷한 정도(similarity)도 함께 돌려준다.
        """
        cols = ("topic", "question", "answer", "answered_by", "answered_at")
        row = self.conn.execute(
            f"SELECT {', '.join(cols)} FROM answers WHERE task=? AND topic_key=?", (task, _norm(topic)),
        ).fetchone()
        if row:
            return dict(zip(cols, row)) | {"similarity": 1.0}
        best, best_score = None, 0.0
        # 업무 이름도 실행마다 조금씩 다를 수 있다("AS 접수부터 처리보고서 작성까지" / "AS 접수부터 수리 견적과 ...").
        # 업무 이름이 충분히 비슷한 기록까지 후보로 본다
        for r in self.conn.execute(f"SELECT task, {', '.join(cols)} FROM answers"):
            rec_task, rec = r[0], dict(zip(cols, r[1:]))
            if rec_task != task and SequenceMatcher(None, _norm(rec_task), _norm(task)).ratio() < 0.6:
                continue
            score = max(
                SequenceMatcher(None, _norm(topic), _norm(rec["topic"])).ratio(),
                SequenceMatcher(None, _norm(question), _norm(rec["question"])).ratio() if question else 0.0,
            )
            if score > best_score:
                best, best_score = rec, score
        if best and best_score >= 0.6:
            return best | {"similarity": round(best_score, 2)}
        return None

    def remember(self, task, topic, question, answer, answered_by):
        self.conn.execute(
            "INSERT OR REPLACE INTO answers VALUES (?,?,?,?,?,?,?)",
            (task, _norm(topic), topic, question, answer, answered_by, datetime.now().isoformat(timespec="seconds")),
        )
        self.conn.commit()

    def all_for(self, task):
        rows = self.conn.execute("SELECT topic, question, answer FROM answers WHERE task=?", (task,)).fetchall()
        return [dict(zip(("topic", "question", "answer"), r)) for r in rows]

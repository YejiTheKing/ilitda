"""그래프 실행 도우미. 멈춤(interrupt)이 생기면 호출자에게 돌려주고, 답을 받아 이어 간다."""
from langgraph.types import Command

from ilitda.agent.graph import build_graph, open_checkpointer
from ilitda.llm.client import LLM, LLMError
from ilitda.memory.store import Memory
from ilitda.runlog import RunLog


class Runner:
    def __init__(self, run_id=None, llm_mode=None, checkpoint_path="runs/checkpoints.sqlite", memory_path=None):
        self.log = RunLog(run_id)
        self.llm = LLM(self.log, mode=llm_mode)
        self.memory = Memory(memory_path) if memory_path else Memory()
        self._cp_cm = open_checkpointer(checkpoint_path)
        self.checkpointer = self._cp_cm.__enter__()
        self.graph = build_graph(self.log, self.llm, self.memory, self.checkpointer)
        self.config = {"configurable": {"thread_id": self.log.run_id}}

    def close(self):
        self._cp_cm.__exit__(None, None, None)

    def _pending(self):
        snap = self.graph.get_state(self.config)
        for task in snap.tasks:
            if task.interrupts:
                return task.interrupts[0].value
        return None

    def _invoke(self, payload):
        try:
            self.graph.invoke(payload, self.config)
        except LLMError as e:
            # 재시도와 기록 재생까지 실패한 경우. 상태는 체크포인트에 남아 있어 나중에 같은 자리에서 다시 시도할 수 있다
            self.log.add("error", "LLM 호출 실패로 중단", str(e))
            return {"type": "error", "message": f"AI 호출에 실패해 멈췄습니다: {e}. 네트워크와 API 키를 확인한 뒤 다시 시도하세요. 진행 상태는 저장되어 있습니다."}
        except (PermissionError, NotADirectoryError, FileNotFoundError) as e:
            self.log.add("error", "자료 폴더 접근 실패", str(e))
            return {"type": "error", "message": f"자료 폴더를 읽을 수 없습니다: {e}"}
        return self._pending()

    def start(self, goal_text, folder):
        """실행을 시작한다. 멈추면 멈춘 이유(dict)를, 끝나면 None을 돌려준다."""
        return self._invoke({"run_id": self.log.run_id, "goal_text": goal_text, "folder": folder})

    def resume(self, reply):
        """멈춘 자리에 답을 넣고 이어 간다.

        빈 답({}, "", None)을 그대로 넘기면 LangGraph가 답이 없는 것으로 보고 같은 자리에서 다시 멈춘다.
        그래서 빈 답은 '답 없음' 표시가 든 값으로 바꿔 보낸다.
        """
        if not reply:
            reply = {"__empty__": True} if isinstance(reply, dict) or reply is None else " "
        return self._invoke(Command(resume=reply))

    def retry(self):
        """오류로 멈춘 자리에서 다시 시도한다."""
        return self._invoke(None)

    def state(self):
        return self.graph.get_state(self.config).values

"""에이전트 흐름.

목표 해석 → 계획 → 자료 읽기 → 버전 정리 → 절차 복원·검증 → 책임자 확인(멈춤) → 체크리스트
→ 신규자 첫 업무 진행(멈춤) → 책임자 승인(멈춤) → 인계 완료. 승인이 보류되면 신규자 진행으로 돌아가 보완한 뒤 다시 승인을 요청한다.

사람에게 물어야 할 때는 interrupt()로 실행을 멈추고, 답을 받으면 같은 자리에서 이어 간다.
"""
import os
from typing import Any, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from ilitda.llm import tasks
from ilitda.llm.client import LLM, LLMError
from ilitda.memory.store import Memory
from ilitda.runlog import RunLog
from ilitda.tools.evidence import verify_evidence
from ilitda.tools.ingest import ingest
from ilitda.tools.scan import scan_folder
from ilitda.tools.versions import diff_versions, group_versions, pick_latest

MAX_EXTRACT_RETRY = 2


class State(TypedDict, total=False):
    run_id: str
    goal_text: str
    folder: str
    goal: dict
    plan: dict
    inventory: list
    documents: list
    unreadable: list
    versions: list        # 계열별 최신본 판별 결과
    changes: list         # 유형이 붙은 변경점
    steps: list           # 근거 검증을 거친 절차
    questions: list       # 책임자에게 물을 것 [{topic, question, kind, claims}]
    answers: list         # [{topic, question, answer, source}]
    checklist: list
    progress: dict        # {item order: {"done": bool, "note": str}}
    approval: dict
    hold_count: int       # 책임자가 보류한 횟수. 되돌아온 라운드의 로그가 중복 제거에 걸리지 않게 구분하는 데 쓴다
    status: str
    metrics: dict


# ---------- 노드 ----------

class Nodes:
    """노드가 공유하는 자원(로그, LLM, 기억)을 묶는다."""

    def __init__(self, log: RunLog, llm: LLM, memory: Memory):
        self.log, self.llm, self.memory = log, llm, memory

    ESSENTIAL = ("task", "newcomer")   # 이것만 꼭 있어야 한다. 책임자·완료 조건은 기본값으로 채울 수 있다

    def read_goal(self, state: State):
        goal = tasks.parse_goal(self.llm, state["goal_text"])
        text = state["goal_text"]
        for attempt in range(2):   # 되물음은 최대 2회. 무한 반복과 호출 낭비를 막는다
            missing = [m for m in goal["missing"] if m in self.ESSENTIAL]
            if not missing:
                break
            self.log.add("goal", "목표에 빠진 항목이 있어 되물음", missing)
            extra = interrupt({"type": "clarify_goal", "question": goal["clarifying_question"], "missing": missing})
            if isinstance(extra, dict) or not str(extra or "").strip():
                break
            text = text + "\n추가 정보: " + str(extra)
            goal = tasks.parse_goal(self.llm, text)
        goal = dict(goal)
        if not goal.get("owner"):
            goal["owner"] = "책임자"
        if not goal.get("done_when"):
            goal["done_when"] = f"{goal.get('newcomer') or '신규자'}가 '{goal.get('task') or '해당 업무'}'를 혼자 끝까지 수행함"
        if not goal.get("task"):
            goal["task"] = state["goal_text"].strip()[:40]
        if not goal.get("newcomer"):
            goal["newcomer"] = "신규자"
        self.log.add("goal", f"목표 해석: 업무 '{goal['task']}', 신규자 {goal['newcomer']}, 책임자 {goal['owner']}", goal["done_when"])
        folder = state.get("folder", "")
        source = "업로드" if "uploads" in folder else ("실제" if "real" in folder else "가상")
        self.log.summarize(task=goal["task"], newcomer=goal["newcomer"], owner=goal["owner"], folder=folder,
                           source=source, public=os.environ.get("ILITDA_PUBLIC") == "1", status="goal")
        return {"goal": goal, "status": "goal"}

    def plan(self, state: State):
        inventory = scan_folder(state["folder"])
        plan = tasks.make_plan(self.llm, state["goal"], inventory)
        self.log.add("plan", f"계획 {len(plan['steps'])}단계", [f"{s['id']} {s['tool']}: {s['action']}" for s in plan["steps"]],
                     notes=plan["notes"])
        return {"inventory": inventory, "plan": plan, "status": "planned"}

    def read_documents(self, state: State):
        result = ingest(state["folder"], self.log)
        if not result["documents"]:
            self.log.add("error", "읽을 수 있는 자료가 없음", result["unreadable"])
            self.log.summarize(status="no_documents", documents=0)
            return {"documents": [], "unreadable": result["unreadable"], "status": "no_documents"}
        return {"documents": result["documents"], "unreadable": result["unreadable"], "status": "read"}

    def sort_versions(self, state: State):
        docs = state["documents"]
        with self.log.tool("group_versions", documents=len(docs)) as call:
            families = group_versions(docs)
            call["result"] = f"계열 {len(families)}개"
        versions, changes, questions = [], [], []
        for fam in families:
            if len(fam["members"]) < 2:
                continue
            with self.log.tool("pick_latest", family=[m["name"] for m in fam["members"]]) as call:
                picked = pick_latest(fam)
                call["result"] = f"최신본 {picked['latest']['name']} / " + "; ".join(picked["evidence"])
            self.log.add("reasoning", f"'{picked['latest']['name']}'을 최신본으로 선택", picked["evidence"])
            versions.append({"family": [m["name"] for m in fam["members"]], "latest": picked["latest"]["name"],
                             "evidence": picked["evidence"], "confident": picked["confident"]})
            if not picked["confident"]:
                questions.append({"kind": "version", "topic": f"최신본: {picked['latest']['name']}",
                                  "question": f"'{'·'.join(m['name'] for m in fam['members'])}' 중 어느 것이 최신본입니까?",
                                  "claims": []})
                continue
            for old in picked["ranked"][1:]:
                with self.log.tool("diff_versions", old=old["name"], new=picked["latest"]["name"]) as call:
                    diff = diff_versions(old, picked["latest"])
                    call["result"] = f"변경 {len(diff)}건"
                if not diff:
                    continue
                classified = tasks.classify_changes(self.llm, picked["latest"]["name"], diff)
                for c in classified:
                    raw = diff[c["index"]] if 0 <= c["index"] < len(diff) else {}
                    changes.append(c | {"family": picked["latest"]["name"], "old_doc": old["name"], "field": raw.get("field"),
                                        "old": raw.get("old"), "new": raw.get("new")})
        important = [c for c in changes if c.get("matters")]
        self.log.add("feedback", f"업무에 영향 있는 변경점 {len(important)}건 (전체 {len(changes)}건)",
                     [f"[{c['type']}] {c['summary']}" for c in important])
        return {"versions": versions, "changes": changes, "questions": state.get("questions", []) + questions, "status": "versions"}

    def restore_procedure(self, state: State):
        docs = state["documents"]
        # 구버전 양식은 절차 복원에서 제외한다. 최신본만 넘겨 혼선을 줄인다
        old_names = {n for v in state["versions"] for n in v["family"] if n != v["latest"]}
        latest_docs = [d for d in docs if d["name"] not in old_names]
        latest_names = [v["latest"] for v in state["versions"]]
        self.log.add("reasoning", f"절차 복원에 최신 자료 {len(latest_docs)}개 사용, 구버전 {len(old_names)}개 제외", sorted(old_names))
        masked = tasks.masked_counts(latest_docs)
        if masked:
            self.log.add("feedback", f"LLM 전송 전 개인정보 형식 {sum(masked.values())}건 가림", masked)

        steps, proc = [], None
        for attempt in range(1, MAX_EXTRACT_RETRY + 2):
            proc = tasks.extract_procedure(self.llm, state["goal"], latest_docs, latest_names)
            with self.log.tool("verify_evidence", steps=len(proc["steps"])) as call:
                steps = verify_evidence(proc["steps"], docs)
                bad = [s for s in steps if s["status"] != "ok"]
                call["result"] = f"근거 확인 {len(steps) - len(bad)}/{len(steps)}"
            if not bad or attempt > MAX_EXTRACT_RETRY:
                break
            self.log.add("feedback", f"근거를 찾지 못한 단계 {len(bad)}개, 다시 추출 ({attempt}/{MAX_EXTRACT_RETRY})",
                         [s["action"] for s in bad])

        questions = list(state.get("questions", []))
        for c in proc["conflicts"]:
            questions.append({"kind": "conflict", "topic": c["topic"], "question": c["question"], "claims": c["claims"]})
        for g in proc["gaps"]:
            questions.append({"kind": "gap", "topic": g["topic"], "question": g["question"], "claims": [], "why": g["why"]})
        for s in steps:
            if s["status"] != "ok":
                questions.append({"kind": "unverified", "topic": f"단계: {s['action']}",
                                  "question": f"'{s['action']}' 단계가 실제 절차에 있습니까? 자료에서 근거를 찾지 못했습니다.", "claims": []})
        self.log.add("feedback", f"절차 {len(steps)}단계, 충돌 {len(proc['conflicts'])}건, 빈틈 {len(proc['gaps'])}건, 근거 미확인 {sum(s['status'] != 'ok' for s in steps)}건")
        self.log.summarize(steps=len(steps), questions=len(questions), documents=len(docs), status="procedure")
        return {"steps": steps, "questions": questions, "status": "procedure"}

    def ask_owner(self, state: State):
        task = state["goal"]["task"]
        pending, answers, suggested = [], list(state.get("answers", [])), 0
        for q in state["questions"]:
            known = self.memory.recall(task, q["topic"], q["question"])
            if known:
                # 자동으로 답하지 않는다. 책임자가 보고 확인하거나 고치도록 답변 칸에 미리 채워 제안만 한다
                q = {**q, "suggested": known["answer"], "suggested_from": known["topic"]}
                suggested += 1
                self.log.add("memory", f"이전 답변 제안: {q['topic']}",
                             f"{known['answer']} (저장된 주제 '{known['topic']}', 유사도 {known['similarity']}) — 책임자가 확인한 뒤에만 반영")
            pending.append(q)
        # 질문이 없어도 책임자가 복원된 절차를 검토·수정할 수 있도록 여기서 한 번 멈춘다
        self.log.add("human", f"책임자 확인 요청 {len(pending)}건" + (f"(이전 답변 제안 {suggested}건 포함)" if suggested else "") + "과 절차 검토, 실행 멈춤",
                     [q["question"] for q in pending])
        # 답변 형식: {질문 topic: 답변 문자열, "__steps__": {"edits": {단계 번호: 바뀐 문장}, "remove": [단계 번호]}}
        replies = interrupt({"type": "ask_owner", "owner": state["goal"]["owner"], "questions": pending,
                             "steps": [{k: v for k, v in s_.items() if k != "evidence"} for s_ in state["steps"]]})
        replies = {k: v for k, v in (replies or {}).items() if k != "__empty__"}
        remember = bool(replies.pop("__remember__", False))   # 책임자가 '저장'을 켠 경우에만 다음 인계 제안용으로 기억한다
        for q in pending:
            reply = _lookup_reply({k: v for k, v in replies.items() if k != "__steps__"}, q["topic"]).strip()
            if reply:
                accepted = bool(q.get("suggested")) and reply == q["suggested"]
                answers.append({"topic": q["topic"], "question": q["question"], "answer": reply, "source": "owner", "from_suggestion": accepted})
                if accepted:
                    self.log.add("memory", f"이전 답변 확인: {q['topic']}", reply)
                elif remember:
                    self.memory.remember(task, q["topic"], q["question"], reply, state["goal"]["owner"])
                    self.log.add("memory", f"답변 저장: {q['topic']}", reply)
                else:
                    self.log.add("human", f"책임자 답변: {q['topic']}", reply)
            else:
                answers.append({"topic": q["topic"], "question": q["question"], "answer": "", "source": "unresolved"})
                self.log.add("human", f"미확정으로 표시: {q['topic']}")

        steps = _apply_step_edits(state["steps"], replies.get("__steps__") or {}, state["goal"]["owner"], self.log)
        self.log.summarize(status="answered", answered=sum(1 for a in answers if a["source"] == "owner"),
                           unresolved=sum(1 for a in answers if a["source"] == "unresolved"))
        return {"answers": answers, "steps": steps, "status": "answered"}


    def make_checklist(self, state: State):
        answered = [a for a in state["answers"] if a["answer"]]
        unresolved = [a for a in state["answers"] if not a["answer"]]
        confirmed_steps = [s for s in state["steps"] if s["status"] == "ok"]
        items = tasks.build_checklist(self.llm, state["goal"], confirmed_steps, answered)
        for a in unresolved:
            items.append({"order": len(items) + 1, "text": f"[미확정] {a['topic']} — 책임자도 확인하지 못함. 수행 전 다시 확인",
                          "how_to_verify": "책임자 확인 후 진행", "required": False})
        self.log.add("tool", "build_checklist", f"항목 {len(items)}개 (미확정 {len(unresolved)}개)", tool="build_checklist")
        return {"checklist": items, "progress": {}, "status": "checklist"}

    def handover(self, state: State):
        progress = dict(state.get("progress", {}))
        # 책임자가 승인을 보류해 되돌아온 경우. 남은 필수 항목이 없어도 한 번은 신규자에게 보완할 기회를 준다
        held = (state.get("approval") or {}).get("approved") is False
        hold_note = (state.get("approval") or {}).get("note", "") if held else ""
        rounds = 0
        while True:
            rounds += 1
            todo = [i for i in state["checklist"] if i["required"] and not progress.get(str(i["order"]), {}).get("done")]
            if not todo and not (held and rounds == 1):
                break
            self.log.add("human", f"신규자 수행 확인 요청 (남은 필수 항목 {len(todo)}개)" + (" — 책임자 보류 후 보완" if held else ""),
                         [i["text"] for i in todo], attempt=state.get("hold_count", 0))
            # 신규자가 수행한 항목을 표시한다. 형식: {항목 번호: {"done": bool, "note": str}}
            update = interrupt({"type": "newcomer_progress", "newcomer": state["goal"]["newcomer"],
                                "checklist": state["checklist"], "progress": progress, "hold_note": hold_note})
            for k, v in (update or {}).items():
                progress[str(k)] = {"done": bool(v.get("done")), "note": v.get("note", "")}
            still = [i for i in state["checklist"] if i["required"] and not progress.get(str(i["order"]), {}).get("done")]
            if still and update is not None and not any(v.get("done") for v in update.values()):
                self.log.add("tool", "notify_owner", f"진행 없음, 책임자에게 미완료 {len(still)}건 알림", tool="notify_owner")
                break
        done = sum(1 for i in state["checklist"] if progress.get(str(i["order"]), {}).get("done"))
        self.log.add("feedback", f"체크리스트 {done}/{len(state['checklist'])} 완료", attempt=state.get("hold_count", 0))
        self.log.summarize(status="handover", checklist=f"{done}/{len(state['checklist'])}")
        return {"progress": progress, "status": "handover"}

    def approve(self, state: State):
        todo = [i for i in state["checklist"] if i["required"] and not state["progress"].get(str(i["order"]), {}).get("done")]
        self.log.add("tool", "notify_owner", f"책임자 승인 요청 (미완료 필수 항목 {len(todo)}개)", tool="notify_owner",
                     attempt=state.get("hold_count", 0))
        decision = interrupt({"type": "owner_approval", "owner": state["goal"]["owner"], "incomplete": todo,
                              "checklist": state["checklist"], "progress": state["progress"]})
        approved = bool((decision or {}).get("approved")) and not todo
        self.log.add("human", "책임자 승인" if approved else "승인 보류", (decision or {}).get("note", ""), attempt=state.get("hold_count", 0))
        metrics = {
            "steps": len(state["steps"]),
            "steps_with_evidence": sum(1 for s in state["steps"] if s["status"] == "ok"),
            "questions": len(state["questions"]),
            "answered_by_owner": sum(1 for a in state["answers"] if a["source"] == "owner"),
            "answered_from_memory": sum(1 for a in state["answers"] if a["source"] == "memory" or a.get("from_suggestion")),
            "unresolved": sum(1 for a in state["answers"] if a["source"] == "unresolved"),
            "changes_that_matter": sum(1 for c in state["changes"] if c.get("matters")),
            "checklist_done": sum(1 for i in state["checklist"] if state["progress"].get(str(i["order"]), {}).get("done")),
            "checklist_total": len(state["checklist"]),
            "llm_calls": self.llm.calls, "llm_replays": self.llm.replays, "llm_usage": self.llm.usage,
        }
        status = "completed" if approved else "pending_approval"
        self.log.add("feedback", "인계 완료 판정" if approved else "인계 미완료", metrics, attempt=state.get("hold_count", 0))
        self.log.summarize(status=status, answered=metrics["answered_by_owner"], unresolved=metrics["unresolved"],
                           checklist=f"{metrics['checklist_done']}/{metrics['checklist_total']}")
        return {"approval": decision or {}, "metrics": metrics, "status": status,
                "hold_count": state.get("hold_count", 0) + (0 if approved else 1)}


def _apply_step_edits(steps, edits, owner, log):
    """책임자가 고치거나 빼거나 더한 단계를 반영한다. 고치거나 더한 단계는 근거가 '책임자 확인'이 된다.

    edits: {"edits": {단계 번호: 바뀐 문장}, "remove": [단계 번호], "add": [{"after": 단계 번호, "action": 문장, "who": 담당}]}
    """
    changed = {str(k): str(v).strip() for k, v in (edits.get("edits") or {}).items() if str(v).strip()}
    removed = {str(k) for k in (edits.get("remove") or [])}
    added = {}
    for a in edits.get("add") or []:
        if str(a.get("action", "")).strip():
            added.setdefault(str(a.get("after", 0)), []).append(a)

    def owner_step(action, who=""):
        return {"order": 0, "action": action, "who": who or "", "form": "", "confidence": "높음", "status": "ok",
                "edited_by": owner, "evidence": [{"doc": "책임자 확인", "quote": action, "found": True, "ratio": 1.0, "why": ""}]}

    out = [owner_step(a["action"], a.get("who")) for a in added.get("0", [])]
    for s in steps:
        key = str(s["order"])
        if key in removed:
            log.add("human", f"책임자가 단계 삭제: {s['action']}")
            continue
        if key in changed and changed[key] != s["action"]:
            log.add("human", f"책임자가 단계 수정: {s['action']} → {changed[key]}")
            s = s | {"action": changed[key], "status": "ok", "edited_by": owner,
                     "evidence": [{"doc": "책임자 확인", "quote": changed[key], "found": True, "ratio": 1.0, "why": ""}]}
        out.append(s)
        for a in added.get(key, []):
            log.add("human", f"책임자가 {key}번 뒤에 단계 추가: {a['action']}")
            out.append(owner_step(a["action"], a.get("who")))
    for i, s in enumerate(out, 1):
        s["order"] = i
    return out


def _lookup_reply(replies, topic):
    """답변 사전에서 topic에 해당하는 답을 찾는다. 정확히 같은 키가 없으면 서로 포함하는 키를 쓴다."""
    if topic in replies:
        return str(replies[topic])
    key = topic.replace(" ", "")
    for k, v in replies.items():
        kk = k.replace(" ", "")
        if kk and (kk in key or key in kk):
            return str(v)
    return ""


def after_read(state: State):
    return END if state.get("status") == "no_documents" else "sort_versions"


def after_approve(state: State):
    """승인이면 끝. 보류면 신규자 수행 단계로 돌려보내 보완한 뒤 다시 승인을 요청하게 한다."""
    return END if state.get("status") == "completed" else "handover"


def build_graph(log: RunLog, llm: LLM, memory: Memory, checkpointer=None):
    n = Nodes(log, llm, memory)
    g = StateGraph(State)
    g.add_node("read_goal", n.read_goal)
    g.add_node("plan", n.plan)
    g.add_node("read_documents", n.read_documents)
    g.add_node("sort_versions", n.sort_versions)
    g.add_node("restore_procedure", n.restore_procedure)
    g.add_node("ask_owner", n.ask_owner)
    g.add_node("make_checklist", n.make_checklist)
    g.add_node("handover", n.handover)
    g.add_node("approve", n.approve)
    g.add_edge(START, "read_goal")
    g.add_edge("read_goal", "plan")
    g.add_edge("plan", "read_documents")
    g.add_conditional_edges("read_documents", after_read, {"sort_versions": "sort_versions", END: END})
    g.add_edge("sort_versions", "restore_procedure")
    g.add_edge("restore_procedure", "ask_owner")
    g.add_edge("ask_owner", "make_checklist")
    g.add_edge("make_checklist", "handover")
    g.add_edge("handover", "approve")
    g.add_conditional_edges("approve", after_approve, {"handover": "handover", END: END})
    return g.compile(checkpointer=checkpointer)


def open_checkpointer(path="runs/checkpoints.sqlite"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return SqliteSaver.from_conn_string(path)

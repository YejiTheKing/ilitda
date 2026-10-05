"""확인 요청함: 책임자가 확인 질문에 답하고(근거 함께), 복원 절차를 고치고, 인계 완료를 승인한다.

답변은 입력할 때마다 임시 파일에 저장되어 화면을 옮기거나 연결이 끊겨도 남는다.
"""
import json
from datetime import datetime

import streamlit as st

from ilitda.runlog import RUNS_DIR
from ilitda.ui import components as ui
from ilitda.ui import session
from ilitda.ui.session import QUESTION_KIND

WHY = {"conflict": "자료끼리 내용이 다릅니다.", "gap": "자료 어디에도 없는 내용입니다.",
       "version": "어느 파일이 최신본인지 가릴 근거가 부족합니다.", "unverified": "근거 문장이 원문에 없습니다."}
TONE = {"conflict": "warn", "gap": "info", "version": "warn", "unverified": "danger"}
SOURCE = {"owner": ("책임자 답변", "ok"), "memory": ("이전 답변 확인", "info"), "unresolved": ("미확정", "warn")}


def render():
    runner, state, pending = session.current()
    if not runner:
        st.html('<div class="il-title">확인 요청함</div>')
        ui.empty_state("진행 중인 인계가 없습니다", "인계를 시작하면 자료만으로 정할 수 없는 항목이 여기에 질문으로 쌓입니다.")
        if st.button("인계 시작", type="primary", key="o-start"):
            session.goto("start")
        return
    goal = state.get("goal") or {}
    info = ui.page_header(state, pending, meta=[("책임자", goal.get("owner")), ("신규자", goal.get("newcomer")), ("실행 ID", runner.log.run_id)])
    kind = pending["type"] if pending else None
    if kind == "error":
        ui.error_panel(pending)
    elif kind == "ask_owner":
        render_ask_owner(runner, state, pending)
    elif kind == "owner_approval":
        render_approval(runner, state, pending)
    else:
        render_history(state, pending)
    ui.page_actions(info, pending)


# ---------- 확인 질문 ----------

def claims_html(q, docs_by_name):
    parts = []
    for c in q.get("claims", []):
        loc = ui.locate(docs_by_name.get(c.get("doc", ""), ""), c.get("quote", ""))
        where = f"원문 {loc['line']}행" if loc else "원문 위치 확인 불가"
        parts.append(f'<div class="il-ev ok"><span class="doc">{ui.esc(c.get("doc", ""))}</span> {ui.chip(where, "gray")}'
                     f'<div class="il-small">{ui.esc(c.get("says", ""))}</div><q>{ui.esc(c.get("quote", ""))}</q></div>')
    return "".join(parts)


def render_ask_owner(runner, state, pending):
    qs = pending["questions"]
    steps_ = pending.get("steps", [])
    rid = runner.log.run_id
    draft_path = RUNS_DIR / rid / "draft_answers.json"
    docs_by_name = ui.docs_map(state)

    def save_draft():
        d = {"answers": {q["topic"]: st.session_state.get(f"ans_{rid}_{i}", "") for i, q in enumerate(qs, 1)},
             "edits": {str(s_["order"]): st.session_state.get(f"edit_{rid}_{s_['order']}", s_["action"]) for s_ in steps_},
             "remove": [str(s_["order"]) for s_ in steps_ if st.session_state.get(f"rm_{rid}_{s_['order']}")],
             "add": [{"after": int(st.session_state.get(f"addafter_{rid}_{n}", 0)), "action": st.session_state.get(f"addtext_{rid}_{n}", "")} for n in range(1, 4)],
             "saved_at": datetime.now().isoformat(timespec="seconds")}
        draft_path.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")

    first_key = f"ans_{rid}_1" if qs else (f"edit_{rid}_{steps_[0]['order']}" if steps_ else None)
    if first_key and first_key not in st.session_state and draft_path.exists():
        # 위젯이 아직 없다(새 세션). 임시 저장 파일에서 되살린다
        try:
            d = json.loads(draft_path.read_text(encoding="utf-8"))
        except ValueError:
            d = {}
        for i, q in enumerate(qs, 1):
            st.session_state[f"ans_{rid}_{i}"] = d.get("answers", {}).get(q["topic"], "")
        for s_ in steps_:
            st.session_state[f"edit_{rid}_{s_['order']}"] = d.get("edits", {}).get(str(s_["order"]), s_["action"])
            st.session_state[f"rm_{rid}_{s_['order']}"] = str(s_["order"]) in d.get("remove", [])
        for n, a in enumerate(d.get("add", []), 1):
            st.session_state[f"addafter_{rid}_{n}"] = int(a.get("after", 0))
            st.session_state[f"addtext_{rid}_{n}"] = a.get("action", "")

    for i, q in enumerate(qs, 1):
        # 이전 인계에서 받은 답은 미리 채워 두고 책임자가 확인·수정한다 (자동 반영 없음). 이미 쓰던 칸은 건드리지 않는다
        if q.get("suggested") and f"ans_{rid}_{i}" not in st.session_state:
            st.session_state[f"ans_{rid}_{i}"] = q["suggested"]
    answered = sum(1 for i in range(1, len(qs) + 1) if st.session_state.get(f"ans_{rid}_{i}", "").strip())
    facts = session.sample_facts(state)
    with ui.card("owner-q"):
        ui.section(f"확인 질문 {len(qs)}건", ui.chip(f"답변 {answered}/{len(qs)}", "ok" if qs and answered == len(qs) else "gray") if qs else "")
        if facts:
            with st.expander("이대표가 아는 사실 (정답 메모) — 가상 자료 테스트에서는 이 표를 보고 답하세요", expanded=True):
                st.markdown(facts)
        if not qs:
            ui.empty_state("물어볼 항목이 없습니다", "아래에서 절차만 검토하고 보내면 됩니다.")
        for i, q in enumerate(qs, 1):
            kind = q.get("kind", "")
            st.html(f'<div class="il-row {"first" if i == 1 and not facts else ""}"><div class="il-num {TONE.get(kind, "")}">{i}</div><div class="il-body">'
                    f'<div class="il-main">{ui.esc(q["question"])}</div>'
                    f'<div class="il-meta">{ui.chip(QUESTION_KIND.get(kind, kind), TONE.get(kind, ""))} {ui.esc(q.get("why") or WHY.get(kind, ""))}'
                    f'{" " + ui.chip("이전 답변 제안", "info") + " 지난 인계의 답을 미리 채웠습니다. 맞으면 그대로, 아니면 고쳐 주세요." if q.get("suggested") else ""}</div>'
                    f'{claims_html(q, docs_by_name)}</div></div>')
            st.text_area("답변", key=f"ans_{rid}_{i}", label_visibility="collapsed", height=72, on_change=save_draft, persist_state="session",
                         placeholder="답변. 모르면 비워 두세요 (미확정으로 남습니다)")

    with ui.card("owner-steps"):
        with st.expander(f"복원된 절차 검토·수정 ({len(steps_)}단계)", expanded=not qs):
            st.caption("틀린 문장은 고치고, 없어야 할 단계는 '삭제'에 표시, 빠진 단계는 '단계 추가'에 적습니다. 고치거나 더한 단계는 근거가 '책임자 확인'이 됩니다.")
            for s_ in steps_:
                c1, c2 = st.columns([6, 1], vertical_alignment="bottom")
                flag = "" if s_["status"] == "ok" else " ⚠ 근거 미확인"
                if f"edit_{rid}_{s_['order']}" not in st.session_state:
                    st.session_state[f"edit_{rid}_{s_['order']}"] = s_["action"]
                c1.text_input(f"{s_['order']}.{flag}", key=f"edit_{rid}_{s_['order']}", on_change=save_draft, persist_state="session")
                c2.checkbox("삭제", key=f"rm_{rid}_{s_['order']}", on_change=save_draft, persist_state="session")
            st.markdown("**단계 추가** (자료에 없어서 에이전트가 만들지 않은 단계)")
            for n in range(1, 4):
                c1, c2 = st.columns([1, 5], vertical_alignment="bottom")
                c1.number_input("몇 번 뒤에", min_value=0, max_value=len(steps_), key=f"addafter_{rid}_{n}", help="0이면 맨 앞", on_change=save_draft, persist_state="session")
                c2.text_input(f"추가할 단계 {n}", key=f"addtext_{rid}_{n}", placeholder="예: 직접 수리 가능하면 현장에서 수리하고 납품한다", on_change=save_draft, persist_state="session")

    saved = ""
    if draft_path.exists():
        try:
            saved = json.loads(draft_path.read_text(encoding="utf-8")).get("saved_at", "")[11:19]
        except ValueError:
            saved = ""
    remember = st.checkbox("답변을 저장해 다음 인계 때 제안으로 보여 주기", value=False, key=f"remember_{rid}",
                           help="끄면 답변은 이 실행에만 쓰이고 어디에도 남지 않습니다.") if qs else False
    with st.container(horizontal=True, gap="small", vertical_alignment="center"):
        if ui.busy_button("답변 보내기" if qs else "검토 완료 · 체크리스트 만들기", "answers_send", type="primary", icon=":material/send:"):
            save_draft()
            replies = {q["topic"]: st.session_state.get(f"ans_{rid}_{i}", "") for i, q in enumerate(qs, 1)}
            replies["__remember__"] = bool(remember)
            edits = {str(s_["order"]): st.session_state.get(f"edit_{rid}_{s_['order']}", s_["action"]) for s_ in steps_
                     if st.session_state.get(f"edit_{rid}_{s_['order']}", s_["action"]) != s_["action"]}
            remove = [str(s_["order"]) for s_ in steps_ if st.session_state.get(f"rm_{rid}_{s_['order']}")]
            add = [{"after": int(st.session_state.get(f"addafter_{rid}_{n}", 0)), "action": st.session_state.get(f"addtext_{rid}_{n}", "").strip()}
                   for n in range(1, 4) if st.session_state.get(f"addtext_{rid}_{n}", "").strip()]
            replies["__steps__"] = {"edits": edits, "remove": remove, "add": add}
            if draft_path.exists():
                draft_path.unlink()
            st.session_state["_goto"] = "newcomer"
            session.run_and_wait(lambda: runner.resume(replies), "답변을 반영해 절차를 정리하고 체크리스트를 만드는 중…")
        st.caption((f"비운 {len(qs) - answered}건은 미확정으로 보냅니다." if qs else "절차 수정 내용만 반영합니다.") + (f" · 입력 중인 내용은 이 실행 안에서만 임시 보관 ({saved})" if saved else ""))


# ---------- 승인 결정 ----------

def render_approval(runner, state, pending):
    inc = pending.get("incomplete", [])
    checklist = pending.get("checklist", [])
    progress = pending.get("progress", {})
    rid = runner.log.run_id
    rd, rt, cd, ct = session.checklist_progress(state, pending)
    with ui.card("approval"):
        ui.section("인계 완료 승인 요청", ui.chip(f"필수 {rd}/{rt}", "ok" if not inc else "warn") + ui.chip(f"전체 {cd}/{ct}", "gray"))
        if inc:
            ui.note(f"미완료 필수 항목 {len(inc)}개 — 모두 완료되어야 승인할 수 있습니다. 보류하면 신규자가 보완한 뒤 다시 승인을 요청합니다.", "warn")
            st.html("".join(f'<div class="il-meta">· {ui.esc(i["text"])}</div>' for i in inc))
        else:
            ui.note("신규자가 필수 항목을 모두 끝냈습니다. 승인하면 인계가 완료됩니다.", "ok")
        notes = [(i, progress.get(str(i["order"]), {}).get("note", "")) for i in checklist if progress.get(str(i["order"]), {}).get("note")]
        if notes:
            ui.section("신규자 메모·질문")
            st.html("".join(f'<div class="il-row"><div class="il-num gray">{i["order"]}</div><div class="il-body"><div class="il-main" style="font-weight:500">{ui.esc(n)}</div>'
                            f'<div class="il-meta">{ui.esc(i["text"])}</div></div></div>' for i, n in notes))
        with st.expander(f"체크리스트 {ct}개 보기"):
            from ilitda.ui.views.newcomer import readonly_list
            readonly_list(checklist, progress)
        note = st.text_input("메모 (보류할 때는 보완할 내용을 적어 주세요)", key=f"approve_note_{rid}_{state.get('hold_count', 0)}")
        with st.container(horizontal=True, gap="small", vertical_alignment="center"):
            if ui.busy_button("인계 완료 승인", "approve_ok", type="primary", disabled=bool(inc), icon=":material/task_alt:"):
                st.session_state["_goto"] = "newcomer"
                session.run_and_wait(lambda: runner.resume({"approved": True, "note": note.strip()}), "완료 판정 중…")
            if ui.busy_button("보류 (보완 요청)", "approve_hold", icon=":material/undo:"):
                st.session_state["_goto"] = "newcomer"
                session.run_and_wait(lambda: runner.resume({"approved": False, "note": note.strip()}), "보류를 기록하고 신규자에게 돌려보내는 중…")
            if inc:
                st.caption("미완료 항목이 있어 승인은 잠겨 있습니다.")


# ---------- 기록 ----------

def render_history(state, pending):
    answers = state.get("answers") or []
    approval = state.get("approval") or {}
    info = session.stage_info(state, pending)
    with ui.card("history"):
        ui.section("확인 요청 기록", ui.chip(f"답변 {len(answers)}건", "gray") if answers else "")
        if not answers and not approval:
            ui.empty_state("지금 답할 요청이 없습니다", info["headline"])
            return
        rows = []
        for i, a in enumerate(answers):
            label, tone = SOURCE.get(a["source"], (a["source"], "gray"))
            rows.append(f'<div class="il-row {"first" if i == 0 else ""}"><div class="il-body"><div class="il-main">{ui.esc(a["topic"])} {ui.chip(label, tone)}</div>'
                        f'<div class="il-meta">{ui.esc(a.get("question", ""))}</div>'
                        f'<div class="il-lead" style="font-size:14px">{ui.esc(a["answer"]) if a["answer"] else "<i>답 없음 — 신규자에게 단정해서 안내하지 않습니다</i>"}</div></div></div>')
        st.html("".join(rows))
        if approval:
            if approval.get("approved"):
                ui.note(approval.get("note") or "", "ok", "책임자 승인 완료")
            else:
                ui.note(approval.get("note") or "(사유 없음)", "warn", "책임자 보류 — 신규자 보완 중")

"""내 인계: 신규자가 보는 화면. 체크리스트(수행·저장·승인 요청·보류 후 보완), 절차와 근거, 바뀐 점."""
import streamlit as st

from ilitda.ui import components as ui
from ilitda.ui import session
from ilitda.ui.views import documents


def render():
    runner, state, pending = session.current()
    if not runner:
        st.html('<div class="il-title">내 인계</div>')
        ui.empty_state("진행 중인 인계가 없습니다", "인계를 시작하고 책임자 확인이 끝나면 여기에 체크리스트가 생깁니다.")
        if st.button("인계 시작", type="primary", key="n-start"):
            session.goto("start")
        return
    goal = state.get("goal") or {}
    info = ui.page_header(state, pending, meta=[("신규자", goal.get("newcomer")), ("완료 조건", goal.get("done_when")), ("실행 ID", runner.log.run_id)])
    kind = pending["type"] if pending else None
    if kind == "error":
        ui.error_panel(pending)
    steps = state.get("steps", [])
    if not steps:
        with ui.card("n-empty"):
            ui.empty_state("아직 절차가 준비되지 않았습니다", info["headline"])
        ui.page_actions(info, pending)
        return

    with ui.card("n-tabs"):
        tab1, tab2, tab3 = st.tabs(["체크리스트", f"절차와 근거 ({len(steps)}단계)", "바뀐 점"])
        with tab1:
            render_checklist(runner, state, pending, info)
        with tab2:
            review, review_text = session.review_state(state, pending)
            st.html(f'<div class="il-meta" style="margin-bottom:6px">{ui.chip(review_text, "ok" if review == "done" else ("warn" if review == "pending" else "gray"))}</div>')
            ui.handover_download(state, runner.log.run_id, key="dl-newcomer")
            ui.step_rows(steps, ui.docs_map(state), key="newcomer")
        with tab3:
            documents.render_changes(state)
    ui.page_actions(info, pending)


def render_checklist(runner, state, pending, info):
    kind = pending["type"] if pending else None
    checklist = (pending or {}).get("checklist") if kind in ("newcomer_progress", "owner_approval") else state.get("checklist")
    approval = state.get("approval") or {}
    held = approval.get("approved") is False and kind == "newcomer_progress"

    if not checklist:
        if kind == "ask_owner":
            ui.empty_state("책임자가 확인 질문에 답을 보내면 체크리스트가 만들어집니다", "")
        else:
            ui.empty_state("체크리스트가 아직 없습니다", info["headline"])
        return

    rd, rt, cd, ct = session.checklist_progress(state, pending)
    st.html(f'<div class="il-meta" style="margin-bottom:6px">{ui.chip(f"필수 {rd}/{rt}", "ok" if rd == rt else "warn")}{ui.chip(f"전체 {cd}/{ct}", "gray")}</div>')
    if held:
        ui.note(approval.get("note") or "(사유 없음)", "warn", "책임자 보류 사유")

    if kind == "newcomer_progress":
        st.caption("수행한 항목에 표시하고 저장하세요. 필수 항목이 모두 끝나야 책임자 승인 요청으로 넘어가고, 항목의 '메모'는 그때 책임자에게 함께 보입니다.")
        update = {}
        progress = pending.get("progress", {})
        rid = runner.log.run_id
        for item in checklist:
            saved = progress.get(str(item["order"]), {})
            c1, c2 = st.columns([8, 1.3], vertical_alignment="top")
            label = f"{item['order']}. {item['text']}" + ("" if item["required"] else "  (선택)")
            checked = c1.checkbox(label, value=bool(saved.get("done")), key=f"chk_{rid}_{item['order']}", help=item.get("how_to_verify"), persist_state="session")
            with c2.popover("메모", icon=":material/edit_note:"):
                note = st.text_area("질문·메모 (책임자에게 보입니다)", value=saved.get("note", ""), key=f"note_{rid}_{item['order']}", height=80, persist_state="session")
            update[str(item["order"])] = {"done": checked, "note": note.strip()}
        required = {str(i["order"]) for i in checklist if i["required"]}
        all_required = all(v["done"] for k, v in update.items() if k in required)
        label = "저장하고 승인 요청" if all_required else "진행 저장"
        with st.container(horizontal=True, gap="small", vertical_alignment="center"):
            if ui.busy_button(label, "progress_save", type="primary", icon=":material/save:"):
                session.run_and_wait(lambda: runner.resume(update), "진행 상태를 저장하는 중…")
            st.caption("필수 항목이 모두 끝났습니다. 저장하면 책임자 승인을 요청합니다." if all_required else "")
    elif kind == "owner_approval":
        ui.note("필수 항목을 모두 끝냈습니다. 책임자가 '확인 요청함'에서 승인 또는 보류를 결정합니다." if not pending.get("incomplete")
                else f"미완료 필수 항목 {len(pending['incomplete'])}개가 있습니다. 책임자가 보류하고 보완을 요청할 수 있습니다.", "info")
        if st.button("승인 결정하기", type="primary", key="to_approval"):
            session.goto("owner")
        readonly_list(checklist, pending.get("progress", {}))
    else:
        if state.get("status") == "completed":
            m = state.get("metrics", {})
            ui.note(f"책임자 승인 완료{(' · 메모: ' + approval['note']) if approval.get('note') else ''}", "ok", "인계 완료")
            ui.handover_download(state, runner.log.run_id, key="dl-done")
            ui.kv([("체크리스트", f"{m.get('checklist_done', cd)}/{m.get('checklist_total', ct)}"),
                   ("근거 있는 단계", f"{m.get('steps_with_evidence', '')}/{m.get('steps', '')}"),
                   ("책임자 답변", m.get("answered_by_owner")), ("이전 답변 확인", m.get("answered_from_memory")),
                   ("미확정", m.get("unresolved")), ("AI 호출", f"{m.get('llm_calls', '')}회 (재생 {m.get('llm_replays', '')}회)")])
        readonly_list(checklist, state.get("progress", {}))


def readonly_list(checklist, progress):
    rows = []
    for i, item in enumerate(checklist):
        done = bool(progress.get(str(item["order"]), {}).get("done"))
        note = progress.get(str(item["order"]), {}).get("note", "")
        mark = ui.chip("완료", "ok") if done else ui.chip("미완료" if item["required"] else "선택", "gray")
        rows.append(f'<div class="il-row {"first" if i == 0 else ""}"><div class="il-num {"" if done else "gray"}">{item["order"]}</div>'
                    f'<div class="il-body"><div class="il-main" style="font-weight:500">{ui.esc(item["text"])}</div>'
                    f'<div class="il-meta">{mark} 확인 방법: {ui.esc(item.get("how_to_verify", ""))}{(" · 메모: " + ui.esc(note)) if note else ""}</div></div></div>')
    st.html("".join(rows))

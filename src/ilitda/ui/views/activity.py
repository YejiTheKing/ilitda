"""활동 기록 화면: 에이전트가 무엇을 어떤 순서로 했는지. 작업 계획과 기술 로그는 접어 둔다."""
import re

import streamlit as st

from ilitda.ui import components as ui
from ilitda.ui import session
from ilitda.ui.session import KIND_LABEL

TONE = {"goal": "info", "plan": "info", "reasoning": "gray", "tool": "gray", "memory": "info", "feedback": "ok", "human": "warn", "error": "danger"}
TOKENS = re.compile(r"입력 (\d+) / 출력 (\d+) 토큰")


def llm_summary(entries):
    calls = [e for e in entries if e.get("tool") == "llm"]
    replays = sum(1 for e in calls if e.get("replay"))
    tin = tout = 0
    for e in calls:
        m = TOKENS.search(str(e.get("detail") or ""))
        if m:
            tin += int(m.group(1))
            tout += int(m.group(2))
    return len(calls), replays, tin, tout


def render():
    runner, state, pending = session.current()
    if not runner:
        st.html('<div class="il-title">실행 로그</div>')
        ui.empty_state("진행 중인 인계가 없습니다", "실행이 시작되면 목표 해석, 계획, 도구 호출, 판단, 사람 확인이 순서대로 기록됩니다.")
        if st.button("인계 시작", type="primary", key="a-start"):
            session.goto("start")
        return
    entries = runner.log.read()
    info = ui.page_header(state, pending, meta=[("기록", f"{len(entries)}건"), ("실행 ID", runner.log.run_id)])

    plan = state.get("plan") or {}
    with ui.card("plan"):
        with st.expander(f"에이전트 작업 계획 ({len(plan.get('steps', []))}단계)" if plan else "에이전트 작업 계획 (아직 없음)"):
            if not plan:
                st.caption("목표 해석이 끝나면 자료 목록을 보고 계획을 세웁니다.")
            for s in plan.get("steps", []):
                st.html(f'<div class="il-row"><div class="il-num gray">{ui.esc(s["id"])}</div><div class="il-body"><div class="il-main" style="font-weight:500">{ui.esc(s["action"])}</div>'
                        f'<div class="il-meta">{ui.chip(s.get("tool", ""), "gray")} {ui.esc(s.get("why", ""))}</div></div></div>')
            if plan.get("notes"):
                ui.note(plan["notes"], "info", "계획 메모")

    counts = {}
    for e in entries:
        counts[e["kind"]] = counts.get(e["kind"], 0) + 1
    calls, replays, tin, tout = llm_summary(entries)
    with ui.card("log"):
        ui.section(f"실행 로그 {len(entries)}건", "".join(ui.chip(f"{KIND_LABEL.get(k, k)} {v}", TONE.get(k, "gray")) for k, v in counts.items()))
        if calls:
            st.html(f'<div class="il-small">AI 호출 {calls}회 (미리 준비된 결과 재생 {replays}회) · 입력 {tin:,} / 출력 {tout:,} 토큰 · 기록된 실제 값</div>')
        kinds = [k for k in KIND_LABEL if k in counts]
        chosen = st.pills("종류", kinds, selection_mode="multi", default=kinds, format_func=lambda k: KIND_LABEL.get(k, k),
                          key=f"act_kinds_{runner.log.run_id}_{len(kinds)}", label_visibility="collapsed")
        chosen = set(chosen or kinds)
        shown = [e for e in entries if e["kind"] in chosen]
        if not shown:
            ui.empty_state("기록이 없습니다", "실행이 진행되면 여기에 쌓입니다.")
        for i, e in enumerate(shown):
            when = str(e.get("time", ""))[11:19]
            extra = (f" · {e['seconds']}초" if e.get("seconds") is not None else "") + (" " + ui.chip("준비된 결과 재생", "info") if e.get("replay") else "")
            st.html(f'<div class="il-row {"first" if i == 0 else ""}"><div class="il-body"><div class="il-main" style="font-weight:500">{ui.esc(e["title"])}</div>'
                    f'<div class="il-meta">{ui.chip(KIND_LABEL.get(e["kind"], e["kind"]), TONE.get(e["kind"], "gray"))} {when}{extra}</div></div></div>')
            d = e.get("detail")
            if isinstance(d, list) and d:
                if len(d) <= 3:
                    st.html("".join(f'<div class="il-meta">· {ui.esc(x)}</div>' for x in d))
                else:
                    with st.expander(f"자세히 ({len(d)}개)"):
                        st.html("".join(f'<div class="il-meta">· {ui.esc(x)}</div>' for x in d))
            elif isinstance(d, dict) and d:
                with st.expander("자세히"):
                    st.json(d, expanded=True)
            elif d:
                st.html(f'<div class="il-meta">{ui.esc(d)}</div>')
    ui.page_actions(info, pending)

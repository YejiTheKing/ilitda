"""일잇다 화면 (진입점).

실행: .venv/bin/streamlit run src/ilitda/ui/app.py
화면: 인계 시작 / 확인 요청함 / 내 인계 / 실행 로그 (+ 공개 모드: 테스트 안내, 피드백 남기기).
에이전트가 돌아가는 동안 실행 로그가 실시간으로 보이고, 멈추면 해당 화면에 요청이 뜬다. 화면을 그리는 것만으로 AI를 다시 부르지 않는다.
"""
import os
from pathlib import Path

# data/, runs/, .env는 프로젝트 루트 기준 상대 경로다. 어디서 실행해도 같은 곳을 보게 한다
os.chdir(Path(__file__).resolve().parents[3])

import streamlit as st  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
st.set_page_config(page_title="일잇다", page_icon=":material/link:", layout="wide", initial_sidebar_state="expanded")
if os.environ.get("ILITDA_PUBLIC") == "1":
    st.set_option("client.showErrorDetails", "type")   # 공개 링크에서는 내부 경로가 든 추적 정보를 보이지 않는다

from ilitda.ui import components as ui  # noqa: E402
from ilitda.ui import session, theme  # noqa: E402
from ilitda.ui.views import activity, newcomer, owner, public, start  # noqa: E402

PAGES = {"start": start.render, "owner": owner.render, "newcomer": newcomer.render, "log": activity.render,
         "guide": public.render_guide, "feedback": public.render_feedback}


def render_sidebar(runner, state, pending):
    with st.sidebar:
        st.html('<div class="il-brand"><div class="name">일잇다 🔗</div>'
                '<small>담당자가 떠난 자리의 업무를 복원하는 인수인계 AI 에이전트</small></div>')
        page = st.session_state["page"]
        busy = session.working()
        open_n = session.open_question_count(pending)
        for key, label, icon in (session.MENU_PUBLIC if session.PUBLIC else session.MENU):
            text = f"{label}  ·  {open_n}" if key == "owner" and open_n else label
            with st.container(key=f"nav-{key}"):
                if st.button(text, icon=icon, type="primary" if page == key else "tertiary", width="stretch", key=f"navbtn-{key}"):
                    session.goto(key)
        st.divider()
        st.html('<div class="il-side-label">진행 중</div>')
        if runner:
            goal = state.get("goal") or {}
            info = session.stage_info(state, pending)
            stage = "완료" if info["index"] >= len(session.STAGES) else session.STAGES[info["index"]]
            st.html(f'<div class="il-small"><span class="il-wrap">{ui.esc(goal.get("task") or "목표 해석 중")}</span><br>'
                    f'단계: {ui.esc(stage)}{" · 오류" if info["blocked"] else ""}<br>'
                    + (f'재개 코드 <code>{ui.esc(session.resume_code(runner))}</code>' if session.PUBLIC else f'실행 ID <code>{ui.esc(runner.log.run_id)}</code>') + '</div>')
            if st.button("새 인계 시작", icon=":material/add:", width="stretch", key="nav-new", disabled=busy):
                session.go_home()
        else:
            st.html('<div class="il-small">진행 중인 인계가 없습니다.</div>')

        current = runner.log.run_id if runner else None
        if session.PUBLIC:
            # 연결이 끊겨 새 세션이 됐을 때 재개 코드(실행ID.토큰)로 멈춘 자리에 다시 들어온다. 코드가 맞는 공개 실행만 열린다
            typed = st.text_input("끊긴 인계 다시 열기 (재개 코드)", placeholder="예: 20261003-161943-f219ec.a1b2c3d4", key="reopen_id", disabled=busy).strip()
            if st.button("열기", key="reopen_go", disabled=busy or not typed) and typed:
                rid = session.can_reopen(typed)
                if rid and rid != current:
                    session.open_runner(rid)
                    st.session_state["_goto"] = "start"
                    st.rerun()
                elif not rid:
                    st.caption("재개 코드를 확인해 주세요.")
        else:
            runs = session.list_runs()
            options = ["(새 인계)"] + runs
            if st.session_state.get("run_choice") not in options:
                st.session_state["run_choice"] = current if current in options else "(새 인계)"
            choice = st.selectbox("이전 실행 열기", options, key="run_choice", format_func=session.run_label, disabled=busy)
            if choice != "(새 인계)" and choice != current and not busy:
                session.open_runner(choice)
                st.rerun()


theme.inject()
session.apply_deferred_navigation()
_runner, _state, _pending = session.current()
render_sidebar(_runner, _state, _pending)
session.attach_worker()   # 에이전트가 아직 돌고 있으면 실시간 로그를 보여 주며 기다린다
PAGES[st.session_state["page"]]()

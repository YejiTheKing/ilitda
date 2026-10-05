"""공개 테스트 모드 전용 화면: 안내, 피드백."""
import json
import uuid
from datetime import datetime

import streamlit as st

from ilitda.ui import components as ui
from ilitda.ui import session
from ilitda.ui.session import FEEDBACK_DIR


def render_guide():
    st.html('<div class="il-title">테스트 안내</div>'
            '<div class="il-sub">담당자가 떠난 자리의 업무를 남겨진 파일만으로 복원하는 인수인계 AI 에이전트. 경진대회 출품작(검증용)이며 소요 시간은 10분 이내입니다.</div>')
    with ui.card("flow"):
        ui.section("이렇게 진행됩니다")
        cols = st.columns(4, gap="small")
        steps = [("1", "인계 시작", "내 업무 파일을 올리거나 가상 자료를 선택하고, 인계 목표를 한 문장으로 입력합니다."),
                 ("2", "확인 요청함", "자료만으로 정할 수 없는 항목을 에이전트가 질문합니다. 아는 범위에서 답변하고, 모르는 항목은 비워 둡니다."),
                 ("3", "내 인계", "근거가 붙은 절차와 체크리스트를 확인하고, 수행 표시 → 책임자 승인까지 진행합니다."),
                 ("4", "피드백 남기기", "복원 정확도와 사용 편의성을 점수와 한 줄 평으로 남깁니다.")]
        for col, (n, t, b) in zip(cols, steps):
            col.html(f'<div class="il-row first"><div class="il-num">{n}</div><div class="il-body"><div class="il-main">{ui.esc(t)}</div><div class="il-meta">{ui.esc(b)}</div></div></div>')
        st.caption("가상 자료를 선택하면 '이대표가 아는 사실 (정답 메모)'가 질문 위에 함께 표시됩니다. 테스트에서는 한 사람이 책임자(답변·승인)와 신규자(체크리스트) 역할을 모두 수행합니다.")
    with ui.card("roles"):
        ui.section("역할 — 테스트에서는 책임자와 신규자를 한 사람이 맡습니다")
        st.markdown("""
| 역할 | 누가 | 하는 일 |
|---|---|---|
| **에이전트** | AI | 파일을 읽고 최신본을 가리고 절차를 복원합니다. 모르는 내용은 지어내지 않고 **책임자에게 질문**합니다 |
| **책임자** (사장·팀장) | **나** | 확인 질문에 답하고, 복원된 절차를 수정하고, 마지막에 승인합니다 |
| **신규자** | **나** | 체크리스트대로 수행 표시를 합니다 (가상 자료에서는 실제로 수행하지 않아도 됩니다) |
""")
    with ui.card("ways"):
        ui.section("내 업무 파일을 올리려면 — 무엇을 올리나")
        if True:
            st.markdown("""
| 종류 | 예시 |
|---|---|
| **빈 양식** | 견적서, 발주서, 거래처 등록 요청서, A/S 접수증, 지출결의서, 작업표준서 |
| **절차 메모** | "이 일은 이렇게 한다"고 적어 둔 메모, 인수인계서, 업무 매뉴얼 한 부분 |
| **체크리스트** | 월마감 체크리스트, 점검표, 신입 교육 체크리스트 |
| **처리 기록** | 실제로 작성했던 견적서·보고서·업무일지 1–2건 (고객 이름·금액은 지우거나 바꿔서) |
""")
            st.caption("한 가지 업무에 관한 파일 3–10개. 구버전·최신본이 섞여 있어도 됩니다. 형식: PDF, Word, Excel, 한글(hwp·hwpx), 텍스트. 사진은 읽지 못합니다.")
            st.markdown("""
| 업무 | 올릴 파일 예시 | 목표 문장 예시 |
|---|---|---|
| **견적** | 견적서 양식(구·신), 단가표, 작년 견적서 1건, 견적 절차 메모 | 신입 영업사원이 견적 요청 접수부터 견적서 발송까지 혼자 하게 인계해줘 |
| **생산·품질** | 작업표준서, 점검 체크리스트, 불량 보고서 양식, 일일 생산일지 | 신입 작업자가 설비 점검부터 생산일지 작성까지 혼자 하게 인계해줘 |
| **민원·고객 응대** | 접수 양식, 응대 매뉴얼, 처리 기록 1–2건 | 신입 상담원이 접수부터 처리 완료 통보까지 혼자 하게 인계해줘 |
""")
    with ui.card("caution"):
        ui.section("주의사항 · 개인정보")
        if True:
            st.markdown("""
- **개인정보·고객정보는 임의 정보로 바꾸거나 제거해서** 올려 주세요. 올려도 되는지 애매하면 사장님이나 상사의 **동의를 먼저** 구하세요
- 올린 파일은 이 PC에만 저장되고, 전화·주소 같은 형식 정보를 가린 뒤 외부 AI(Anthropic API)로 분석되며, **대회가 끝나면 삭제**합니다
- **회사 이름·개인정보는 대회 영상, 발표자료, 보고서에 나오지 않습니다**
- 하루 AI 호출 한도가 있어 "한도 도달" 안내가 나올 수 있습니다. 그 경우 가상 자료로 진행해 주세요
- 연결이 끊기면 왼쪽 메뉴 아래 '끊긴 인계 다시 열기'에 재개 코드(사이드바에 보이는 실행ID.코드)를 넣으면 멈춘 자리부터 이어집니다
""")
    if st.button("시작하기", type="primary", key="guide_start", icon=":material/arrow_forward:"):
        session.goto("start")


def render_feedback():
    runner, state, pending = session.current()
    st.html('<div class="il-title">피드백 남기기</div><div class="il-sub">대회 제출용 사용자 검증 확인서에 들어갑니다 (이름 또는 소속, 날짜, 피드백).</div>')
    fb_folder = state.get("folder") or next((f for f in session.sample_folders() if session.sample_intro(f)), "")
    facts = session.intro_section(session.sample_intro(fb_folder), "이대표가 아는 사실")
    if facts:
        with st.expander("이대표가 아는 사실 (정답 메모) — 가상 자료로 진행한 경우 이 표와 비교해 평가해 주세요"):
            st.markdown(facts)
    with ui.card("feedback"):
        with st.form("feedback"):
            name = st.text_input("이름")
            org = st.text_input("소속 또는 직무 (예: 제조업 영업, 세무사 사무소 직원, 대학생)")
            minutes = st.number_input("사용한 시간(분)", min_value=1, max_value=120, value=10)
            own_files = st.radio("사용한 자료", ["준비된 가상 자료", "내 업무 파일 올리기"], horizontal=True)
            st.markdown("**점수** (1 전혀 아니다 ~ 5 매우 그렇다)")
            accuracy = st.slider("복원된 절차가 실제 업무(또는 자료 내용)와 맞게 나왔다", 1, 5, 3,
                                 help="가상 자료로 진행한 경우 위의 '이대표가 아는 사실 (정답 메모)'와 비교해 주세요.")
            ease = st.slider("사용하기 쉬웠다", 1, 5, 3)
            intent = st.slider("내 직장에 이런 도구가 있다면 쓰겠다", 1, 5, 3)
            good = st.text_area("좋았던 점")
            bad = st.text_area("불편했거나 틀린 점, 보완하면 좋을 점")
            offer = st.checkbox("우리 회사의 양식과 절차 메모를 제공할 의향이 있습니다 (선택)")
            st.caption("회사 이름과 개인정보는 대회 영상·발표자료·보고서에 나오지 않습니다. 이름·소속(직무)·피드백은 사용자 검증 확인서에만 들어갑니다.")
            consent = st.checkbox("위 이름·소속·피드백을 대회 제출 서류(사용자 검증 확인서)에 적는 것에 동의합니다")
            sent_key = f"feedback_sent_{runner.log.run_id if runner else 'none'}"
            if st.session_state.get(sent_key):
                st.success("이미 저장되었습니다. 고맙습니다.")
            elif st.form_submit_button("보내기", type="primary"):
                if not name.strip() or not consent:
                    st.error("이름과 동의 체크가 필요합니다.")
                else:
                    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
                    entry = {"name": name.strip(), "org": org.strip(), "minutes": int(minutes), "good": good.strip(),
                             "bad": bad.strip(), "intent": int(intent), "own_files": own_files == "내 업무 파일 올리기",
                             "accuracy": int(accuracy), "ease": int(ease), "offer_files": bool(offer), "consent": True,
                             "date": datetime.now().strftime("%Y-%m-%d"), "time": datetime.now().isoformat(timespec="seconds"),
                             "run_id": runner.log.run_id if runner else None}
                    try:   # 파일 이름에는 입력값을 넣지 않는다 (경로 문자·개인정보)
                        (FEEDBACK_DIR / f"{entry['time'].replace(':', '')}_{uuid.uuid4().hex[:6]}.json").write_text(
                            json.dumps(entry, ensure_ascii=False, indent=1), encoding="utf-8")
                        st.session_state[sent_key] = True   # 같은 실행에서 두 번 저장되지 않게
                        st.success("고맙습니다. 저장되었습니다.")
                    except OSError:
                        st.error("저장에 실패했습니다. 잠시 뒤 다시 시도해 주세요.")

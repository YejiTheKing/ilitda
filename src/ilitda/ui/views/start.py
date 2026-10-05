"""인계 시작: 자료 → 목표 한 문장 → 시작. 시작한 뒤에는 같은 자리에 진행 상태와 결과(복원한 절차·자료와 최신본). 에이전트의 계획은 실행 로그에."""
from pathlib import Path

import streamlit as st

from ilitda.ui import components as ui
from ilitda.ui import session
from ilitda.ui.session import GOAL_EXAMPLES, GOAL_FORMAT, PUBLIC, UPLOAD_DIR, UPLOAD_MAX_FILES, UPLOAD_MAX_MB, UPLOAD_TYPES
from ilitda.ui.views import documents

MODE_SAMPLE, MODE_OWN = "준비된 가상 자료", "내 업무 파일 올리기"


def file_list_html(files):
    if not files:
        return '<div class="il-small">선택한 파일이 없습니다.</div>'
    return "".join(f'<div class="il-row {"first" if i == 0 else ""}"><div class="il-body"><span class="il-wrap">{ui.esc(f["name"])}</span> '
                   f'{ui.chip(f["ext"].upper() or "파일", "gray")}<span class="il-small">{ui.esc(session.fmt_size(f["size"]))}</span></div></div>'
                   for i, f in enumerate(files))


def render():
    runner, state, pending = session.current()
    if not runner:
        render_form()
    else:
        render_result(runner, state, pending)


# ---------- 시작 폼 ----------

def render_form():
    if not PUBLIC:
        render_form_private()
        return
    st.html('<div class="il-title">인계 시작</div>'
            '<div class="il-sub">담당자가 남긴 파일만으로 절차를 복원하고, 책임자 확인을 거쳐 신규자의 첫 업무 완료까지 이끕니다.</div>')
    if "start_mode" not in st.session_state:
        st.session_state["start_mode"] = MODE_OWN
    uploads, consent, folder, files = None, True, None, []

    with ui.card("start"):
        ui.section("1. 자료")
        mode = st.segmented_control("자료", [MODE_OWN, MODE_SAMPLE], key="start_mode", label_visibility="collapsed") \
            or MODE_OWN   # 선택을 해제하면 None이 온다. 위젯이 그려진 뒤라 session_state는 건드리지 않는다
        if mode == MODE_OWN:
            uploads = st.file_uploader("파일 선택", type=UPLOAD_TYPES, accept_multiple_files=True, key="start_uploads", label_visibility="collapsed")
            files = [{"name": Path(u.name).name, "size": u.size, "ext": Path(u.name).suffix.lstrip(".").lower()} for u in (uploads or [])]
            consent = st.checkbox("개인정보·고객정보는 임의 정보로 바꾸거나 지웠고, 올려도 되는 자료입니다. 외부 AI(Anthropic API) 처리에 동의합니다.",
                                  key="start_consent")
            with st.expander("무엇을 올리나 · 어떻게 처리되나"):
                st.markdown("한 가지 업무에 관한 파일 3–10개: 빈 양식(견적서·발주서·접수증), 절차 메모·인수인계서, 체크리스트·점검표, 실제 처리 기록 1–2건. "
                            f"구버전과 최신본이 섞여 있어도 됩니다. 형식: {', '.join(UPLOAD_TYPES)} (사진은 읽지 못합니다).  \n"
                            "올린 파일은 이 PC에만 저장되고, 전화·주소 같은 형식 정보를 가린 뒤 AI로 분석되며, 대회가 끝나면 삭제합니다. "
                            "회사 이름·개인정보는 대회 영상·발표자료·보고서에 나오지 않습니다. 올려도 되는지 애매하면 사장님이나 상사의 동의를 먼저 구하세요.")
        else:
            folders = session.sample_folders()
            if not folders:
                ui.empty_state("가상 자료가 없습니다", "data/sample 아래에 업무 폴더가 있어야 합니다.")
            else:
                folder = st.selectbox("자료 폴더", folders, key="start_folder") if len(folders) > 1 else folders[0]
                intro = session.sample_intro(folder)
                files = session.folder_files(folder)
                st.caption(f"{session.intro_section(intro, '어떤 회사').split('.')[0].replace('가상의 ', '가상 ').replace('**', '') if intro else Path(folder).name} · 파일 {len(files)}개")
                with st.expander("어떤 회사인지 · 파일 목록 · 정답 메모 · zip 내려받기"):
                    if intro:
                        for title, body in intro.items():
                            if title.startswith("이렇게"):
                                continue
                            st.markdown(f"**{title}**")
                            st.markdown(body)
                    st.html(file_list_html(files))
                    st.download_button(f"파일 {len(files)}개 zip 내려받기", session.zip_folder(folder), file_name=f"{Path(folder).name}.zip",
                                       mime="application/zip", key="start_zip", type="tertiary", icon=":material/download:")

        ui.section("2. 인계 목표")
        goal = st.text_area("인계 목표", session.default_goal(folder) if mode == MODE_SAMPLE else GOAL_EXAMPLES["거래처·견적"],
                            key=f"start_goal_{Path(folder).name if folder else 'own'}", height=84, placeholder=GOAL_FORMAT,
                            help=f"형식: {GOAL_FORMAT} 업무나 신규자가 빠지면 에이전트가 되묻습니다.")
        for msg in st.session_state.pop("start_problems", []):
            st.error(msg)
        with st.container(horizontal=True, gap="small", vertical_alignment="center"):
            start = ui.busy_button("인계 시작", "start_go", type="primary", icon=":material/play_arrow:")
            st.caption("올린 파일은 AI 호출로 1~2분 걸립니다. 진행 상황은 버튼 아래에 바로 표시됩니다." if mode == MODE_OWN else "진행 상황은 버튼 아래에 바로 표시됩니다.")
    if not start:
        return

    problems = []
    if mode == MODE_OWN:
        if not uploads:
            problems.append("파일을 올려 주세요.")
        elif len(uploads) > UPLOAD_MAX_FILES or any(u.size > UPLOAD_MAX_MB * 1024 * 1024 for u in uploads):
            problems.append(f"파일은 {UPLOAD_MAX_FILES}개, 각 {UPLOAD_MAX_MB}MB까지입니다.")
        if not consent:
            problems.append("개인정보 확인과 외부 AI 처리 동의가 필요합니다.")
    elif not folder:
        problems.append("가상 자료 폴더가 없습니다.")
    if not goal.strip():
        problems.append("인계 목표를 적어 주세요.")
    if problems:
        st.session_state["start_problems"] = problems
        ui.release("start_go")
        st.rerun()

    launch(goal, folder, uploads if mode == MODE_OWN else None)


def launch(goal, folder, uploads):
    """실행을 만들고, 올린 파일이 있으면 실행 폴더에 저장한 뒤 에이전트를 시작한다."""
    runner = session.open_runner()
    if uploads:
        target = UPLOAD_DIR / runner.log.run_id
        target.mkdir(parents=True, exist_ok=True)
        saved = []
        for u in uploads:
            name = Path(u.name).name   # 경로 문자를 떼어 폴더 밖으로 못 나가게
            stem, ext, k = Path(name).stem, Path(name).suffix, 2
            while (target / name).exists():   # 같은 이름이면 덮어쓰지 않고 번호를 붙인다
                name, k = f"{stem} ({k}){ext}", k + 1
            (target / name).write_bytes(u.getbuffer())
            saved.append(name)
        folder = str(target)
        runner.log.add("human", f"사용자가 파일 {len(saved)}개 업로드", saved)
    st.session_state["_goto"] = "start"
    session.run_and_wait(lambda: runner.start(goal, folder), "에이전트가 목표를 해석하고 자료를 읽는 중…")


# ---------- 시작 폼 (실제용) ----------

FORMAT_LABELS = {"pdf": "PDF", "docx": "Word", "xlsx": "Excel", "hwpx": "한글", "hwp": "한글", "txt": "텍스트", "md": "텍스트"}


def render_form_private():
    """실제 업무용: 큰 업로드 영역 하나 → 업로드 가이드 → 목표 → 맨 아래 버튼. 폴더 경로 선택은 없다."""
    st.html('<div class="il-title">인계 시작</div>'
            '<div class="il-sub">담당자가 남긴 파일을 올리면 절차를 복원하고, 책임자 확인을 거쳐 신규자의 업무 완료를 돕습니다.</div>')
    formats = " · ".join(dict.fromkeys(FORMAT_LABELS[t] for t in UPLOAD_TYPES))
    with ui.card("start"):
        ui.section("자료 업로드")
        with st.container(key="start-drop"):
            st.html(f'<style>.st-key-start-drop [data-testid="stFileUploaderDropzoneInstructions"] span::after {{ content: "{formats} · 파일당 {UPLOAD_MAX_MB}MB · 최대 {UPLOAD_MAX_FILES}개"; }}</style>')
            uploads = st.file_uploader("파일 선택", type=UPLOAD_TYPES, accept_multiple_files=True, key="start_uploads", label_visibility="collapsed")
        # 고른 즉시 검사해 결과를 드롭존 바로 아래에 보여 준다 (제출 때까지 기다리지 않는다)
        if uploads:
            too_big = [u.name for u in uploads if u.size > UPLOAD_MAX_MB * 1024 * 1024]
            if too_big:
                st.error(f"{UPLOAD_MAX_MB}MB를 넘는 파일: {', '.join(too_big)}. 목록에서 지워 주세요.")
            elif len(uploads) > UPLOAD_MAX_FILES:
                st.error(f"한 번에 {UPLOAD_MAX_FILES}개까지 올릴 수 있습니다. 지금 {len(uploads)}개입니다.")
            else:
                st.html(f'<div class="il-small" style="color:var(--il-accent);font-weight:600;margin-top:-4px">'
                        f'파일 {len(uploads)}개 준비됨 · {session.fmt_size(sum(u.size for u in uploads))}</div>')
        with st.expander("업로드 가이드", icon=":material/help_outline:"):
            st.markdown(
                "**무엇을 올리나** 한 가지 업무에 관한 파일 3–10개. 빈 양식(견적서·발주서·접수증), 절차 메모·인수인계서, 체크리스트·점검표, 실제 처리 기록 1–2건. "
                "구버전과 최신본이 섞여 있어도 됩니다. 에이전트가 최신본을 가려냅니다.  \n"
                f"**형식과 크기** {formats}. 파일당 {UPLOAD_MAX_MB}MB, 한 번에 {UPLOAD_MAX_FILES}개까지. 사진·스캔 이미지는 읽지 못합니다.  \n"
                "**처리 방식** 올린 파일은 이 PC의 실행 폴더에만 저장됩니다. 전화번호·주소 같은 형식 정보를 가린 뒤 AI로 분석하며, 결과는 실행 로그에서 근거와 함께 확인할 수 있습니다.")

        ui.section("인계 목표")
        goal = st.text_area("인계 목표", GOAL_EXAMPLES["거래처·견적"], key="start_goal_own", height=84, placeholder=GOAL_FORMAT,
                            label_visibility="collapsed", help=f"형식: {GOAL_FORMAT} 업무나 신규자가 빠지면 에이전트가 되묻습니다.")
        for msg in st.session_state.pop("start_problems", []):
            st.error(msg)
        with st.container(key="start-actions", horizontal=True, gap="small", vertical_alignment="center", horizontal_alignment="right"):
            st.caption("AI 호출로 1~2분 걸립니다. 진행 상황은 아래에 바로 표시됩니다.")
            start = ui.busy_button("인계 시작", "start_go", type="primary", icon=":material/play_arrow:")
    if not start:
        return

    problems = []
    if not uploads:
        problems.append("파일을 올려 주세요.")
    elif len(uploads) > UPLOAD_MAX_FILES or any(u.size > UPLOAD_MAX_MB * 1024 * 1024 for u in uploads):
        problems.append(f"파일은 {UPLOAD_MAX_FILES}개, 각 {UPLOAD_MAX_MB}MB까지입니다.")
    if not goal.strip():
        problems.append("인계 목표를 적어 주세요.")
    if problems:
        st.session_state["start_problems"] = problems
        ui.release("start_go")
        st.rerun()
    launch(goal, None, uploads)


# ---------- AI가 판단한 것 ----------

def render_ai_judgments(runner, state):
    """AI(LLM)가 내린 판단과 코드가 검증한 것을 나눠 보여 준다. '고정 규칙만 있는 웹페이지'로 오해하지 않게."""
    from ilitda.ui.views.activity import llm_summary
    calls, replays, tin, tout = llm_summary(runner.log.read())
    plan = state.get("plan") or {}
    changes = [c for c in state.get("changes", []) if c.get("matters")]
    qs = state.get("questions", [])
    conflicts = [q for q in qs if q.get("kind") == "conflict"]
    gaps = [q for q in qs if q.get("kind") == "gap"]
    steps = state.get("steps", [])
    label = f"AI가 판단한 것 — 호출 {calls}회" + (f" · 입력 {tin:,} / 출력 {tout:,} 토큰" if (tin or tout) else "") \
        + (f" · 준비된 응답 재생 {replays}회" if replays else "")
    with st.expander(label):
        st.html(f'<div class="il-meta">{ui.chip("AI", "info")} <b>계획</b> {len(plan.get("steps", []))}단계 — 자료 목록을 보고 어떤 도구를 어떤 순서로 쓸지 정함'
                + (f'<br><span class="il-small">{ui.esc(plan.get("notes", ""))}</span>' if plan.get("notes") else "") + "</div>")
        if changes:
            st.html(f'<div class="il-meta">{ui.chip("AI", "info")} <b>변경 영향 분류</b> {len(changes)}건 — 어떤 변경이 업무에 영향을 주는지</div>'
                    + "".join(f'<div class="il-meta">· [{ui.esc(c.get("type", ""))}] {ui.esc(c.get("summary", ""))} → {ui.esc(c.get("impact", ""))}</div>' for c in changes[:5]))
        if conflicts or gaps:
            st.html(f'<div class="il-meta">{ui.chip("AI", "info")} <b>충돌·빈틈 감지</b> 충돌 {len(conflicts)}건 · 빈틈 {len(gaps)}건 — 자료끼리 어긋나거나 없는 내용을 찾아 질문으로 만듦</div>'
                    + "".join(f'<div class="il-meta">· {ui.esc(q.get("topic", ""))}: {ui.esc(q.get("why") or "출처 " + str(len(q.get("claims", []))) + "개가 서로 다름")}</div>' for q in (conflicts + gaps)[:5]))
        if steps:
            ok = sum(1 for s in steps if s["status"] == "ok")
            st.html(f'<div class="il-meta">{ui.chip("AI", "info")} <b>절차 복원</b> {len(steps)}단계와 근거 인용을 작성 → {ui.chip("코드", "gray")} 인용이 원문에 실제로 있는지 검증 {ok}/{len(steps)}</div>')
        st.html(f'<div class="il-meta">{ui.chip("코드", "gray")} <b>최신본 판별·변경점 비교·근거 검증</b>은 일부러 규칙 코드로 — AI가 지어낸 근거를 잡아내고, 같은 입력에 같은 결과를 내기 위해</div>')


# ---------- 진행 상태와 결과 ----------

def render_result(runner, state, pending):
    goal = state.get("goal") or {}
    docs = state.get("documents", [])
    meta = [("신규자", goal.get("newcomer")), ("책임자", goal.get("owner")),
            ("자료", f"{session.source_label(state.get('folder', ''))} {len(docs)}개" if docs else session.source_label(state.get("folder", ""))),
            ("실행 ID", runner.log.run_id)]
    info = ui.page_header(state, pending, meta=meta)
    kind = pending["type"] if pending else None

    if kind == "error":
        ui.error_panel(pending)
    elif state.get("status") == "no_documents":
        with ui.card("nodocs"):
            ui.empty_state("읽을 수 있는 자료가 없습니다", "양식, 절차 메모, 체크리스트 파일(PDF, Word, Excel, HWPX, 텍스트)을 넣고 다시 시작하세요.")
            for u in state.get("unreadable", []):
                st.html(f'<div class="il-meta">{ui.chip("읽기 실패", "danger")} {ui.esc(u["name"])} — {ui.esc(u["reason"])}</div>')
    elif kind == "clarify_goal":
        with ui.card("clarify"):
            ui.section("에이전트가 묻습니다")
            ui.note(pending.get("question", ""), "info")
            extra = st.text_input("추가 정보", key=f"clarify_{runner.log.run_id}", placeholder="예: 업무는 월마감, 신규자는 박신입", persist_state="session")
            if ui.busy_button("답변 보내기", "clarify_send", type="primary", disabled=not extra.strip()):
                session.run_and_wait(lambda: runner.resume(extra.strip()), "이어서 진행 중…")

    steps = state.get("steps", [])
    if goal and (docs or steps):
        with ui.card("summary"):
            ui.section("에이전트가 한 일", "")
            versions = state.get("versions", [])
            changes = [c for c in state.get("changes", []) if c.get("matters")]
            answers = state.get("answers") or []
            qn = len(state.get("questions", []))
            rd, rt, cd, ct = session.checklist_progress(state, pending)
            ui.kv([("읽은 자료", f"{len(docs)}개" + (f" (실패 {len(state.get('unreadable', []))})" if state.get("unreadable") else "")),
                   ("최신본 판별", f"{len(versions)}묶음" if versions else "해당 없음"),
                   ("업무에 영향 있는 변경", f"{len(changes)}건" if versions else ""),
                   ("복원한 절차", f"{len(steps)}단계 · 근거 확인 {sum(1 for s in steps if s['status'] == 'ok')}" if steps else ""),
                   ("책임자 확인", (f"질문 {qn}건 · 답변 {sum(1 for a in answers if a['source'] == 'owner')} · 이전 답변 확인 {sum(1 for a in answers if a['source'] == 'memory' or a.get('from_suggestion'))} · 미확정 {sum(1 for a in answers if a['source'] == 'unresolved')}") if answers else (f"질문 {qn}건 대기" if qn else "")),
                   ("체크리스트", f"{cd}/{ct}" if ct else ""),
                   ("완료 조건", goal.get("done_when"))])
            render_ai_judgments(runner, state)

    if steps or docs:
        with ui.card("result"):
            tab_steps, tab_docs = st.tabs([f"복원한 절차 ({len(steps)}단계)", "자료와 최신본"])
            with tab_steps:
                if steps:
                    st.caption("단계와 근거 인용은 AI가 작성하고, 인용이 원문에 있는지는 코드가 검증합니다. 책임자가 고친 단계는 '책임자 확인'으로 표시됩니다.")
                    ui.handover_download(state, runner.log.run_id, key="dl-start")
                    ui.step_rows(steps, ui.docs_map(state), key="start")
                else:
                    ui.empty_state("아직 절차가 복원되지 않았습니다", "")
            with tab_docs:
                documents.render_body(state)
    if kind != "clarify_goal" and state.get("status") != "no_documents":
        ui.page_actions(info, pending)

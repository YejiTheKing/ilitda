"""화면 공통 상태: 실행(Runner) 열고 닫기, 에이전트 실시간 실행, 진행 단계 계산, 메뉴, 공개 모드 규칙, 가상 자료 소개.

업무 로직은 ilitda.agent에 있고 여기서는 부르기만 한다. 화면을 다시 그리는 것만으로 AI를 다시 부르지 않는다.
"""
import json
import os
import re
import secrets
import threading
import time
import uuid
from pathlib import Path

import streamlit as st

from ilitda.agent.runner import Runner
from ilitda.runlog import RUNS_DIR

# 공개 테스트 모드: 모르는 사람이 쓰는 링크. 실제 자료와 남의 실행을 숨기고 안내·피드백 화면을 켠다
PUBLIC = os.environ.get("ILITDA_PUBLIC") == "1"
FEEDBACK_DIR = Path("runs/feedback")
UPLOAD_DIR = Path("runs/uploads")          # 테스터가 올린 파일. 실행별 폴더. 저장소 제외
UPLOAD_TYPES = ["pdf", "docx", "xlsx", "hwpx", "hwp", "txt", "md"]
UPLOAD_MAX_FILES, UPLOAD_MAX_MB = 20, 10

# 인계 목표 문장 예시. 형식: [신규자]가 [업무 시작]부터 [업무 끝]까지 혼자 할 수 있게 인계해줘. 책임자는 [사람/역할].
GOAL_EXAMPLES = {
    "거래처·견적": "신규 입사한 박신입이 신규 거래처 등록부터 첫 견적서 발송까지 혼자 할 수 있게 인계해줘. 책임자는 이대표.",
    "영업·A/S": "신입 영업사원이 A/S 접수부터 수리 견적과 처리보고서 작성까지 혼자 할 수 있게 인계해줘. 책임자는 영업팀장.",
    "공정 관리": "신입 도장 공정 담당자가 협력사·설비·약품 관리 업무를 혼자 할 수 있게 인계해줘. 책임자는 도장 파트장.",
}
GOAL_FORMAT = "[신규자]가 [업무 시작]부터 [업무 끝]까지 혼자 할 수 있게 인계해줘. 책임자는 [사람 또는 역할]."
# 가상 자료 폴더별 기본 목표 문장
GOAL_BY_FOLDER = {
    "거래처등록_견적": GOAL_EXAMPLES["거래처·견적"],
    "출장비_정산": "신입 총무 담당 김신입이 출장비 정산 접수부터 입금 확인까지 혼자 할 수 있게 인계해줘. 책임자는 박팀장.",
    "비품_구매": "신입 총무 담당 김신입이 비품 구매 요청 접수부터 입고 확인까지 혼자 할 수 있게 인계해줘. 책임자는 박팀장.",
}


def default_goal(folder):
    return GOAL_BY_FOLDER.get(Path(folder).name if folder else "", GOAL_EXAMPLES["거래처·견적"])

# 메뉴. (키, 이름, 아이콘). 공개 모드에는 안내·피드백이 더 있다
MENU = [("start", "인계 시작", ":material/play_circle:"), ("owner", "확인 요청함", ":material/help:"),
        ("newcomer", "내 인계", ":material/checklist:"), ("log", "실행 로그", ":material/history:")]
MENU_PUBLIC = [("guide", "테스트 안내", ":material/info:")] + MENU + [("feedback", "피드백 남기기", ":material/rate_review:")]
PAGE_KEYS = {k for k, _, _ in MENU_PUBLIC}

KIND_LABEL = {"goal": "목표", "plan": "계획", "reasoning": "판단", "tool": "도구", "memory": "기억",
              "feedback": "검증", "human": "사람", "error": "오류"}
STATUS_LABEL = {None: "시작 전", "goal": "목표 해석", "planned": "계획 수립", "read": "자료 읽음", "no_documents": "자료 없음",
                "versions": "버전 정리", "procedure": "절차 복원", "answered": "확인 완료", "checklist": "체크리스트 생성",
                "handover": "수행 확인", "pending_approval": "승인 보류", "completed": "인계 완료"}
QUESTION_KIND = {"conflict": "자료 충돌", "gap": "자료 없음", "version": "최신본 불명", "unverified": "근거 미확인"}


# ---------- 실행 관리 ----------

def get_runner():
    return st.session_state.get("runner")


def current():
    """(runner, state, pending). 실행이 없으면 (None, {}, None)."""
    runner = get_runner()
    state = runner.state() if runner else {}
    return runner, state, st.session_state.get("pending")


def memory_path(run_id=None):
    """공개 모드에서는 브라우저 세션마다 기억 파일을 따로 쓴다. 비공개 모드는 공용 기억(기본값).

    여러 테스터가 같은 가상 자료로 테스트하면 앞사람의 답변이 뒷사람 질문에 제안으로 채워진다.
    세션별로 나누면 각자 질문을 전부 받고, 같은 세션에서 두 번째로 돌리면 이전 답변 제안(기억)이 보인다.
    """
    if not PUBLIC:
        # 비공개 모드는 공용 기억. ILITDA_MEMORY_PATH를 주면 그 파일을 쓴다 (시연 촬영처럼 깨끗한 기억이 필요할 때)
        custom = os.environ.get("ILITDA_MEMORY_PATH")
        return Path(custom) if custom else None
    marker = (RUNS_DIR / run_id / "memory_id") if run_id else None
    if marker and marker.exists():
        # 끊긴 실행을 다른 브라우저에서 다시 열어도 그 실행이 쓰던 기억 파일을 그대로 쓴다
        st.session_state["_sid"] = marker.read_text(encoding="utf-8").strip()
    if "_sid" not in st.session_state:
        st.session_state["_sid"] = uuid.uuid4().hex[:10]
    folder = RUNS_DIR / "_memory_public"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{st.session_state['_sid']}.sqlite"


def open_runner(run_id=None):
    old = st.session_state.get("runner")
    if old:
        old.close()
    runner = Runner(run_id=run_id, memory_path=memory_path(run_id))
    st.session_state["runner"] = runner
    st.session_state["pending"] = runner._pending() if run_id else None
    if PUBLIC:
        folder = RUNS_DIR / runner.log.run_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "memory_id").write_text(st.session_state["_sid"], encoding="utf-8")
        token = folder / "token"
        if not token.exists():
            # 실행 ID만으로는 남의 실행을 열 수 없게, 재개에는 이 토큰이 함께 필요하다
            token.write_text(secrets.token_hex(4), encoding="utf-8")
        if not run_id:
            runner.log.summarize(public=True, status=None)   # 첫 AI 호출 전에 끊겨도 본인은 다시 열 수 있게 공개 표시를 먼저 남긴다
    return runner


def resume_code(runner):
    """공개 모드에서 끊긴 실행을 다시 여는 코드: 실행ID.토큰"""
    token = RUNS_DIR / runner.log.run_id / "token"
    return f"{runner.log.run_id}.{token.read_text(encoding='utf-8').strip()}" if token.exists() else runner.log.run_id


def working():
    """에이전트 스레드가 아직 도는 중인지."""
    w = st.session_state.get("_worker")
    return bool(w and w[0].is_alive())


def go_home():
    """실행을 닫고 시작 화면으로. 위젯은 이미 그려진 뒤라 다음 실행 맨 앞에서 바꾼다."""
    if working():
        return
    runner = st.session_state.get("runner")
    if runner:
        runner.close()
    for key in ("runner", "pending", "_worker"):
        st.session_state.pop(key, None)
    st.session_state["_go_home"] = True
    st.rerun()


def goto(page):
    """다음 실행에서 화면을 바꾼다. 버튼 콜백 안에서 부른다."""
    st.session_state["_goto"] = page
    st.rerun()


def apply_deferred_navigation():
    if st.session_state.pop("_go_home", False):
        st.session_state["page"] = "start"
        st.session_state["run_choice"] = "(새 인계)"
        st.session_state["reopen_id"] = ""   # 남아 있으면 같은 실행이 바로 다시 열린다
    target = st.session_state.pop("_goto", None)
    if target in PAGE_KEYS:
        st.session_state["page"] = target
    if "page" not in st.session_state or st.session_state["page"] not in PAGE_KEYS:
        st.session_state["page"] = "guide" if PUBLIC else "start"


# ---------- 에이전트 실시간 실행 ----------

LIVE_TONE = {"goal": "info", "plan": "info", "reasoning": "gray", "tool": "gray", "memory": "info", "feedback": "ok", "human": "warn", "error": "danger"}


def live_line(entry):
    """실행 로그 한 줄을 실시간 창에 보여 줄 HTML."""
    import html as _html
    kind = entry.get("kind", "")
    title = _html.escape(str(entry.get("title", "")))
    detail = entry.get("detail")
    if isinstance(detail, list):
        detail = f"{len(detail)}개" if len(detail) > 2 else " · ".join(str(x) for x in detail)
    elif isinstance(detail, dict):
        detail = ""
    detail = _html.escape(str(detail or ""))[:140]
    extra = ""
    if entry.get("seconds") is not None:
        extra += f" · {entry['seconds']}초"
    if entry.get("replay"):
        extra += ' <span class="il-chip info">준비된 결과 재생</span>'
    label = KIND_LABEL.get(kind, kind)
    return (f'<div class="il-live"><span class="il-chip {LIVE_TONE.get(kind, "gray")}">{label}</span>'
            f'<span class="t">{title}</span><span class="d">{detail}{extra}</span></div>')


# 로그 제목으로 지금 어느 단계인지 알아낸다. (제목에 들어 있는 글자, 단계 이름, 진행률)
STAGE_MARKS = [("목표 해석", "목표 해석", 0.15), ("되물음", "목표 되물음", 0.15), ("계획 ", "계획 수립", 0.30),
               ("group_versions", "자료 읽기·버전 정리", 0.45), ("pick_latest", "최신본 판별", 0.50), ("diff_versions", "변경점 비교", 0.55),
               ("llm:classify_changes", "변경 영향 분류 (AI)", 0.60), ("llm:extract_procedure", "절차 복원 (AI)", 0.75),
               ("verify_evidence", "근거 실존 검증", 0.85), ("책임자 확인 요청", "책임자 확인 준비", 0.95),
               ("답변 저장", "답변 반영", 0.40), ("미확정으로 표시", "답변 반영", 0.40), ("llm:build_checklist", "체크리스트 생성 (AI)", 0.75),
               ("build_checklist", "체크리스트 정리", 0.90), ("신규자 수행 확인 요청", "수행 확인 준비", 0.95),
               ("책임자 승인 요청", "승인 요청 준비", 0.95), ("인계 완료 판정", "완료 판정", 1.0)]


def _stage(entries, since):
    """이번 실행에서 새로 쌓인 로그(since 이후)를 보고 (단계 이름, 진행률)."""
    label, frac = "시작", 0.05
    for e in entries[since:]:
        title = str(e.get("title", ""))
        for mark, name, f in STAGE_MARKS:
            if mark in title and f >= frac:
                label, frac = name, f
    return label, frac


def _pour(box, runner, seen):
    """새로 쌓인 로그를 실시간 창에 붓는다. 쓰는 도중의 반 줄은 다음 번에 읽는다."""
    if not runner:
        return seen, []
    try:
        entries = runner.log.read()
    except ValueError:
        return seen, []
    for e in entries[seen:]:
        box.html(live_line(e))
    return len(entries), entries


def _watch(worker, result, runner, message):
    """에이전트 스레드가 끝날 때까지 진행 막대와 로그를 실시간으로 보여 주고, 끝나면 멈춘 자리(pending)를 저장해 다시 그린다."""
    folder = (runner.state() or {}).get("folder", "") if runner else ""
    hint = "올린 파일은 보통 1~2분 걸립니다." if "uploads" in folder else ("실제 자료는 1~2분 걸릴 수 있습니다." if "real" in folder else "")
    box = st.status(message, expanded=True)
    bar = box.progress(0.05, text="접수됨 · 시작하는 중")
    if hint:
        box.caption(hint + " 이 창을 닫거나 다른 화면으로 가도 작업은 계속됩니다.")
    start_seen = len(runner.log.read()) if runner else 0
    seen, entries = _pour(box, runner, 0)
    started = time.time()
    while worker.is_alive():
        seen, entries = _pour(box, runner, seen)
        label, frac = _stage(entries, start_seen)
        bar.progress(min(frac, 0.98), text=f"{label} · {time.time() - started:.0f}초")
        time.sleep(0.35)
    _pour(box, runner, seen)
    bar.progress(1.0, text=f"완료 · {time.time() - started:.0f}초")
    pending = result.get("pending")
    st.session_state["pending"] = pending
    st.session_state.pop("_worker", None)
    _release_all()
    failed = bool(pending and pending.get("type") == "error")
    box.update(label=f"{'오류로 멈춤' if failed else '에이전트 작업 완료'} · {time.time() - started:.0f}초",
               state="error" if failed else "complete", expanded=False)
    st.rerun()


def run_and_wait(fn, message):
    """에이전트를 다른 스레드에서 돌리고, 그동안 실행 로그를 그대로 보여 준다. fn은 Runner의 start/resume/retry."""
    runner = get_runner()
    result = {}

    def work():
        try:
            result["pending"] = fn()
        except Exception as e:  # 예상 못 한 오류도 화면에 그대로. 상태는 체크포인트에 남아 있다
            result["pending"] = {"type": "error", "message": f"실행 중 오류: {e}"}
        result["done"] = True

    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    st.session_state["_worker"] = (worker, result, runner.log.run_id if runner else None)
    _watch(worker, result, runner, message)


def _release_all():
    """'처리 중…'으로 잠긴 버튼을 모두 되돌린다."""
    for k in [k for k in st.session_state if str(k).startswith("_busy_")]:
        del st.session_state[k]


def attach_worker():
    """화면이 다시 그려졌는데 에이전트가 아직 돌고 있으면 다시 붙어서 기다린다. 끝났으면 결과를 받는다."""
    w = st.session_state.get("_worker")
    if not w:
        return
    worker, result, rid = w
    runner = get_runner()
    if not runner or runner.log.run_id != rid:
        st.session_state.pop("_worker", None)
        return
    if worker.is_alive():
        _watch(worker, result, runner, "에이전트가 작업 중입니다…")
    else:
        st.session_state["pending"] = result.get("pending") if result.get("done") else (runner._pending() if runner else None)
        st.session_state.pop("_worker", None)
        _release_all()


def list_runs():
    if not RUNS_DIR.exists():
        return []
    return sorted((p.name for p in RUNS_DIR.iterdir() if p.is_dir() and not p.name.startswith("_") and p.name[:4].isdigit()),
                  reverse=True)


def run_summary(run_id):
    path = RUNS_DIR / run_id / "summary.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except ValueError:
        return {}


def run_label(run_id):
    """실행 ID 대신 '10/03 16:19 · 업무 · 자료 출처 · 상태'처럼 보여준다."""
    if run_id == "(새 인계)":
        return run_id
    info = run_summary(run_id)
    when = f"{run_id[4:6]}/{run_id[6:8]} {run_id[9:11]}:{run_id[11:13]}"
    task = (info.get("task") or "(목표 해석 전)")[:16]
    return f"{when} · {task} · {info.get('source', '?')} · {STATUS_LABEL.get(info.get('status'), info.get('status') or '-')}"


def can_reopen(code):
    """공개 모드에서 재개 코드(실행ID.토큰)로 다시 열 수 있는지. 형식·공개 표시·토큰이 모두 맞아야 한다. 맞으면 실행 ID."""
    m = re.fullmatch(r"(\d{8}-\d{6}-[0-9a-f]{6,12})\.([0-9a-f]{8})", code.strip())
    if not m:
        return None
    run_id, token = m.group(1), m.group(2)
    if run_summary(run_id).get("public") is not True:
        return None
    saved = RUNS_DIR / run_id / "token"
    if not saved.exists() or not secrets.compare_digest(saved.read_text(encoding="utf-8").strip(), token):
        return None
    return run_id


# ---------- 자료 폴더 ----------

def sample_folders():
    """허용된 폴더(ILITDA_ALLOWED_DIRS) 아래의 업무 폴더. 테스터 업로드 폴더는 목록에 올리지 않는다."""
    from ilitda.safety.paths import allowed_dirs

    out = []
    for base in allowed_dirs():
        if base.resolve() == UPLOAD_DIR.resolve():
            continue
        if base.exists():
            out += [str(p.relative_to(Path.cwd())) if p.is_relative_to(Path.cwd()) else str(p)
                    for p in sorted(base.iterdir()) if p.is_dir()]
    return out


def is_sample_folder(folder):
    try:
        return bool(folder) and Path(folder).resolve().is_relative_to(Path("data/sample").resolve())
    except (OSError, ValueError, RuntimeError):
        return False


def sample_intro(folder):
    """가상 자료 폴더 옆의 '소개_<폴더명>.md'를 절(## 제목) 단위로. 폴더 밖에 두어 에이전트는 읽지 못한다."""
    if not is_sample_folder(folder):
        return {}
    path = Path(folder).parent / f"소개_{Path(folder).name}.md"
    if not path.exists():
        return {}
    sections, title, buf = {}, None, []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            if title:
                sections[title] = "\n".join(buf).strip()
            title, buf = line[3:].strip(), []
        else:
            buf.append(line)
    if title:
        sections[title] = "\n".join(buf).strip()
    return sections


def intro_section(intro, prefix):
    return next((body for title, body in intro.items() if title.startswith(prefix)), "")


def sample_facts(state):
    """가상 자료 실행이면 정답 메모('이대표가 아는 사실' 절) 본문, 아니면 빈 문자열."""
    return intro_section(sample_intro(state.get("folder", "")), "이대표가 아는 사실")


def folder_files(folder):
    """폴더 안 파일 목록 [{name, size, ext}]. 설정 파일(.json)과 숨김 파일은 뺀다."""
    p = Path(folder) if folder else None
    if not p or not p.is_dir():
        return []
    out = []
    for f in sorted(p.iterdir()):
        if f.is_file() and not f.name.startswith((".", "~$")) and f.suffix != ".json":
            out.append({"name": f.name, "size": f.stat().st_size, "ext": f.suffix.lstrip(".").lower()})
    return out


@st.cache_data(show_spinner=False)
def zip_folder(folder):
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in folder_files(folder):
            z.write(Path(folder) / f["name"], f["name"])
    return buf.getvalue()


def fmt_size(n):
    if n is None:
        return ""
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n / 1024 / 1024:.1f} MB"


def source_label(folder):
    if not folder:
        return ""
    if "uploads" in folder:
        return "올린 파일"
    if "real" in folder:
        return "실제 자료"
    return "가상 자료"


# ---------- 진행 단계 ----------

STAGES = ["자료 읽기", "책임자 확인", "절차 정리", "신규자 수행", "책임자 승인"]
MID_STATUSES = ("goal", "planned", "read", "versions", "procedure", "answered", "checklist", "handover", "pending_approval")


def open_question_count(pending):
    """메뉴와 상단에 보이는 '지금 답해야 할 요청' 수. 실제 pending 데이터에서 센다."""
    if not pending:
        return 0
    if pending["type"] == "ask_owner":
        return len(pending.get("questions", []))
    if pending["type"] in ("owner_approval", "clarify_goal"):
        return 1
    return 0


def checklist_progress(state, pending=None):
    """체크리스트 진행 수치. (필수 완료, 필수 전체, 전체 완료, 전체)."""
    items = (pending or {}).get("checklist") if pending and pending.get("type") in ("newcomer_progress", "owner_approval") else None
    items = items or state.get("checklist") or []
    prog = (pending or {}).get("progress") if pending and "progress" in (pending or {}) else state.get("progress", {})
    prog = prog or {}
    req = [i for i in items if i.get("required")]
    done = lambda i: bool(prog.get(str(i["order"]), {}).get("done"))
    return sum(1 for i in req if done(i)), len(req), sum(1 for i in items if done(i)), len(items)


def stage_info(state, pending):
    """지금 어디까지 됐고 무엇을 해야 하는지.

    {"index": 현재 단계(0~4, 끝나면 5), "blocked": 오류 여부, "headline": 한 줄, "detail": 보조 설명,
     "primary": (버튼 이름, 동작), "secondary": [(버튼 이름, 동작)...]}
    동작: ("page", 화면 키) / ("retry",) / ("home",) / None
    """
    status = state.get("status")
    approval = state.get("approval") or {}
    kind = pending["type"] if pending else None
    info = {"index": 0, "blocked": False, "headline": "", "detail": "", "primary": None, "secondary": []}

    if kind == "error":
        err = classify_error(pending.get("message", ""))
        info.update(index=_index_from_status(status), blocked=True, headline=err["title"] + ". 진행 상태는 저장되어 있어 같은 자리에서 이어 갈 수 있습니다.",
                    detail=err["body"], primary=("다시 시도", ("retry",)) if err["retry"] else ("새 인계 시작", ("home",)),
                    secondary=[("새 인계 시작", ("home",))] if err["retry"] else [])
        return info
    if status == "no_documents":
        info.update(index=0, blocked=True, headline="읽을 수 있는 자료가 없어 멈췄습니다.",
                    detail="PDF, Word, Excel, 한글(hwp·hwpx), 텍스트 파일을 넣고 다시 시작하세요.", primary=("새 인계 시작", ("home",)))
        return info
    if kind == "clarify_goal":
        info.update(index=0, headline="목표 문장에 빠진 정보가 있어 에이전트가 묻고 있습니다.",
                    detail="업무 이름과 신규자를 알려 주면 자료를 읽기 시작합니다.", primary=("질문에 답하기", ("page", "start")))
        return info
    if kind == "ask_owner":
        n = len(pending.get("questions", []))
        headline = (f"자료만으로 정할 수 없는 항목 {n}건, 책임자 확인이 필요합니다." if n else "확인할 질문은 없습니다. 복원된 절차를 검토하고 보내 주세요.")
        info.update(index=1, headline=headline, detail="답을 보내면 절차가 정리되고 체크리스트가 만들어집니다. 모르는 항목은 비워 두면 '미확정'으로 남습니다.",
                    primary=(f"확인 질문 {n}건 답하기" if n else "절차 검토하고 보내기", ("page", "owner")))
        return info
    if kind == "newcomer_progress":
        rd, rt, _, _ = checklist_progress(state, pending)
        held = approval.get("approved") is False
        info["index"] = 3
        if held:
            info.update(headline="책임자가 승인을 보류했습니다. 보완한 뒤 다시 승인을 요청하세요.",
                        detail=f"보류 사유: {approval.get('note') or '(없음)'}")
        else:
            info.update(headline="절차가 정리되었습니다. 신규자가 체크리스트대로 수행할 차례입니다.",
                        detail=f"필수 항목 {rd}/{rt} 완료. 필수 항목을 모두 저장하면 책임자 승인 요청으로 넘어갑니다.")
        info.update(primary=("체크리스트 보기", ("page", "newcomer")), secondary=[("피드백 남기기", ("page", "feedback"))] if PUBLIC else [])
        return info
    if kind == "owner_approval":
        inc = len(pending.get("incomplete", []))
        info.update(index=4, headline="책임자 승인을 기다리고 있습니다.",
                    detail=("미완료 필수 항목이 없습니다. 승인하면 인계가 완료됩니다." if not inc else f"미완료 필수 항목 {inc}개가 있어 승인할 수 없습니다. 보류하고 보완을 요청하세요."),
                    primary=("승인 결정하기", ("page", "owner")))
        return info
    if status == "completed":
        _, _, cd, ct = checklist_progress(state)
        info.update(index=5, headline="인계가 완료되었습니다.", detail=f"책임자 승인 완료 · 체크리스트 {cd}/{ct}",
                    primary=("피드백 남기기", ("page", "feedback")) if PUBLIC else ("새 인계 시작", ("home",)),
                    secondary=[("새 인계 시작", ("home",))] if PUBLIC else [])
        return info
    if status in MID_STATUSES:
        # 멈춤 정보가 없는데 끝나지도 않았다: 서버 재시작 등으로 끊긴 실행. 체크포인트에서 이어 갈 수 있다
        info.update(index=_index_from_status(status), blocked=True, headline="실행이 도중에 끊겼습니다. 저장된 자리부터 이어 갈 수 있습니다.",
                    detail=f"마지막 상태: {STATUS_LABEL.get(status, status)}", primary=("이어서 진행", ("retry",)), secondary=[("새 인계 시작", ("home",))])
        return info
    info.update(index=0, headline="자료를 읽고 절차를 복원하는 중입니다.")
    return info


def _index_from_status(status):
    if status in (None, "goal", "planned", "read", "versions", "procedure"):
        return 0
    if status == "answered":
        return 2
    if status in ("checklist", "handover", "pending_approval"):
        return 3
    if status == "completed":
        return 5
    return 0


def review_state(state, pending):
    """자료 검수(책임자 확인) 상태. ('done'|'pending'|'none', 설명)."""
    answers = state.get("answers")
    if answers is not None and (not pending or pending["type"] != "ask_owner"):
        owner = sum(1 for a in answers if a["source"] == "owner")
        mem = sum(1 for a in answers if a["source"] == "memory" or a.get("from_suggestion"))
        unres = sum(1 for a in answers if a["source"] == "unresolved")
        parts = [f"책임자 답변 {owner}"] + ([f"이전 답변 확인 {mem}"] if mem else []) + ([f"미확정 {unres}"] if unres else [])
        return "done", "책임자 확인 완료 · " + " · ".join(parts)
    if pending and pending["type"] == "ask_owner":
        return "pending", f"책임자 확인 대기 · 질문 {len(pending.get('questions', []))}건"
    return "none", "확인 전"


# ---------- 오류 분류 ----------

def classify_error(message):
    """에이전트가 돌려준 오류 문구를 사람이 할 일로 바꾼다. {"title", "body", "retry", "kind"}"""
    m = message or ""
    if "길이 한도" in m:
        return {"kind": "length", "title": "응답이 길이 한도에 걸려 잘렸습니다",
                "body": "같은 자리에서 다시 시도하면 대개 지나갑니다. 반복되면 파일 수를 줄이거나 긴 파일을 나눠 다시 시작하세요.", "retry": True}
    if "호출 한도(" in m:
        return {"kind": "cap", "title": "오늘의 AI 호출 한도에 도달했습니다",
                "body": "이 링크는 하루에 쓸 수 있는 AI 호출 횟수가 정해져 있습니다. 가상 자료는 계속 쓸 수 있고, 올린 파일은 내일 다시 시도할 수 있습니다.",
                "retry": False}
    if re.search(r"API 오류 (401|403)|authentication|invalid x-api-key|api_key", m, re.I):
        return {"kind": "auth", "title": "AI 서비스 인증에 실패했습니다",
                "body": "API 키가 없거나 올바르지 않습니다. 운영자가 .env의 ANTHROPIC_API_KEY를 확인해야 합니다. 키를 고친 뒤 같은 자리에서 이어 갈 수 있습니다.",
                "retry": True}
    if "연결 실패" in m or "Connection" in m or "timed out" in m.lower():
        return {"kind": "network", "title": "AI 서비스에 연결하지 못했습니다",
                "body": "네트워크 연결을 확인한 뒤 다시 시도하세요. 같은 자리에서 이어 갑니다.", "retry": True}
    if re.search(r"API 오류 (429|5\d\d)|overloaded", m, re.I):
        return {"kind": "service", "title": "AI 서비스가 잠시 응답하지 못했습니다",
                "body": "요청이 몰리거나 서비스 쪽 문제입니다. 잠시 뒤 다시 시도하세요.", "retry": True}
    if "자료 폴더" in m or "허용되지 않은 경로" in m:
        return {"kind": "folder", "title": "자료 폴더를 읽을 수 없습니다", "body": m, "retry": False}
    return {"kind": "other", "title": "처리 중 오류가 났습니다", "body": m, "retry": True}

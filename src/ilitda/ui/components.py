"""화면 조각. 모든 화면이 같은 것을 같은 모양으로 그린다.

HTML은 우리가 직접 만든 il-* 클래스만 쓰고, 사용자 데이터는 전부 escape 한다.
"""
import html
from contextlib import contextmanager
from difflib import SequenceMatcher

import streamlit as st

from ilitda.tools.evidence import _squash
from ilitda.ui import session

TONE = {"ok": "ok", "warn": "warn", "danger": "danger", "info": "info", "gray": "gray", "": ""}


def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


def chip(text, tone=""):
    return f'<span class="il-chip {TONE.get(tone, "")}">{esc(text)}</span>'


@contextmanager
def card(key):
    """흰 표면 카드. key는 화면 안에서 유일해야 한다."""
    with st.container(key=f"card-{key}"):
        yield


def section(title, right=""):
    st.html(f'<div class="il-sec"><h3>{esc(title)}</h3><span class="r">{right}</span></div>')


def note(text, tone="", title=""):
    t = f'<span class="t">{esc(title)}</span>' if title else ""
    st.html(f'<div class="il-note {TONE.get(tone, "")}">{t}{esc(text)}</div>')


def empty_state(title, body=""):
    st.html(f'<div class="il-empty"><div class="t">{esc(title)}</div><div class="b">{esc(body)}</div></div>')


def kv(pairs):
    """[(이름, 값)] → 한 줄 메타 정보."""
    st.html('<div class="il-kv">' + "".join(f"<span>{esc(k)} <b>{esc(v)}</b></span>" for k, v in pairs if v) + "</div>")


def stepper_html(index, blocked=False):
    parts = []
    for i, name in enumerate(session.STAGES):
        cls = "done" if i < index else ("current" if i == index else "")
        if blocked and i == index:
            cls = "blocked"
        mark = "✓" if i < index else ("!" if cls == "blocked" else str(i + 1))
        parts.append(f'<span class="il-step {cls}"><span class="n">{mark}</span>{esc(name)}{" · 멈춤" if cls == "blocked" else ""}</span>')
    return '<div class="il-stepper">' + "".join(parts) + "</div>"


def run_action(action):
    """상단 띠·버튼의 동작을 실행한다."""
    if not action:
        return
    kind = action[0]
    if kind == "page":
        session.goto(action[1])
    elif kind == "home":
        session.go_home()
    elif kind == "retry":
        runner = session.get_runner()
        if runner:
            session.run_and_wait(lambda: runner.retry(), "저장된 자리부터 이어 가는 중…")


def page_header(state, pending, meta=None, key="pagehead"):
    """상단 띠: 업무명, 진행 단계, 지금 할 일과 주 행동. 모든 실행 화면이 같은 것을 쓴다."""
    info = session.stage_info(state, pending)
    goal = state.get("goal") or {}
    task = goal.get("task") or (state.get("goal_text") or "").strip()[:60] or "목표 해석 중"
    with st.container(key=key):
        st.html(f'<div class="il-title">{esc(task)}</div>' + stepper_html(info["index"], info["blocked"]))
        st.html(f'<div class="il-lead">{esc(info["headline"])}</div>'
                + (f'<div class="il-sub">{esc(info["detail"])}</div>' if info["detail"] else ""))
        if meta:
            kv(meta)
    return info


def page_actions(info, pending=None, key="pageact"):
    """화면 맨 아래의 행동 버튼 줄. 버튼은 위 띠가 아니라 내용 다음에 온다.

    지금 보고 있는 화면으로 가는 버튼은 아무 일도 하지 않으므로 그리지 않는다. 오류 화면은 오류 상자가 버튼을 가진다.
    """
    if not info or (pending and pending.get("type") == "error"):
        return
    here = ("page", st.session_state.get("page"))
    actions = [(label, a, "primary") for label, a in [info["primary"]] if info["primary"] and a != here]
    actions += [(label, a, "secondary") for label, a in info["secondary"] if a != here]
    if actions:
        with st.container(horizontal=True, gap="small", key=f"{key}-actions"):
            for i, (label, action, kind) in enumerate(actions):
                if st.button(label, type=kind, key=f"{key}-{kind}-{i}"):
                    run_action(action)


def error_panel(pending, key="error"):
    """오류 종류별 안내와 다음 행동. 한도·인증·연결을 구분한다."""
    err = session.classify_error(pending.get("message", ""))
    with card(key):
        st.html(f'<div class="il-note danger">{esc(err["body"])}</div>')
        with st.expander("오류 원문"):
            st.code(pending.get("message", ""), language=None, wrap_lines=True)
        with st.container(horizontal=True, gap="small"):
            runner = session.get_runner()
            if err["retry"] and runner and st.button("다시 시도", type="primary", key=f"{key}-retry"):
                session.run_and_wait(lambda: runner.retry(), "저장된 자리부터 다시 시도하는 중…")
            if st.button("새 인계 시작", key=f"{key}-home"):
                session.go_home()
    return err


# ---------- 근거 ----------

def locate(text, quote):
    """인용문이 원문 몇 번째 줄에 있는지. {"line": 1부터, "text", "before", "after", "ratio"} 또는 None."""
    if not text or not quote:
        return None
    lines = text.splitlines()
    q = _squash(quote)
    if not q:
        return None
    best, best_i = 0.0, None
    for i, ln in enumerate(lines):
        sq = _squash(ln)
        if not sq:
            continue
        if q in sq or (len(sq) >= 8 and sq in q):
            best, best_i = 1.0, i
            break
        r = SequenceMatcher(None, q, sq).ratio()
        if r > best:
            best, best_i = r, i
    if best_i is None or best < 0.5:
        return None
    return {"line": best_i + 1, "text": lines[best_i], "before": lines[best_i - 1] if best_i > 0 else "",
            "after": lines[best_i + 1] if best_i + 1 < len(lines) else "", "ratio": round(best, 2)}


def evidence_html(ev, docs_by_name):
    """근거 하나: 문서명, 원문 인용, 원문 속 위치."""
    found = ev.get("found", True)
    doc = ev.get("doc", "")
    loc = locate(docs_by_name.get(doc, ""), ev.get("quote", "")) if found and doc in docs_by_name else None
    where = f"원문 {loc['line']}행" if loc else ("책임자가 직접 확인한 내용" if doc == "책임자 확인" else ("원문에서 찾지 못함" if not found else ""))
    status = chip("원문 확인", "ok") if found else chip(ev.get("why") or "원문 미확인", "danger")
    return (f'<div class="il-ev {"ok" if found else "bad"}"><span class="doc">{esc(doc)}</span> {status}'
            f'<q>{esc(ev.get("quote", ""))}</q><span class="loc">{esc(where)}</span></div>')


def source_view(docs_by_name, doc, quote, key):
    """'원문 보기': 문서 이름, 인용이 있는 줄과 앞뒤 줄을 그대로 보여 준다."""
    text = docs_by_name.get(doc)
    if text is None:
        st.caption("이 문서의 원문은 실행 기록에 없습니다.")
        return
    loc = locate(text, quote)
    if not loc:
        st.caption("원문에서 이 문장을 찾지 못했습니다. 아래는 문서 앞부분입니다.")
        st.html(f'<div class="il-src">{esc(text[:600])}</div>')
        return
    body = (f"{esc(loc['before'])}\n" if loc["before"] else "") + f'<span class="hit">{esc(loc["text"])}</span>' + (f"\n{esc(loc['after'])}" if loc["after"] else "")
    st.html(f'<div class="il-small">{esc(doc)} · {loc["line"]}행 앞뒤</div><div class="il-src">{body}</div>')


def evidence_block(evidence, docs_by_name, key):
    """단계 하나의 근거 목록 + 원문 보기."""
    if not evidence:
        st.caption("근거가 없습니다.")
        return
    st.html("".join(evidence_html(ev, docs_by_name) for ev in evidence))
    viewable = [ev for ev in evidence if ev.get("doc") in docs_by_name]
    if viewable:
        pick = st.selectbox("원문 보기", [f"{i + 1}. {ev['doc']}" for i, ev in enumerate(viewable)], key=f"{key}-src",
                            label_visibility="collapsed")
        ev = viewable[int(pick.split(".")[0]) - 1]
        source_view(docs_by_name, ev["doc"], ev.get("quote", ""), key)


def step_status(step):
    if step.get("edited_by"):
        return chip(f"책임자 확인 · {step['edited_by']}", "info")
    if step.get("status") == "ok":
        n = sum(1 for e in step.get("evidence", []) if e.get("found"))
        return chip(f"근거 확인 {n}건", "ok")
    return chip("근거 미확인", "warn")


def step_rows(steps, docs_by_name, key, progress=None, checklist_by_step=None):
    """업무 절차 표: 번호, 해야 할 일, 담당·양식, 근거, 확인 상태. 긴 문장도 자르지 않는다."""
    for i, s in enumerate(steps):
        tone = "" if s.get("status") == "ok" else "warn"
        meta = []
        if s.get("who"):
            meta.append(f"담당 <b>{esc(s['who'])}</b>")
        if s.get("form"):
            meta.append(f"양식 <b>{esc(s['form'])}</b>")
        if s.get("confidence"):
            meta.append(f"확신 {esc(s['confidence'])}")
        st.html(f'<div class="il-row {"first" if i == 0 else ""}"><div class="il-num {tone}">{s.get("order", i + 1)}</div>'
                f'<div class="il-body"><div class="il-main">{esc(s.get("action", ""))}</div>'
                f'<div class="il-meta">{" · ".join(meta)}{" · " if meta else ""}{step_status(s)}</div></div></div>')
        ev = s.get("evidence", [])
        label = f"근거 {len(ev)}건" + ("" if s.get("status") == "ok" else " · 자료에서 확인되지 않아 책임자 확인이 필요합니다")
        with st.expander(label):
            evidence_block(ev, docs_by_name, key=f"{key}-ev-{s.get('order', i)}")


def docs_map(state):
    return {d["name"]: d.get("text", "") for d in state.get("documents", [])}


def change_html(c):
    tone = {"서식": "gray", "기준값": "info", "절차": "warn", "담당": "warn"}.get(c.get("type"), "gray")
    head = chip(c.get("type", "변경"), tone) + (chip("업무에 영향", "warn") if c.get("matters") else chip("참고", "gray"))
    diff = ""
    if c.get("old") or c.get("new"):
        diff = (f'<div class="il-diff"><div><span class="lab">변경 전 · {esc(c.get("old_doc", ""))}</span><span class="old">{esc(c.get("old") or "(없음)")}</span></div>'
                f'<div><span class="lab">변경 후 · {esc(c.get("family", ""))}</span>{esc(c.get("new") or "(삭제)")}</div></div>')
    return (f'<div class="il-row"><div class="il-body"><div class="il-main">{head} {esc(c.get("summary", ""))}</div>'
            f'<div class="il-meta">영향: {esc(c.get("impact", ""))}</div>{diff}</div></div>')


def handover_download(state, run_id, key):
    """복원된 절차를 인수인계서(Word)로 내려받는 버튼. 절차가 있을 때만."""
    if not state.get("steps"):
        return
    from ilitda.ui.handover_doc import build_docx, file_name
    st.download_button("인수인계서 내려받기 (Word)", build_docx(state, run_id), file_name=file_name(state, run_id),
                       mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=key,
                       icon=":material/download:", help="절차·책임자 확인·최신 양식·체크리스트를 한 문서로. 미확정 항목은 표시됩니다.")


def busy_button(label, key, busy_label="처리 중…", **kwargs):
    """누르면 그 자리에서 비활성화되고 '처리 중…'으로 바뀌는 버튼. 한 번만 True를 돌려준다.

    Streamlit은 버튼의 글자나 활성 상태가 바뀌면 같은 실행에서 눌림을 돌려주지 않으므로, on_click에서 표시한 깃발을 신호로 쓴다.
    작업이 끝나면 session.run_and_wait가 깃발을 지워 버튼이 돌아온다. 검증에 실패하면 release(key)로 되돌린다.
    """
    flag = f"_busy_{key}"

    def _mark():
        st.session_state[flag] = "pending"

    state = st.session_state.get(flag)
    disabled = kwargs.pop("disabled", False) or bool(state)
    st.button(busy_label if state else label, key=key, disabled=disabled, on_click=_mark, **kwargs)
    if state == "pending":
        st.session_state[flag] = "running"
        return True
    return False


def release(key):
    """busy_button을 다시 누를 수 있게 되돌린다 (검증 실패 등)."""
    st.session_state.pop(f"_busy_{key}", None)


def next_hint_button(info, key):
    """상단 띠가 없는 자리에서 쓰는 '다음 행동' 버튼 하나."""
    if info and info.get("primary"):
        label, action = info["primary"]
        if st.button(label, type="primary", key=key):
            run_action(action)

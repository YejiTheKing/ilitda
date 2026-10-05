"""자료와 최신본: 읽은 파일을 최신 후보 / 책임자 확인 / 이전 버전 / 읽기 실패로 구분하고, 변경 전·후와 영향을 보여 준다. (탭 안에서 쓰는 조각)"""
import streamlit as st

from ilitda.ui import components as ui
from ilitda.ui import session

ROLE = {"form": ("빈 양식", "gray"), "record": ("작성 기록", "gray")}


def render_body(state):
    docs = state.get("documents", [])
    unreadable = state.get("unreadable", [])
    versions = state.get("versions", [])
    sizes = {f["name"]: f["size"] for f in session.folder_files(state.get("folder"))}
    latest = {v["latest"]: v for v in versions}
    older = {n: v["latest"] for v in versions for n in v["family"] if n != v["latest"]}

    total = len(docs) + len(unreadable)
    ui.section(f"파일 {total}개", ui.chip(f"읽음 {len(docs)}", "ok") + (ui.chip(f"읽기 실패 {len(unreadable)}", "danger") if unreadable else ""))
    if not docs and not unreadable:
        ui.empty_state("아직 읽은 자료가 없습니다", "")
        return
    if unreadable:
        ui.note(f"파일 {len(unreadable)}개를 읽지 못해 나머지 {len(docs)}개로 절차를 복원했습니다. 읽지 못한 파일의 내용은 책임자 확인이 필요합니다.", "warn")
    groups = [
        ("최신 후보", [d for d in docs if d["name"] in latest and latest[d["name"]]["confident"]], "info"),
        ("책임자 확인 필요", [d for d in docs if d["name"] in latest and not latest[d["name"]]["confident"]], "warn"),
        ("단일 자료", [d for d in docs if d["name"] not in latest and d["name"] not in older], "gray"),
        ("이전 버전", [d for d in docs if d["name"] in older], "gray"),
    ]
    first = True
    for label, items, tone in groups:
        for d in items:
            role, rtone = ROLE.get(d.get("role", ""), ("", "gray"))
            meta = [ui.chip(label, tone)]
            if role:
                meta.append(ui.chip(role, rtone))
            if d["name"] in older:
                meta.append(f"최신본: <b>{ui.esc(older[d['name']])}</b>")
            size = sizes.get(d["name"])
            tail = f" · {ui.esc(d.get('ext', '').lstrip('.').upper())}" + (f" · {session.fmt_size(size)}" if size else "") + f" · {len(d.get('text', ''))}자"
            st.html(f'<div class="il-row {"first" if first else ""}"><div class="il-body"><div class="il-main" style="font-weight:600">{ui.esc(d["name"])}</div>'
                    f'<div class="il-meta">{" ".join(meta)}{tail}</div></div></div>')
            first = False
            if d["name"] in latest:
                v = latest[d["name"]]
                with st.expander(f"최신본 판별 근거 {len(v['evidence'])}건 · 비교한 파일 {len(v['family'])}개 · 코드 규칙(수정 날짜 불사용)"):
                    st.html("".join(f'<div class="il-meta">· {ui.esc(e)}</div>' for e in v["evidence"])
                            + f'<div class="il-meta">비교: {ui.esc(", ".join(v["family"]))}</div>')
                    if not v["confident"]:
                        ui.note("판별 근거가 서로 같아 확정하지 않았습니다. 확인 요청함에서 책임자가 최신본을 지정합니다.", "warn")
    for u in unreadable:
        st.html(f'<div class="il-row"><div class="il-body"><div class="il-main" style="font-weight:600">{ui.esc(u["name"])}</div>'
                f'<div class="il-meta">{ui.chip("읽기 실패", "danger")} {ui.esc(u["reason"])}</div></div></div>')
    st.html('<div style="height:8px"></div>')
    render_changes(state)


def render_changes(state):
    versions = state.get("versions", [])
    changes = state.get("changes", [])
    docs_by_name = ui.docs_map(state)
    matters = [c for c in changes if c.get("matters")]
    ui.section(f"변경점 {len(changes)}건", (ui.chip(f"업무에 영향 {len(matters)}", "warn") if matters else "") + ui.chip("비교: 코드", "gray") + ui.chip("영향 분류: AI", "info"))
    if not versions:
        ui.empty_state("비교할 버전 묶음이 없습니다", "같은 양식의 버전이 2개 이상 있을 때 최신본 판별과 변경 전·후 비교가 생깁니다.")
        return
    if not changes:
        ui.empty_state("버전 사이에 내용 차이가 없습니다", "묶인 파일들의 내용이 같습니다(사본 등).")
        return
    for v in versions:
        st.html(f'<div class="il-meta">최신 양식 <b>{ui.esc(v["latest"])}</b> (구버전: {ui.esc(", ".join(n for n in v["family"] if n != v["latest"]) or "없음")})</div>')
    ordered = matters + [c for c in changes if not c.get("matters")]
    for i, c in enumerate(ordered):
        st.html(ui.change_html(c))
        with st.expander("근거 보기 — 두 문서의 원문"):
            col1, col2 = st.columns(2)
            with col1:
                if c.get("old") and c.get("old_doc") in docs_by_name:
                    ui.source_view(docs_by_name, c["old_doc"], c["old"], key=f"chg-old-{i}")
                else:
                    st.caption(f"{c.get('old_doc', '')}: 이전 버전에는 이 항목이 없습니다.")
            with col2:
                if c.get("new") and c.get("family") in docs_by_name:
                    ui.source_view(docs_by_name, c["family"], c["new"], key=f"chg-new-{i}")
                else:
                    st.caption(f"{c.get('family', '')}: 최신본에서 이 항목이 빠졌습니다.")

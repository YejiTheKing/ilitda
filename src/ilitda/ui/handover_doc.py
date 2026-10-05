"""복원된 절차를 신입이 일하면서 보는 인수인계서(Word)로 만든다.

실행 상태(state)만 받아서 만든다. 매뉴얼처럼 절차만 적는다. 출처·근거·변경 전후·체크리스트·실행 ID는 넣지 않는다.
근거가 없는 단계와 책임자가 답하지 않은 항목은 '확인할 것'에 "~ 확인하기" 꼴로 짧게 모은다.
"""
import io
import re
from datetime import datetime

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

FONT = "Malgun Gothic"


def _doc():
    d = Document()
    for s in d.sections:
        s.top_margin = s.bottom_margin = Cm(2)
        s.left_margin = s.right_margin = Cm(2)
    st = d.styles["Normal"]
    st.font.name = FONT
    st.font.size = Pt(10.5)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    for name in ("Heading 1",):
        h = d.styles[name]
        h.font.name = FONT
        h.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    d.styles["Heading 1"].font.size = Pt(13)
    return d


def _widths(table, widths_cm):
    table.autofit = False
    for row in table.rows:
        for cell, w in zip(row.cells, widths_cm):
            cell.width = Cm(w)
            tcPr = cell._tc.get_or_add_tcPr()
            tcW = OxmlElement("w:tcW")
            tcW.set(qn("w:w"), str(int(w * 567)))
            tcW.set(qn("w:type"), "dxa")
            tcPr.append(tcW)


def _table(d, header, rows, widths, pt=9.5):
    t = d.add_table(rows=1 + len(rows), cols=len(header))
    t.style = "Table Grid"
    for c, h in enumerate(header):
        cell = t.cell(0, c)
        cell.text = ""
        run = cell.paragraphs[0].add_run(h)
        run.bold = True
        run.font.size = Pt(pt)
    for r, row in enumerate(rows, 1):
        for c, v in enumerate(row):
            cell = t.cell(r, c)
            cell.text = ""
            run = cell.paragraphs[0].add_run(str(v if v is not None else ""))
            run.font.size = Pt(pt)
            cell.paragraphs[0].paragraph_format.space_after = Pt(0)
    _widths(t, widths)
    d.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def file_name(state, run_id):
    task = re.sub(r"[\\/:*?\"<>|\s]+", "_", (state.get("goal") or {}).get("task", "업무"))[:30]
    return f"인수인계서_{task}_{run_id}.docx"


def _closest_step(text, steps):
    """체크리스트 항목과 가장 비슷한 절차 단계. 미확정 항목처럼 닮은 단계가 없으면 None."""
    from difflib import SequenceMatcher
    if text.startswith("[미확정]"):
        return None
    best, score = None, 0.0
    for s in steps:
        r = SequenceMatcher(None, text, s.get("action", "")).ratio()
        if r > score:
            best, score = s, r
    return best if score >= 0.3 else None


def _todo(text):
    """질문을 '~ 확인하기' 꼴의 할 일로 바꾼다. 물음표 문장은 쓰지 않는다."""
    t = re.sub(r"[?？]+$", "", (text or "").strip()).strip()
    t = re.sub(r"(은|는|이|가)$", "", t).strip()
    return f"{t} 확인하기" if t else ""


def build_docx(state, run_id):
    """state(그래프 상태 dict)로 인수인계서 docx 바이트를 만든다. 절차 + 확인할 것만."""
    goal = state.get("goal") or {}
    steps = state.get("steps") or []
    answers = state.get("answers") or []

    d = _doc()
    p = d.add_paragraph()
    r = p.add_run(f"{goal.get('task', '업무')} 인수인계서")
    r.bold = True
    r.font.size = Pt(18)
    info = d.add_paragraph(" · ".join(x for x in [f"담당 {goal['newcomer']}" if goal.get("newcomer") else "",
                                                 f"확인 {goal['owner']}" if goal.get("owner") else "",
                                                 datetime.now().strftime("%Y-%m-%d")] if x))
    info.paragraph_format.space_after = Pt(2)
    if goal.get("done_when"):
        d.add_paragraph(f"끝나는 기준: {goal['done_when']}")

    d.add_heading("1. 절차", level=1)
    checklist = state.get("checklist") or []
    if checklist:
        # 체크리스트가 만들어진 뒤에는 그 항목이 '할 일'이다. 담당·양식은 가장 비슷한 절차 단계에서 가져온다
        rows = []
        for item in checklist:
            if item.get("text", "").startswith("[미확정]"):
                continue   # 미확정은 표에 넣지 않는다. '확인할 것'에만 남긴다
            step = _closest_step(item.get("text", ""), steps)
            rows.append([item.get("order", ""), item.get("text", "") + ("" if item.get("required", True) else "  (선택)"),
                         (step or {}).get("who") or "", (step or {}).get("form") or ""])
    else:
        rows = [[s.get("order", ""), s.get("action", ""), s.get("who") or "", s.get("form") or ""] for s in steps]
    _table(d, ["번호", "할 일", "담당", "양식"], rows, [1.0, 10.4, 2.2, 3.4])

    todos = []
    for a in answers:
        if not a.get("answer"):
            todos.append(_todo(a.get("topic") or a.get("question")))
    for s_ in steps:
        if s_.get("status") != "ok" and not s_.get("edited_by"):
            todos.append(f"{s_.get('order', '')}번 '{s_.get('action', '')}' 책임자에게 확인하기")
    todos = [t for t in dict.fromkeys(todos) if t]
    if todos:
        d.add_heading("2. 확인할 것", level=1)
        for t in todos:
            d.add_paragraph(t, style="List Bullet")

    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()

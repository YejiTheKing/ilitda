"""제출물 마크다운 초안을 docx로 만든다.

- 02_기술설명서.md → 02_기술설명서.docx : 운영규정 <별지 1> 표(항목 / 기재 내용) 그대로 1쪽
- 01_개발완료보고서.md → 01_개발완료보고서.docx : 별지 4 자유양식, 제목·글머리·표 (A4 5쪽 목표)
사용: .venv/bin/python scripts/build_submissions.py
PDF는 Word 또는 한글에서 '내보내기'로 만든다 (이 PC에 변환기가 없음).
"""
import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

OUT = Path("docs/제출물")
FONT = "Malgun Gothic"


def base_doc(margin_cm, font_pt):
    doc = Document()
    for s in doc.sections:
        s.top_margin = s.bottom_margin = Cm(margin_cm)
        s.left_margin = s.right_margin = Cm(margin_cm)
    st = doc.styles["Normal"]
    st.font.name = FONT
    st.font.size = Pt(font_pt)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    for name in ("Heading 1", "Heading 2", "List Bullet"):
        h = doc.styles[name]
        h.font.name = FONT
        h.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    doc.styles["Heading 1"].font.size = Pt(font_pt + 3)
    doc.styles["Heading 2"].font.size = Pt(font_pt + 1)
    return doc


def clean(s, keep_bold=False):
    if not keep_bold:
        s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"`([^`]*)`", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    return s.replace("<br>", "\n").strip()


def set_widths(table, widths_cm):
    table.autofit = False
    for row in table.rows:
        for cell, w in zip(row.cells, widths_cm):
            cell.width = Cm(w)
            tcPr = cell._tc.get_or_add_tcPr()
            tcW = OxmlElement("w:tcW")
            tcW.set(qn("w:w"), str(int(w * 567)))
            tcW.set(qn("w:type"), "dxa")
            tcPr.append(tcW)


def add_runs(para, text, pt, bold=False):
    """**굵게** 표시를 런으로 나눠 넣는다."""
    for i, piece in enumerate(re.split(r"\*\*", text)):
        if not piece:
            continue
        run = para.add_run(piece)
        run.font.size = Pt(pt)
        run.bold = bold or (i % 2 == 1)


def fill_cell(cell, text, pt, bold=False, shade=None):
    cell.text = ""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        para = cell.paragraphs[0] if i == 0 else cell.add_paragraph()
        add_runs(para, line, pt, bold)
        para.paragraph_format.space_after = Pt(0)
        para.paragraph_format.space_before = Pt(0)
    if shade:
        tcPr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd"); shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), shade)
        tcPr.append(shd)


def md_table_rows(block, keep_bold=False):
    rows = []
    for line in block:
        if re.match(r"^\|[-| :]+\|$", line.strip()):
            continue
        rows.append([clean(c.strip(), keep_bold) for c in line.strip().strip("|").split("|")])
    return rows


# ---------- 별지 1 기술설명서 ----------

def build_tech_sheet():
    md = (OUT / "02_기술설명서.md").read_text(encoding="utf-8")
    rows = md_table_rows([l for l in md.splitlines() if l.startswith("|")], keep_bold=True)[1:]   # 머리글 제외
    doc = base_doc(1.5, 8.5)
    title = doc.add_paragraph()
    r = title.add_run("<별지 1> AI Agent 기술설명서 (1페이지)")
    r.bold = True
    r.font.size = Pt(12)
    title.paragraph_format.space_after = Pt(4)
    table = doc.add_table(rows=len(rows) + 1, cols=2)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    fill_cell(table.cell(0, 0), "항목", 8.5, bold=True)
    fill_cell(table.cell(0, 1), "기재 내용", 8.5, bold=True)
    for i, (k, v) in enumerate(rows, 1):
        fill_cell(table.cell(i, 0), k, 8.5, bold=True)
        fill_cell(table.cell(i, 1), v, 8)
    set_widths(table, [3.3, 14.7])
    out = OUT / "02_기술설명서.docx"
    doc.save(out)
    return out, sum(len(re.sub(r"\s", "", v)) for _, v in rows)


# ---------- 별지 4 개발완료보고서 ----------

WIDTHS = {2: [4.0, 13.4], 3: [3.2, 7.0, 7.2], 4: [2.4, 5.0, 5.0, 5.0], 5: [2.0, 3.8, 3.8, 3.8, 4.0], 6: [1.6, 3.2, 3.2, 3.2, 3.2, 3.0], 7: [1.4, 2.8, 2.8, 2.8, 2.8, 2.8, 2.0]}


def build_report(src="01_개발완료보고서.md", out_name="01_개발완료보고서.docx"):
    """별지 4 자유양식. 지시어: [[PAGEBREAK]] 쪽 나눔, [[IMG 경로 | 설명]] 그림, '> ' 인용은 연한 바탕 상자."""
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    md = (OUT / src).read_text(encoding="utf-8")
    lines = md.splitlines()
    doc = base_doc(1.9, 10)
    i = 0
    while i < len(lines):
        l = lines[i]
        if l.startswith("|"):
            block = []
            while i < len(lines) and lines[i].startswith("|"):
                block.append(lines[i])
                i += 1
            rows = md_table_rows(block, keep_bold=True)
            n = len(rows[0])
            table = doc.add_table(rows=len(rows), cols=n)
            table.style = "Table Grid"
            for r_i, row in enumerate(rows):
                for c_i in range(n):
                    fill_cell(table.cell(r_i, c_i), row[c_i] if c_i < len(row) else "", 9, bold=(r_i == 0), shade="EEF1F0" if r_i == 0 else None)
            if n in WIDTHS:
                set_widths(table, WIDTHS[n])
            doc.add_paragraph().paragraph_format.space_after = Pt(4)
            continue
        if l.strip() == "[[PAGEBREAK]]":
            doc.add_page_break()
        elif l.startswith("[[IMG "):
            inner = l[6:].rstrip("]").strip()
            path, _, caption = inner.partition("|")
            doc.add_picture(path.strip(), width=Cm(17.2))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            cap = doc.add_paragraph(); add_runs(cap, clean(caption.strip(), True), 8.5)
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER; cap.paragraph_format.space_after = Pt(6)
        elif l.startswith("> "):
            table = doc.add_table(rows=1, cols=1); table.style = "Table Grid"
            fill_cell(table.cell(0, 0), clean(l[2:], True), 9.5, shade="E6F2EF")
            set_widths(table, [17.4])
            doc.add_paragraph().paragraph_format.space_after = Pt(2)
        elif l.startswith("# "):
            p = doc.add_paragraph(); add_runs(p, clean(l[2:], True), 15, bold=True)
        elif l.startswith("## "):
            doc.add_heading(clean(l[3:]), level=1)
        elif l.startswith("### "):
            doc.add_heading(clean(l[4:]), level=2)
        elif l.strip() in ("---", ""):
            pass
        elif l.startswith("- "):
            p = doc.add_paragraph(style="List Bullet"); add_runs(p, clean(l[2:], True), 10)
            p.paragraph_format.space_after = Pt(2)
        elif re.match(r"^\d+\. ", l):
            p = doc.add_paragraph(); add_runs(p, clean(l, True), 10)
            p.paragraph_format.space_after = Pt(1)
        else:
            p = doc.add_paragraph(); add_runs(p, clean(l, True), 10)
            p.paragraph_format.space_after = Pt(5)
            p.paragraph_format.line_spacing = 1.15
        i += 1
    out = OUT / out_name
    doc.save(out)
    return out, len(re.sub(r"\s", "", md))


# ---------- 별지 3 발표자료 (10장) ----------

def parse_slides(md):
    """## 장 N. 절을 {head, label, title, sub, numbers, keywords, columns, fig, script}로."""
    out = []
    for part in re.split(r"\n(?=## 장 \d+\.)", md):
        lines = part.splitlines()
        if not lines or not lines[0].startswith("## 장"):
            continue
        s = {"head": clean(lines[0][3:]), "label": "", "title": "", "sub": "", "numbers": [], "keywords": [], "columns": [], "fig": "", "script": ""}
        mode = None
        for line in lines[1:]:
            if line.startswith("**라벨**"):
                s["label"] = clean(line.split(":", 1)[1]); mode = None
            elif line.startswith("**제목**"):
                s["title"] = clean(line.split(":", 1)[1]); mode = None
            elif line.startswith("**부제**"):
                s["sub"] = clean(line.split(":", 1)[1]); mode = None
            elif line.startswith("**그림**"):
                s["fig"] = clean(line.split(":", 1)[1]); mode = "fig"
            elif line.startswith("**숫자**"):
                mode = "numbers"
            elif line.startswith("**키워드**"):
                mode = "keywords"
            elif line.startswith("**열**"):
                mode = "columns"
            elif line.startswith("**대본"):
                mode = "script"
            elif line.strip() == "---":
                mode = None
            elif mode in ("numbers", "columns") and line.startswith("- "):
                k, _, v = clean(line[2:]).partition(" | ")
                s[mode].append((k.strip(), v.strip()))
            elif mode == "keywords" and line.startswith("- "):
                s["keywords"].append(clean(line[2:]))
            elif mode == "fig" and line.strip():
                s["fig"] += " " + clean(line)
            elif mode == "script" and line.strip():
                s["script"] += clean(line) + "\n"
        out.append(s)
    return out


def build_slides():
    """라벨 + 주장 제목 → 숫자 띠 → 열 상자/행 → 키워드 → 그림 자리. 글자 16pt 이상, 대본은 발표자 노트."""
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Emu, Pt as PPt

    md = (OUT / "03_발표자료_10장.md").read_text(encoding="utf-8")
    slides = parse_slides(md)
    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(12192000), Emu(6858000)
    W, H = prs.slide_width, prs.slide_height
    ACC, TXT, MUT, LINE, SOFT, BG = (RGBColor(0x16, 0x7D, 0x68), RGBColor(0x17, 0x2B, 0x2A), RGBColor(0x5B, 0x6B, 0x69),
                                     RGBColor(0xE2, 0xE7, 0xE5), RGBColor(0xE6, 0xF2, 0xEF), RGBColor(0xF6, 0xF7, 0xF9))
    M = Emu(640000)
    FOOT = Emu(520000)

    def para(tf, txt, size, color, bold=False, space=4, first=False):
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        r = p.add_run(); r.text = txt; r.font.size = PPt(size); r.font.bold = bold; r.font.color.rgb = color; r.font.name = FONT
        p.space_after = PPt(space)
        return p

    def box(sl, x, y, w, h, fill=None, line=LINE):
        sh = sl.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
        sh.adjustments[0] = 0.05
        if fill:
            sh.fill.solid(); sh.fill.fore_color.rgb = fill
        else:
            sh.fill.background()
        sh.line.color.rgb = line; sh.line.width = PPt(0.75)
        sh.shadow.inherit = False
        sh.text_frame.word_wrap = True
        return sh

    for n, s in enumerate(slides, 1):
        sl = prs.slides.add_slide(prs.slide_layouts[6])
        cover = (n == 1)
        bar = sl.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, Emu(80000)); bar.fill.solid(); bar.fill.fore_color.rgb = ACC; bar.line.fill.background()
        y = Emu(360000)
        # 라벨 칩
        if s["label"]:
            chip = box(sl, M, y, Emu(220000) + Emu(170000) * len(s["label"]), Emu(330000), fill=SOFT, line=SOFT)
            para(chip.text_frame, s["label"], 14, ACC, bold=True, space=0, first=True)
            y += Emu(400000)
        # 제목·부제
        tb = sl.shapes.add_textbox(M, y, W - 2 * M, Emu(1000000)); tb.text_frame.word_wrap = True
        para(tb.text_frame, s["title"] or s["head"], 48 if cover else 30, ACC if cover else TXT, bold=True, space=4, first=True)
        if s["sub"]:
            para(tb.text_frame, s["sub"], 18 if cover else 15, MUT, space=0)
        y += Emu(1250000 if s["sub"] else 800000)
        if cover:
            y += Emu(300000)
        # 숫자 띠
        if s["numbers"]:
            k = len(s["numbers"]); gap = Emu(160000); bw = int((W - 2 * M - gap * (k - 1)) / k)
            for i, (val, cap) in enumerate(s["numbers"]):
                b = box(sl, M + i * (bw + gap), y, bw, Emu(1200000), fill=SOFT, line=SOFT)
                para(b.text_frame, val, 36, ACC, bold=True, space=2, first=True)
                para(b.text_frame, cap, 13, TXT, space=0)
            y += Emu(1200000 + 200000)
        has_fig = bool(s["fig"]) and not cover
        fig_w = Emu(3500000) if has_fig else 0
        body_w = W - 2 * M - (fig_w + Emu(240000) if has_fig else 0)
        # 열: 3개 이하이고 그림이 없으면 나란히, 아니면 행으로
        if s["columns"]:
            k = len(s["columns"]); gap = Emu(140000)
            if k <= 3 and not has_fig:
                ch = Emu(2300000) if s["keywords"] else (H - y - FOOT)
                cw = int((body_w - gap * (k - 1)) / k)
                for i, (head, body) in enumerate(s["columns"]):
                    b = box(sl, M + i * (cw + gap), y, cw, ch)
                    para(b.text_frame, head, 20, ACC, bold=True, space=6, first=True)
                    para(b.text_frame, body, 15, TXT, space=0)
                y += ch + Emu(160000)
            else:
                rh = Emu(420000) if k > 5 else (Emu(480000) if k > 3 else Emu(560000))
                for i, (head, body) in enumerate(s["columns"]):
                    b = box(sl, M, y + i * (rh + Emu(60000)), body_w, rh, fill=SOFT if i % 2 == 0 else None, line=LINE)
                    p = b.text_frame.paragraphs[0]
                    r = p.add_run(); r.text = head + "   "; r.font.size = PPt(15); r.font.bold = True; r.font.color.rgb = ACC; r.font.name = FONT
                    r2 = p.add_run(); r2.text = body; r2.font.size = PPt(14); r2.font.color.rgb = TXT; r2.font.name = FONT
                y += k * (rh + Emu(60000)) + Emu(120000)
        # 키워드
        if s["keywords"] and y < H - FOOT - Emu(300000):
            kb = sl.shapes.add_textbox(M, y, body_w, H - y - FOOT); kb.text_frame.word_wrap = True
            for i, t in enumerate(s["keywords"]):
                para(kb.text_frame, "•  " + t, 18 if cover else 16, TXT, space=8, first=(i == 0))
        # 그림 자리
        if has_fig:
            fy = Emu(1500000) if not s["numbers"] else Emu(3200000)
            fb = box(sl, W - M - fig_w, fy, fig_w, H - fy - FOOT, fill=BG)
            para(fb.text_frame, "그림 자리", 12, MUT, bold=True, space=4, first=True)
            para(fb.text_frame, s["fig"], 11, MUT, space=0)
        # 하단: 쪽 번호 · 심사 번호
        fb2 = sl.shapes.add_textbox(M, H - Emu(380000), W - 2 * M, Emu(300000))
        tag = re.search(r"\[심사[^\]]*\]", s["head"])
        para(fb2.text_frame, f"{n} / {len(slides)}" + (f"   ·   {tag.group(0)}" if tag else "") + "   ·   일잇다 — 바톤터치", 10, MUT, space=0, first=True)
        sl.notes_slide.notes_text_frame.text = s["script"].strip()
    out = OUT / "03_발표자료_10장.pptx"
    prs.save(out)
    return out, len(slides)


if __name__ == "__main__":
    p, n = build_tech_sheet()
    print(f"{p}: 기재 내용 {n:,}자 (공백 제외)")
    p, n = build_report()
    print(f"{p}: 본문 {n:,}자 (공백 제외)")
    p, n = build_report("01_개발완료보고서_2안.md", "01_개발완료보고서_2안.docx")
    print(f"{p}: 본문 {n:,}자 (공백 제외)")
    p, n = build_slides()
    print(f"{p}: 슬라이드 {n}장 (그림은 자리만, 대본은 발표자 노트)")

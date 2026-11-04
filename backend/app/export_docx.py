"""Экспорт документа КСП/КМЖ (v2) в редактируемый DOCX с сохранением оформления."""
import re
from io import BytesIO

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

FONT = "Arial"
ACCENT = RGBColor(0x1F, 0x38, 0x64)
HEADER_FILL = "D9E2F3"
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_BULLET = re.compile(r"^\s*[-*•]\s+(.*)$")
_NUMBERED = re.compile(r"^\s*(\d+[.)])\s+(.*)$")
_SUBHEAD = re.compile(r"^\s*#{1,6}\s*(.*)$")


def _set_font(style, size=None, bold=None, color=None):
    style.font.name = FONT
    if size:
        style.font.size = Pt(size)
    if bold is not None:
        style.font.bold = bold
    if color is not None:
        style.font.color.rgb = color
    rpr = style.element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.append(fonts)
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        fonts.set(qn(attr), FONT)
    for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        if fonts.get(qn(attr)) is not None:
            del fonts.attrib[qn(attr)]


def _inline(paragraph, text, size=None, bold=False):
    pos = 0
    for m in _BOLD.finditer(text):
        if m.start() > pos:
            _run(paragraph, text[pos:m.start()], size, bold)
        _run(paragraph, m.group(1), size, True)
        pos = m.end()
    if pos < len(text):
        _run(paragraph, text[pos:], size, bold)


def _run(paragraph, text, size, bold):
    r = paragraph.add_run(text)
    r.bold = bold or None
    if size:
        r.font.size = Pt(size)
    return r


def _shade(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def _row_flag(row, tag):
    tr_pr = row._tr.get_or_add_trPr()
    tr_pr.append(OxmlElement(tag))


def _write_text(doc, text):
    in_code = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.5)
            p.paragraph_format.space_after = Pt(0)
            r = p.add_run(line)
            r.font.name = "Consolas"
            r.font.size = Pt(8.5)
            continue
        if not line.strip():
            continue
        if _SUBHEAD.match(line):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.keep_with_next = True
            _inline(p, _SUBHEAD.match(line).group(1), bold=True)
            continue
        m = _BULLET.match(line)
        if m:
            p = doc.add_paragraph(style="List Bullet")
            _inline(p, m.group(1))
            p.paragraph_format.space_after = Pt(2)
            continue
        m = _NUMBERED.match(line)
        if m:
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.7)
            p.paragraph_format.first_line_indent = Cm(-0.7)
            p.paragraph_format.space_after = Pt(2)
            _inline(p, f"{m.group(1)} {m.group(2)}")
            continue
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(4)
        _inline(p, line)


def _column_widths(part, total_cm):
    n = len(part["header"])
    given = part.get("widths")
    if given and len(given) == n:
        weights = [float(x) for x in given]
    else:
        weights = []
        for i in range(n):
            cells = [part["header"][i]] + [r[i] for r in part["rows"] if i < len(r)]
            avg = sum(len(c) for c in cells) / max(len(cells), 1)
            weights.append(min(max(avg, 8), 60))
    s = sum(weights)
    widths = [max(total_cm * w / s, 1.6) for w in weights]
    scale = total_cm / sum(widths)
    return [w * scale for w in widths]


def _write_table(doc, part, total_cm):
    header, rows = part["header"], part["rows"]
    n = len(header)
    table = doc.add_table(rows=0, cols=n)
    table.style = "Table Grid"
    table.autofit = False
    tbl_pr = table._tbl.tblPr
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tbl_pr.append(layout)
    widths = _column_widths(part, total_cm)
    for ri, values in enumerate([header] + rows):
        row = table.add_row()
        _row_flag(row, "w:cantSplit")
        if ri == 0:
            _row_flag(row, "w:tblHeader")  # шапка повторяется на каждой странице
        for ci in range(n):
            cell = row.cells[ci]
            cell.width = Cm(widths[ci])
            if ri == 0:
                _shade(cell, HEADER_FILL)
            value = str(values[ci]) if ci < len(values) else ""
            lines = value.split("\n") or [""]
            for li, line in enumerate(lines):
                p = cell.paragraphs[0] if li == 0 else cell.add_paragraph()
                p.paragraph_format.space_after = Pt(1)
                _inline(p, line, size=9, bold=(ri == 0))
    for ci, w in enumerate(widths):
        table.columns[ci].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def needs_landscape(content) -> bool:
    return any(p.get("type") == "table" and len(p.get("header", [])) >= 5
               for b in content.get("blocks", []) for p in b.get("parts", []))


def build_docx(lesson: dict, content: dict) -> BytesIO:
    """lesson: {title, subject, grade, topic}; content — уже нормализованный документ v2."""
    doc = Document()
    sec = doc.sections[0]
    landscape = needs_landscape(content)
    if landscape:
        sec.orientation = WD_ORIENT.LANDSCAPE
        sec.page_width, sec.page_height = Cm(29.7), Cm(21.0)
    else:
        sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Cm(1.5))
    usable = (sec.page_width - sec.left_margin - sec.right_margin) / 360000  # EMU → см

    _set_font(doc.styles["Normal"], 10)
    _set_font(doc.styles["Title"], 17, True, ACCENT)
    _set_font(doc.styles["Heading 1"], 13, True, ACCENT)
    _set_font(doc.styles["List Bullet"], 10)

    title = doc.add_heading(lesson.get("title") or "КСП / КМЖ", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.add_run(" · ".join(x for x in (lesson.get("subject"), lesson.get("grade"), lesson.get("topic")) if x)).bold = True

    for block in content.get("blocks", []):
        doc.add_heading(block.get("heading") or "—", level=1)
        for part in block.get("parts", []):
            if part.get("type") == "table":
                _write_table(doc, part, usable)
            elif part.get("text", "").strip():
                _write_text(doc, part["text"])

    footer = sec.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.add_run("USTAZ AI PRO MAX · ").italic = True
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    r = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = "1"
    r.append(t)
    fld.append(r)
    footer._p.append(fld)

    doc.core_properties.title = lesson.get("title") or ""
    doc.core_properties.author = "USTAZ AI PRO MAX"  # личные данные учителя в метаданные не пишем
    stream = BytesIO()
    doc.save(stream)
    stream.seek(0)
    return stream

"""Экспорт презентации в PPTX (python-pptx)."""
from io import BytesIO
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

ACCENT = RGBColor(0x1D, 0x4E, 0xD8)
DARK = RGBColor(0x17, 0x20, 0x33)
MUTED = RGBColor(0x64, 0x74, 0x8B)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT = RGBColor(0xEE, 0xF2, 0xFF)


def _set_run(run, size=18, bold=False, color=DARK):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = "Arial"


def _fill(shape, color: RGBColor):
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()


def _add_textbox(slide, left, top, width, height, text, size=18, bold=False, color=DARK, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text or ""
    _set_run(run, size=size, bold=bold, color=color)
    return box


def _bullets(slide, left, top, width, height, items, size=18):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items or []):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.level = 0
        p.space_after = Pt(8)
        run = p.add_run()
        run.text = "• " + str(item)
        _set_run(run, size=size, color=DARK)
    return box


def _bar(slide, prs):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), prs.slide_width, Inches(0.18)
    )
    _fill(shape, ACCENT)


def _footer(slide, prs, meta, index, total):
    label = " · ".join(x for x in [meta.get("subject"), meta.get("grade"), meta.get("topic")] if x)
    _add_textbox(
        slide, Inches(0.5), prs.slide_height - Inches(0.45),
        prs.slide_width - Inches(1.4), Inches(0.35),
        f"{label}   ·   {index}/{total}", size=10, color=MUTED,
    )


def _render_slide(prs, slide_data: dict, meta: dict, index: int, total: int):
    layout = slide_data.get("layout") or "content"
    blank = prs.slide_layouts[6]  # blank
    s = prs.slides.add_slide(blank)
    _bar(s, prs)
    title = slide_data.get("title") or ""
    subtitle = slide_data.get("subtitle") or ""
    body = slide_data.get("body") or ""
    bullets = slide_data.get("bullets") or []
    accent = slide_data.get("accent") or ""
    left = slide_data.get("left") or ""
    right = slide_data.get("right") or ""

    if layout == "title":
        # large centered title
        _add_textbox(s, Inches(0.7), Inches(2.0), Inches(12), Inches(1.4),
                     title, size=36, bold=True, color=DARK, align=PP_ALIGN.CENTER)
        if subtitle:
            _add_textbox(s, Inches(1), Inches(3.5), Inches(11.3), Inches(0.8),
                         subtitle, size=20, color=MUTED, align=PP_ALIGN.CENTER)
        meta_line = " · ".join(x for x in [meta.get("subject"), meta.get("grade")] if x)
        if meta_line:
            _add_textbox(s, Inches(1), Inches(4.5), Inches(11.3), Inches(0.5),
                         meta_line, size=16, color=ACCENT, align=PP_ALIGN.CENTER)
        if accent:
            _add_textbox(s, Inches(1.5), Inches(5.3), Inches(10.3), Inches(0.6),
                         accent, size=14, color=MUTED, align=PP_ALIGN.CENTER)
    elif layout == "section":
        shape = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.5), Inches(2.4),
                                  Inches(10.3), Inches(2.2))
        _fill(shape, LIGHT)
        _add_textbox(s, Inches(1.8), Inches(2.7), Inches(9.7), Inches(1.5),
                     title, size=28, bold=True, color=ACCENT, align=PP_ALIGN.CENTER)
        if subtitle:
            _add_textbox(s, Inches(1.8), Inches(4.0), Inches(9.7), Inches(0.5),
                         subtitle, size=16, color=MUTED, align=PP_ALIGN.CENTER)
    elif layout == "two_col":
        _add_textbox(s, Inches(0.6), Inches(0.5), Inches(12), Inches(0.9),
                     title, size=26, bold=True, color=DARK)
        if subtitle:
            _add_textbox(s, Inches(0.6), Inches(1.3), Inches(12), Inches(0.4),
                         subtitle, size=14, color=MUTED)
        _add_textbox(s, Inches(0.6), Inches(2.0), Inches(5.8), Inches(4.2),
                     left, size=16, color=DARK)
        _add_textbox(s, Inches(6.9), Inches(2.0), Inches(5.8), Inches(4.2),
                     right, size=16, color=DARK)
    elif layout == "closing":
        _add_textbox(s, Inches(0.8), Inches(2.2), Inches(11.7), Inches(1.2),
                     title, size=32, bold=True, color=DARK, align=PP_ALIGN.CENTER)
        text = body or "\n".join(f"• {b}" for b in bullets)
        if text:
            _add_textbox(s, Inches(1.5), Inches(3.6), Inches(10.3), Inches(2.2),
                         text, size=18, color=MUTED, align=PP_ALIGN.CENTER)
    else:  # content / bullets
        _add_textbox(s, Inches(0.6), Inches(0.5), Inches(12), Inches(0.9),
                     title, size=26, bold=True, color=DARK)
        top = Inches(1.5)
        if subtitle:
            _add_textbox(s, Inches(0.6), Inches(1.35), Inches(12), Inches(0.4),
                         subtitle, size=14, color=MUTED)
            top = Inches(1.9)
        if bullets:
            _bullets(s, Inches(0.7), top, Inches(11.8), Inches(4.5), bullets, size=18)
        elif body:
            _add_textbox(s, Inches(0.7), top, Inches(11.8), Inches(4.5), body, size=18)
        if accent:
            _add_textbox(s, Inches(0.7), Inches(6.5), Inches(11.8), Inches(0.4),
                         accent, size=12, bold=True, color=ACCENT)

    _footer(s, prs, meta, index, total)
    # notes
    notes = slide_data.get("notes") or ""
    if notes:
        ns = s.notes_slide
        ns.notes_text_frame.text = notes


def build_pptx(meta: dict, content: dict) -> BytesIO:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    slides = content.get("slides") or []
    total = max(len(slides), 1)
    if not slides:
        s = empty_placeholder(prs, meta)
        buf = BytesIO()
        prs.save(buf)
        buf.seek(0)
        return buf
    for i, sl in enumerate(slides, 1):
        _render_slide(prs, sl, meta, i, total)
    buf = BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf


def empty_placeholder(prs, meta):
    blank = prs.slide_layouts[6]
    s = prs.slides.add_slide(blank)
    _add_textbox(s, Inches(1), Inches(3), Inches(11), Inches(1),
                 meta.get("title") or "Презентация", size=28, bold=True, align=PP_ALIGN.CENTER)
    return s

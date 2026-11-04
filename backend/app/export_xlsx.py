"""Экспорт таблиц документа (КТП, планы, ключи) в XLSX."""
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

HEADER_FILL = PatternFill("solid", fgColor="D9E2F3")
HEADER_FONT = Font(name="Arial", bold=True, size=11)
CELL_FONT = Font(name="Arial", size=10)
THIN = Border(
    left=Side(style="thin", color="B0B8C8"),
    right=Side(style="thin", color="B0B8C8"),
    top=Side(style="thin", color="B0B8C8"),
    bottom=Side(style="thin", color="B0B8C8"),
)


def _write_table(ws, start_row, header, rows):
    for c, h in enumerate(header, 1):
        cell = ws.cell(start_row, c, h)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.border = THIN
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    for ri, row in enumerate(rows):
        for c, val in enumerate(row, 1):
            cell = ws.cell(start_row + 1 + ri, c, val)
            cell.font = CELL_FONT
            cell.border = THIN
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    return start_row + 1 + len(rows)


def build_xlsx(meta: dict, content: dict) -> BytesIO:
    wb = Workbook()
    # Sheet 1: meta
    ws0 = wb.active
    ws0.title = "Реквизиты"
    ws0["A1"] = "Название"
    ws0["B1"] = meta.get("title") or ""
    ws0["A2"] = "Предмет"
    ws0["B2"] = meta.get("subject") or ""
    ws0["A3"] = "Класс"
    ws0["B3"] = meta.get("grade") or ""
    ws0["A4"] = "Тема"
    ws0["B4"] = meta.get("topic") or ""
    ws0["A5"] = "Тип"
    ws0["B5"] = (content or {}).get("doc_type") or "ksp"
    ws0["A6"] = "Язык"
    ws0["B6"] = (content or {}).get("language") or ""
    for col in range(1, 3):
        ws0.column_dimensions[get_column_letter(col)].width = 28

    # Presentations: slides list
    if (content or {}).get("doc_type") == "presentation":
        ws = wb.create_sheet("Слайды")
        ws.append(["№", "Макет", "Заголовок", "Подзаголовок", "Текст", "Пункты", "Заметки"])
        for i, s in enumerate(content.get("slides") or [], 1):
            ws.append([
                i, s.get("layout", ""), s.get("title", ""), s.get("subtitle", ""),
                s.get("body", ""), "\n".join(s.get("bullets") or []), s.get("notes", ""),
            ])
        for col in range(1, 8):
            ws.column_dimensions[get_column_letter(col)].width = 18
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf

    # Block documents: one sheet per block with tables; text blocks as notes
    tables_written = 0
    for bi, block in enumerate(content.get("blocks") or [], 1):
        heading = (block.get("heading") or f"Раздел {bi}")[:28]
        safe = "".join(ch if ch.isalnum() or ch in " _-" else "_" for ch in heading)[:28] or f"S{bi}"
        # unique sheet name
        name = safe
        n = 1
        while name in wb.sheetnames:
            n += 1
            name = f"{safe[:24]}_{n}"
        parts = block.get("parts") or []
        tables = [p for p in parts if p.get("type") == "table"]
        texts = [p.get("text", "") for p in parts if p.get("type") != "table"]
        if tables:
            ws = wb.create_sheet(name)
            row = 1
            for p in tables:
                header = p.get("header") or []
                rows = p.get("rows") or []
                row = _write_table(ws, row, header, rows) + 2
                tables_written += 1
            for col in range(1, max((len(p.get("header") or []) for p in tables), default=3) + 1):
                ws.column_dimensions[get_column_letter(col)].width = 16
            if any(texts):
                ws2 = wb.create_sheet((name + "_текст")[:31])
                ws2["A1"] = "\n\n".join(t for t in texts if t)
                ws2.column_dimensions["A"].width = 80
        elif any(texts):
            ws = wb.create_sheet(name)
            ws["A1"] = "\n\n".join(t for t in texts if t)
            ws.column_dimensions["A"].width = 80

    if tables_written == 0 and len(wb.sheetnames) == 1:
        ws = wb.create_sheet("Содержимое")
        lines = []
        for b in content.get("blocks") or []:
            lines.append(b.get("heading") or "")
            for p in b.get("parts") or []:
                if p.get("type") == "table":
                    lines.append(" | ".join(p.get("header") or []))
                    for r in p.get("rows") or []:
                        lines.append(" | ".join(str(c) for c in r))
                else:
                    lines.append(p.get("text") or "")
            lines.append("")
        ws["A1"] = "\n".join(lines)
        ws.column_dimensions["A"].width = 80

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf

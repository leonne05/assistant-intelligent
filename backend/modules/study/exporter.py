from datetime import date
import io
import re

from docx import Document
from docx.shared import Cm
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate


class StudyExporter:
    def __init__(self):
        self.formats = {
            "pdf": {"extension": "pdf", "media_type": "application/pdf"},
            "docx": {
                "extension": "docx",
                "media_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            },
            "md": {"extension": "md", "media_type": "text/markdown; charset=utf-8"},
        }
        self.contents = {"summary": "resume", "full": "fiche-complete"}

        self.replacements = {
            "→": "->", "←": "<-", "≥": ">=", "≤": "<=", "≠": "!=", "≈": "~",
            "−": "-", "√": "racine ", "∞": "infini", "π": "pi", "∑": "somme",
            "’": "'", "“": '"', "”": '"', "\u202f": " ", "\u00a0": " ",
        }

        self.body_style = ParagraphStyle("body", fontName="Helvetica", fontSize=10.5, leading=15, spaceAfter=6)
        self.heading_styles = {
            level: ParagraphStyle(
                f"heading{level}", fontName="Helvetica-Bold", fontSize=size, leading=size + 4,
                spaceBefore=12, spaceAfter=6, keepWithNext=1,
            )
            for level, size in {1: 20, 2: 15, 3: 12.5, 4: 11}.items()
        }


    def get_best_summary(self, course):

        if course["pdf"] is not None and course["pdf"]["summary"]:
            return course["pdf"]["summary"]

        return course["summary"]


    def demote_headings(self, text):
        return re.sub(r"^#{1,6}\s+", "### ", text, flags=re.MULTILINE)


    def build_markdown(self, course_id, course, content):

        footer = f"Document généré par JARVIS (module Études) le {date.today().strftime('%d/%m/%Y')} - cours {course_id}."

        if content == "summary":
            summary = self.get_best_summary(course=course)

            if not summary:
                raise ValueError(
                    "Ce cours n'a pas encore de résumé : lance d'abord le résumé du cours (POST /study/courses/{id}/summary)."
                )

            return summary.strip() + "\n\n" + footer

        if not course["transcript"].strip() and not course["pdf"]:
            raise ValueError("Ce cours est vide : il n'y a rien à exporter.")

        parts = [f"# Cours {course_id} - fiche complète", footer]

        if course["pdf"] is not None and course["pdf"]["summary"]:
            parts.append("## Résumé global (PDF et explications orales)")
            parts.append(self.demote_headings(text=course["pdf"]["summary"].strip()))

        if course["summary"]:
            parts.append("## Résumé de ce que le professeur a dit")
            parts.append(self.demote_headings(text=course["summary"].strip()))

        notes = [(index, note) for index, note in enumerate(course["chunk_summaries"], start=1) if note]

        if notes:
            parts.append("## Notes par morceau d'enregistrement")

            for index, note in notes:
                parts.append(f"### Morceau {index}")
                parts.append(note.strip())

        if course["chunks"]:
            parts.append("## Transcription complète")

            for index, chunk_text in enumerate(course["chunks"], start=1):
                parts.append(f"**Morceau {index}.** {chunk_text.strip()}")

        return "\n\n".join(parts)


    def parse_markdown(self, markdown):

        blocks = []
        paragraph_lines = []

        def flush_paragraph():
            if paragraph_lines:
                blocks.append({"type": "paragraph", "text": " ".join(paragraph_lines)})
                paragraph_lines.clear()

        for raw_line in markdown.split("\n"):
            line = raw_line.rstrip()
            stripped = line.strip()

            heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
            bullet = re.match(r"^(\s*)[-*•]\s+(.*)$", line)
            number = re.match(r"^(\s*)(\d+)[.)]\s+(.*)$", line)

            if not stripped:
                flush_paragraph()
            elif re.match(r"^[-*_]{3,}$", stripped):
                flush_paragraph()
            elif heading:
                flush_paragraph()
                blocks.append({"type": "heading", "level": min(len(heading.group(1)), 4), "text": heading.group(2)})
            elif bullet:
                flush_paragraph()
                level = min(len(bullet.group(1)) // 2, 2)
                blocks.append({"type": "bullet", "level": level, "text": bullet.group(2)})
            elif number:
                flush_paragraph()
                level = min(len(number.group(1)) // 2, 2)
                blocks.append({"type": "number", "level": level, "number": number.group(2), "text": number.group(3)})
            else:
                paragraph_lines.append(stripped)

        flush_paragraph()

        return blocks


    def split_bold(self, text):

        parts = text.replace("`", "").split("**")

        return [(part, index % 2 == 1) for index, part in enumerate(parts) if part]


    def clean_pdf_text(self, text):

        for old, new in self.replacements.items():
            text = text.replace(old, new)

        clean_chars = []

        for char in text:
            try:
                char.encode("cp1252")
                clean_chars.append(char)
            except UnicodeEncodeError:
                clean_chars.append("?")

        return "".join(clean_chars)


    def to_pdf_markup(self, text):

        markup = ""

        for part, is_bold in self.split_bold(text=self.clean_pdf_text(text=text)):
            part = part.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            markup += f"<b>{part}</b>" if is_bold else part

        return markup


    def build_pdf(self, blocks, title):

        buffer = io.BytesIO()
        document = SimpleDocTemplate(
            buffer, pagesize=A4, title=self.clean_pdf_text(text=title),
            leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
        )
        story = []

        for block in blocks:
            markup = self.to_pdf_markup(text=block["text"])

            if block["type"] == "heading":
                story.append(Paragraph(markup, self.heading_styles[block["level"]]))

            elif block["type"] == "paragraph":
                story.append(Paragraph(markup, self.body_style))

            else:
                bullet_text = "•" if block["type"] == "bullet" else block["number"] + "."
                style = ParagraphStyle(
                    "list", parent=self.body_style, spaceAfter=3,
                    leftIndent=16 + block["level"] * 14, bulletIndent=block["level"] * 14,
                )
                story.append(Paragraph(markup, style, bulletText=bullet_text))

        document.build(story)

        return buffer.getvalue()


    def add_runs(self, paragraph, text):

        for part, is_bold in self.split_bold(text=text):
            run = paragraph.add_run(part)
            run.bold = is_bold


    def build_docx(self, blocks):

        document = Document()

        for block in blocks:

            if block["type"] == "heading":
                document.add_heading(text="".join(part for part, is_bold in self.split_bold(text=block["text"])), level=block["level"])

            elif block["type"] == "paragraph":
                self.add_runs(paragraph=document.add_paragraph(), text=block["text"])

            elif block["type"] == "bullet":
                style = "List Bullet" if block["level"] == 0 else f"List Bullet {block['level'] + 1}"
                self.add_runs(paragraph=document.add_paragraph(style=style), text=block["text"])

            else:
                paragraph = document.add_paragraph()
                paragraph.paragraph_format.left_indent = Cm(0.9 + block["level"] * 0.6)
                paragraph.paragraph_format.first_line_indent = Cm(-0.6)
                paragraph.add_run(block["number"] + ".  ")
                self.add_runs(paragraph=paragraph, text=block["text"])

        buffer = io.BytesIO()
        document.save(buffer)

        return buffer.getvalue()


    def export(self, course_id, course, file_format, content):

        if file_format not in self.formats:
            raise ValueError("Format inconnu : choisis pdf, docx ou md.")

        if content not in self.contents:
            raise ValueError("Contenu inconnu : choisis summary (résumé) ou full (fiche complète).")

        markdown = self.build_markdown(course_id=course_id, course=course, content=content)

        if file_format == "md":
            data = markdown.encode("utf-8")
        else:
            blocks = self.parse_markdown(markdown=markdown)

            if file_format == "pdf":
                data = self.build_pdf(blocks=blocks, title=f"Cours {course_id}")
            else:
                data = self.build_docx(blocks=blocks)

        safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", course_id).strip("_") or "cours"
        file_info = self.formats[file_format]

        return {
            "file_name": f"jarvis_{safe_name}_{self.contents[content]}.{file_info['extension']}",
            "media_type": file_info["media_type"],
            "data": data,
        }
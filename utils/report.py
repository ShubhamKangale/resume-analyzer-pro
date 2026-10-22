"""
Generates a downloadable PDF report summarizing an analysis result.
Uses the lightweight 'fpdf2' library.
"""
from fpdf import FPDF


def _safe(text):
    """Helvetica only supports latin-1; replace anything else so PDF never crashes."""
    return str(text).encode("latin-1", "replace").decode("latin-1")


class ReportPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(44, 95, 158)
        self.cell(0, 12, "AI Resume Analyzer - Analysis Report", new_x="LMARGIN", new_y="NEXT", align="C")
        self.set_draw_color(44, 95, 158)
        self.line(10, 22, 200, 22)
        self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def build_report(file_path, user_name, resume_file_name, jd_title, result):
    pdf = ReportPDF()
    pdf.add_page()
    pdf.set_text_color(0, 0, 0)

    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, _safe(f"Candidate: {user_name}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, _safe(f"Resume File: {resume_file_name}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, _safe(f"Job Title: {jd_title or 'N/A'}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 22)
    if result["score"] >= 60:
        pdf.set_text_color(46, 125, 50)   # green
    else:
        pdf.set_text_color(178, 34, 34)   # red
    pdf.cell(0, 14, f"Match Score: {result['score']}%", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Matched Skills", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, new_x="LMARGIN", new_y="NEXT", text=_safe(", ".join(result["matched_skills"]) or "None found"))
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Missing Skills", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, new_x="LMARGIN", new_y="NEXT", text=_safe(", ".join(result["missing_skills"]) or "None -- great coverage!"))
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Suggestions", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    for tip in result["suggestions"]:
        pdf.multi_cell(0, 7, new_x="LMARGIN", new_y="NEXT", text=_safe(f"- {tip}"))
    pdf.ln(2)

    pdf.output(file_path)
    return file_path

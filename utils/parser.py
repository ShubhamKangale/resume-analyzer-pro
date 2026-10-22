"""
Resume parsing utilities.
Extracts raw text from PDF / DOCX resumes and pulls out simple
contact-info entities (email, phone) using regular expressions.
"""
import os
import re
import docx2txt
import pdfplumber

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_REGEX = re.compile(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3,5}\)?[-.\s]?\d{3}[-.\s]?\d{3,4}")


def allowed_file(filename, allowed_extensions):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def extract_text_from_pdf(file_path):
    """Extract raw text from a PDF file using pdfplumber."""
    text_chunks = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_chunks.append(page_text)
    return "\n".join(text_chunks)


def extract_text_from_docx(file_path):
    """Extract raw text from a DOCX file using docx2txt."""
    return docx2txt.process(file_path) or ""


def extract_text(file_path):
    """Dispatch to the correct extractor based on file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext == ".docx":
        return extract_text_from_docx(file_path)
    raise ValueError(f"Unsupported file type: {ext}")


def extract_contact_info(text):
    """Pull out email and phone number from resume text using regex."""
    email_match = EMAIL_REGEX.search(text)
    phone_match = PHONE_REGEX.search(text)
    return {
        "email": email_match.group(0) if email_match else None,
        "phone": phone_match.group(0) if phone_match else None,
    }

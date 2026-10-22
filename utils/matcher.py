"""
Matching & scoring engine.
Compares a resume's extracted text against a job description using
the master skills list, computes a match score, and generates simple
rule-based improvement suggestions.
"""
import re
import string

STOP_WORDS = {
    "the", "and", "a", "an", "is", "are", "to", "of", "in", "for", "with",
    "on", "at", "by", "as", "be", "this", "that", "it", "or", "will",
    "we", "you", "your", "our", "their", "from", "have", "has", "not",
}


def normalize(text):
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.lower()
    text = text.translate(str.maketrans("", "", string.punctuation))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text):
    return [w for w in normalize(text).split(" ") if w and w not in STOP_WORDS]


def find_skills_in_text(text, skill_list):
    """
    Return the subset of skill_list whose name appears in text
    (case-insensitive, word-boundary aware so 'R' doesn't match inside
    'Marketing', for example).
    """
    normalized_text = f" {normalize(text)} "
    found = []
    for skill in skill_list:
        pattern = r"(?<![a-z0-9])" + re.escape(skill.lower()) + r"(?![a-z0-9])"
        if re.search(pattern, normalized_text):
            found.append(skill)
    return found


def compute_match(resume_text, jd_text, skill_list):
    """
    Compare resume_text against jd_text using the provided master skill_list.

    Returns a dict with:
      score            - float, 0-100
      matched_skills   - list[str] skills present in both resume & JD
      missing_skills   - list[str] skills required by JD but absent from resume
      suggestions      - list[str] actionable improvement tips
    """
    jd_skills = find_skills_in_text(jd_text, skill_list)
    resume_skills = set(find_skills_in_text(resume_text, skill_list))

    if not jd_skills:
        # No recognizable skills in the JD -- fall back to generic token overlap
        jd_tokens = set(tokenize(jd_text))
        resume_tokens = set(tokenize(resume_text))
        overlap = jd_tokens & resume_tokens
        score = round((len(overlap) / max(len(jd_tokens), 1)) * 100, 2)
        return {
            "score": min(score, 100.0),
            "matched_skills": sorted(overlap),
            "missing_skills": [],
            "suggestions": [
                "Add a clear 'Skills' section listing your technical and soft skills.",
                "Mirror the key terminology used in the job description where genuinely applicable.",
            ],
        }

    matched = [s for s in jd_skills if s in resume_skills]
    missing = [s for s in jd_skills if s not in resume_skills]
    score = round((len(matched) / len(jd_skills)) * 100, 2)

    suggestions = generate_suggestions(resume_text, missing)

    return {
        "score": score,
        "matched_skills": matched,
        "missing_skills": missing,
        "suggestions": suggestions,
    }


def generate_suggestions(resume_text, missing_skills):
    """Rule-based improvement suggestions."""
    tips = []

    if missing_skills:
        shown = ", ".join(missing_skills[:6])
        tips.append(f"Consider adding these missing but relevant keywords if you have experience with them: {shown}.")

    word_count = len(resume_text.split())
    if word_count < 150:
        tips.append("Your resume looks quite short -- add more detail about your projects, responsibilities, and achievements.")
    elif word_count > 1200:
        tips.append("Your resume is quite long -- consider trimming it to the most relevant one to two pages.")

    if not re.search(r"\d", resume_text):
        tips.append("Quantify your achievements with numbers where possible (e.g., 'improved performance by 20%').")

    if "summary" not in resume_text.lower() and "objective" not in resume_text.lower():
        tips.append("Add a short professional summary at the top highlighting your key strengths.")

    if not tips:
        tips.append("Great match! Do a final proofread and tailor the wording slightly to mirror the job description.")

    return tips

"""
AI Resume Analyzer - Flask backend.

Run with:
    python app.py

Make sure MySQL is running and schema.sql has been imported first:
    mysql -u root -p < schema.sql
"""
import json
import os
import uuid
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, send_file, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from config import (
    SECRET_KEY, UPLOAD_FOLDER, REPORT_FOLDER, ALLOWED_EXTENSIONS, MAX_CONTENT_LENGTH,
    SKIP_EMAIL_VERIFICATION,
)
from utils.db import run_query
from utils.parser import extract_text, allowed_file
from utils.matcher import compute_match
from utils.report import build_report
from utils import ai_features
from utils.ai_features import AIConfigError, AIResponseError
from utils.github_verifier import cross_verify, GitHubError
from utils.emailer import (
    smtp_configured, is_valid_email_format, read_token, send_verification_email,
    send_password_reset_email, read_reset_token, reset_token_matches,
)

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORT_FOLDER, exist_ok=True)


# ----------------------------------------------------------------
# Footer / contact info (change these in .env, or edit the defaults here)
# ----------------------------------------------------------------
SITE_LINKS = {
    "linkedin": os.environ.get("LINKEDIN_URL", "https://www.linkedin.com/").strip(),
    "youtube": os.environ.get("YOUTUBE_URL", "https://www.youtube.com/").strip(),
    "instagram": os.environ.get("INSTAGRAM_URL", "https://www.instagram.com/").strip(),
    "email": os.environ.get("CONTACT_EMAIL", "your-email@example.com").strip(),
}


@app.context_processor
def inject_site_links():
    """Makes `site` (social links + email) and `current_year` available in every template."""
    from datetime import datetime
    return {"site": SITE_LINKS, "current_year": datetime.now().year}


# ----------------------------------------------------------------
# Auth helpers
# ----------------------------------------------------------------
def mail_notice(sent_text):
    """Honest flash text: only claim an email was sent if SMTP is actually configured."""
    if smtp_configured():
        return sent_text
    return ("Email sending is not set up on this server, so no email was sent. "
            "(Developer mode: the link was printed in the server terminal.)")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


# ----------------------------------------------------------------
# Public pages
# ----------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("All fields are required.", "error")
            return redirect(url_for("register"))
        if not is_valid_email_format(email):
            flash("Please enter a valid email address.", "error")
            return redirect(url_for("register"))

        existing = run_query("SELECT user_id, email_verified FROM users WHERE email = %s", (email,), fetch_one=True)
        if existing:
            if not existing["email_verified"]:
                flash("This email is registered but not verified yet. Use 'Resend verification email' below.", "error")
                return redirect(url_for("resend_verification"))
            flash("An account with this email already exists.", "error")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)
        if SKIP_EMAIL_VERIFICATION:
            # Dev-only mode (SKIP_EMAIL_VERIFICATION=1 in .env): no email needed
            run_query(
                "INSERT INTO users (name, email, password_hash, role, email_verified) VALUES (%s, %s, %s, 'user', 1)",
                (name, email, password_hash),
                commit=True,
            )
            flash("Account created! You can log in now.", "success")
            return redirect(url_for("login"))
        run_query(
            "INSERT INTO users (name, email, password_hash, role, email_verified) VALUES (%s, %s, %s, 'user', 0)",
            (name, email, password_hash),
            commit=True,
        )
        if send_verification_email(name, email):
            flash("Account created! " + mail_notice("We sent a verification link to your email. Please verify it, then log in."), "success")
        else:
            flash("Account created, but we couldn't send the verification email. Use 'Resend verification email'.", "error")
            return redirect(url_for("resend_verification"))
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = run_query("SELECT * FROM users WHERE email = %s", (email,), fetch_one=True)
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "error")
            return redirect(url_for("login"))
        if not user["email_verified"]:
            flash("Please verify your email before logging in. Check your inbox, or request a new link below.", "error")
            return redirect(url_for("resend_verification"))

        session["user_id"] = user["user_id"]
        session["name"] = user["name"]
        session["role"] = user["role"]
        flash(f"Welcome back, {user['name']}!", "success")
        return redirect(url_for("admin_panel") if user["role"] == "admin" else url_for("upload_page"))

    return render_template("login.html")


@app.route("/verify/<token>")
def verify_email(token):
    email, error = read_token(token)
    if error == "expired":
        flash("This verification link has expired. Request a new one below.", "error")
        return redirect(url_for("resend_verification"))
    if error:
        flash("This verification link is invalid.", "error")
        return redirect(url_for("login"))

    user = run_query("SELECT user_id, email_verified FROM users WHERE email = %s", (email,), fetch_one=True)
    if not user:
        flash("This verification link is invalid.", "error")
        return redirect(url_for("login"))
    if user["email_verified"]:
        flash("Your email is already verified. Please log in.", "success")
    else:
        run_query("UPDATE users SET email_verified = 1 WHERE user_id = %s", (user["user_id"],), commit=True)
        flash("Email verified successfully! You can now log in.", "success")
    return redirect(url_for("login"))


@app.route("/resend-verification", methods=["GET", "POST"])
def resend_verification():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not is_valid_email_format(email):
            flash("Please enter a valid email address.", "error")
            return redirect(url_for("resend_verification"))

        user = run_query("SELECT name, email_verified FROM users WHERE email = %s", (email,), fetch_one=True)
        if user and not user["email_verified"]:
            send_verification_email(user["name"], email)
        # Same message either way, so this page can't be used to discover which emails are registered
        flash(mail_notice("If that email has an unverified account, a new verification link has been sent."), "success")
        return redirect(url_for("login"))

    return render_template("resend_verification.html")


MIN_PASSWORD_LENGTH = 6


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not is_valid_email_format(email):
            flash("Please enter a valid email address.", "error")
            return redirect(url_for("forgot_password"))

        user = run_query("SELECT name, password_hash FROM users WHERE email = %s", (email,), fetch_one=True)
        if user:
            send_password_reset_email(user["name"], email, user["password_hash"])
        # Same message either way, so this page can't be used to discover which emails are registered
        flash(mail_notice("If an account exists for that email, a password reset link has been sent."), "success")
        return redirect(url_for("login"))

    return render_template("forgot_password.html")


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    payload, error = read_reset_token(token)
    if error == "expired":
        flash("This reset link has expired. Please request a new one.", "error")
        return redirect(url_for("forgot_password"))
    if error:
        flash("This reset link is invalid.", "error")
        return redirect(url_for("forgot_password"))

    user = run_query("SELECT user_id, password_hash FROM users WHERE email = %s", (payload["e"],), fetch_one=True)
    # The fingerprint check makes the link single-use: after a reset the old hash is gone
    if not user or not reset_token_matches(payload, user["password_hash"]):
        flash("This reset link is invalid or has already been used. Please request a new one.", "error")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if len(password) < MIN_PASSWORD_LENGTH:
            flash(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.", "error")
            return redirect(url_for("reset_password", token=token))
        if password != confirm:
            flash("Passwords do not match.", "error")
            return redirect(url_for("reset_password", token=token))

        # Opening the emailed link also proves the address is real, so mark it verified
        run_query(
            "UPDATE users SET password_hash = %s, email_verified = 1 WHERE user_id = %s",
            (generate_password_hash(password), user["user_id"]),
            commit=True,
        )
        flash("Password updated! You can now log in with your new password.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html", token=token)


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


# ----------------------------------------------------------------
# Core resume analysis flow
# ----------------------------------------------------------------
@app.route("/upload")
@login_required
def upload_page():
    return render_template("upload.html")


@app.route("/api/analyze", methods=["POST"])
@login_required
def analyze_resume():
    resume_file = request.files.get("resume")
    jd_title = request.form.get("jd_title", "").strip()
    jd_text = request.form.get("job_description", "").strip()

    if not resume_file or resume_file.filename == "":
        return jsonify({"error": "Please choose a resume file to upload."}), 400
    if not allowed_file(resume_file.filename, ALLOWED_EXTENSIONS):
        return jsonify({"error": "Only PDF and DOCX files are supported."}), 400
    if not jd_text:
        return jsonify({"error": "Please paste a job description to compare against."}), 400

    # Save file with a unique name to avoid collisions
    original_name = secure_filename(resume_file.filename)
    unique_name = f"{uuid.uuid4().hex}_{original_name}"
    file_path = os.path.join(UPLOAD_FOLDER, unique_name)
    resume_file.save(file_path)

    try:
        resume_text = extract_text(file_path)
    except Exception:
        return jsonify({"error": "Could not read the uploaded file. Please try a different file."}), 400

    if not resume_text.strip():
        return jsonify({"error": "No readable text found in the resume. Try a different file."}), 400

    # Save resume + JD records
    resume_id = run_query(
        "INSERT INTO resumes (user_id, file_name, file_path, extracted_text) VALUES (%s, %s, %s, %s)",
        (session["user_id"], original_name, file_path, resume_text),
        commit=True,
    )
    jd_id = run_query(
        "INSERT INTO job_descriptions (user_id, jd_title, jd_text) VALUES (%s, %s, %s)",
        (session["user_id"], jd_title, jd_text),
        commit=True,
    )

    # Load master skills list and compute the match
    skills_rows = run_query("SELECT skill_name FROM skills_master", fetch=True)
    skill_list = [row["skill_name"] for row in skills_rows]
    result = compute_match(resume_text, jd_text, skill_list)

    result_id = run_query(
        """INSERT INTO analysis_results
           (resume_id, jd_id, match_score, matched_skills, missing_skills, suggestions)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (
            resume_id, jd_id, result["score"],
            ", ".join(result["matched_skills"]),
            ", ".join(result["missing_skills"]),
            " | ".join(result["suggestions"]),
        ),
        commit=True,
    )

    return jsonify({
        "result_id": result_id,
        "score": result["score"],
        "matched_skills": result["matched_skills"],
        "missing_skills": result["missing_skills"],
        "suggestions": result["suggestions"],
    })


@app.route("/dashboard")
@login_required
def dashboard():
    history = run_query(
        """SELECT r.result_id, r.match_score, r.analyzed_at, res.file_name, jd.jd_title
           FROM analysis_results r
           JOIN resumes res ON r.resume_id = res.resume_id
           JOIN job_descriptions jd ON r.jd_id = jd.jd_id
           WHERE res.user_id = %s
           ORDER BY r.analyzed_at DESC""",
        (session["user_id"],),
        fetch=True,
    )
    latest = history[0] if history else None
    latest_detail = None
    if latest:
        latest_detail = run_query(
            "SELECT * FROM analysis_results WHERE result_id = %s",
            (latest["result_id"],), fetch_one=True,
        )
    return render_template("dashboard.html", history=history, latest=latest_detail)


@app.route("/report/<int:result_id>")
@login_required
def download_report(result_id):
    row = run_query(
        """SELECT r.*, res.file_name, res.user_id AS resume_owner, jd.jd_title, u.name AS user_name
           FROM analysis_results r
           JOIN resumes res ON r.resume_id = res.resume_id
           JOIN job_descriptions jd ON r.jd_id = jd.jd_id
           JOIN users u ON res.user_id = u.user_id
           WHERE r.result_id = %s""",
        (result_id,), fetch_one=True,
    )
    if not row or row["resume_owner"] != session["user_id"]:
        abort(404)

    result = {
        "score": row["match_score"],
        "matched_skills": [s for s in (row["matched_skills"] or "").split(", ") if s],
        "missing_skills": [s for s in (row["missing_skills"] or "").split(", ") if s],
        "suggestions": (row["suggestions"] or "").split(" | "),
    }
    report_path = os.path.join(REPORT_FOLDER, f"report_{result_id}.pdf")
    build_report(report_path, row["user_name"], row["file_name"], row["jd_title"], result)
    return send_file(report_path, as_attachment=True, download_name=f"resume_analysis_report_{result_id}.pdf")


# ----------------------------------------------------------------
# AI career tools (LLM) + GitHub cross-verifier
# ----------------------------------------------------------------
def _get_owned_analysis(result_id):
    """Fetch resume text, JD text and missing skills for an analysis owned by the logged-in user."""
    return run_query(
        """SELECT r.result_id, r.missing_skills, res.extracted_text AS resume_text, jd.jd_text
           FROM analysis_results r
           JOIN resumes res ON r.resume_id = res.resume_id
           JOIN job_descriptions jd ON r.jd_id = jd.jd_id
           WHERE r.result_id = %s AND res.user_id = %s""",
        (result_id, session["user_id"]), fetch_one=True,
    )


def _missing_list(row):
    return [s for s in (row["missing_skills"] or "").split(", ") if s]


# feature key -> function(row) -> dict
AI_FEATURES = {
    "star_rewrite": lambda row: ai_features.star_rewrite(row["resume_text"]),
    "roadmap": lambda row: ai_features.learning_roadmap(row["jd_text"], _missing_list(row)),
    "interview": lambda row: ai_features.interview_questions(row["jd_text"], row["resume_text"]),
    "red_flags": lambda row: ai_features.red_flag_check(row["resume_text"]),
    "pitch": lambda row: ai_features.elevator_pitch(row["resume_text"]),
    "trap": lambda row: ai_features.interviewer_traps(row["jd_text"], row["resume_text"]),
    "rejection": lambda row: ai_features.rejection_reasons(row["jd_text"], row["resume_text"], _missing_list(row)),
    "projects": lambda row: ai_features.project_ideas(row["jd_text"], _missing_list(row)),
    "roles": lambda row: ai_features.best_fit_roles(row["resume_text"]),
    "hr_email": lambda row: ai_features.hr_email_draft(row["jd_text"], row["resume_text"]),
    "linkedin": lambda row: ai_features.linkedin_profile(row["jd_text"], row["resume_text"]),
}


@app.route("/api/ai/<feature>", methods=["POST"])
@login_required
def run_ai_feature(feature):
    if feature not in AI_FEATURES:
        return jsonify({"error": "Unknown feature."}), 404

    payload = request.get_json(silent=True) or {}
    try:
        result_id = int(payload.get("result_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Missing analysis id."}), 400
    refresh = bool(payload.get("refresh"))

    row = _get_owned_analysis(result_id)
    if not row:
        return jsonify({"error": "Analysis not found."}), 404

    # Serve cached output unless the user asked to regenerate
    if not refresh:
        cached = run_query(
            "SELECT output_json FROM ai_feature_results WHERE result_id = %s AND feature = %s",
            (result_id, feature), fetch_one=True,
        )
        if cached:
            return jsonify({"feature": feature, "cached": True, "data": json.loads(cached["output_json"])})

    try:
        data = AI_FEATURES[feature](row)
    except AIConfigError as exc:
        return jsonify({"error": str(exc)}), 503
    except AIResponseError as exc:
        return jsonify({"error": str(exc)}), 502
    except Exception:
        app.logger.exception("AI feature '%s' failed", feature)
        return jsonify({"error": "The AI service is unavailable right now. Please try again."}), 502

    if not data.get("empty"):
        run_query(
            """INSERT INTO ai_feature_results (result_id, feature, output_json)
               VALUES (%s, %s, %s)
               ON DUPLICATE KEY UPDATE output_json = VALUES(output_json), created_at = CURRENT_TIMESTAMP""",
            (result_id, feature, json.dumps(data)), commit=True,
        )
    return jsonify({"feature": feature, "cached": False, "data": data})


@app.route("/api/voice-evaluate", methods=["POST"])
@login_required
def voice_evaluate():
    """Score one spoken (or typed) mock-interview answer. Not cached: every answer is different."""
    payload = request.get_json(silent=True) or {}
    try:
        result_id = int(payload.get("result_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Missing analysis id."}), 400

    question = (payload.get("question") or "").strip()
    answer = (payload.get("answer") or "").strip()
    try:
        duration = max(0.0, min(float(payload.get("duration") or 0), 900.0))
    except (TypeError, ValueError):
        duration = 0.0

    if not question:
        return jsonify({"error": "Missing question."}), 400
    if len(answer.split()) < 5:
        return jsonify({"error": "Your answer is too short. Please speak or type at least a couple of sentences."}), 400

    row = _get_owned_analysis(result_id)
    if not row:
        return jsonify({"error": "Analysis not found."}), 404

    try:
        data = ai_features.evaluate_voice_answer(question, answer, row["jd_text"], duration)
    except AIConfigError as exc:
        return jsonify({"error": str(exc)}), 503
    except AIResponseError as exc:
        return jsonify({"error": str(exc)}), 502
    except Exception:
        app.logger.exception("Voice evaluation failed")
        return jsonify({"error": "The AI service is unavailable right now. Please try again."}), 502
    return jsonify({"data": data})


@app.route("/api/github-verify", methods=["POST"])
@login_required
def github_verify():
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    try:
        result_id = int(payload.get("result_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Missing analysis id."}), 400
    if not username:
        return jsonify({"error": "Please enter your GitHub username."}), 400

    row = _get_owned_analysis(result_id)
    if not row:
        return jsonify({"error": "Analysis not found."}), 404

    try:
        data = cross_verify(username, row["resume_text"])
    except GitHubError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"feature": "github", "data": data})


# ----------------------------------------------------------------
# Admin panel
# ----------------------------------------------------------------
@app.route("/admin")
@login_required
@admin_required
def admin_panel():
    users = run_query("SELECT user_id, name, email, role, created_at FROM users ORDER BY created_at DESC", fetch=True)
    skills = run_query("SELECT * FROM skills_master ORDER BY category, skill_name", fetch=True)
    stats = run_query(
        """SELECT COUNT(*) AS total_users FROM users""", fetch_one=True
    )
    resume_count = run_query("SELECT COUNT(*) AS total_resumes FROM resumes", fetch_one=True)
    avg_score = run_query("SELECT ROUND(AVG(match_score),2) AS avg_score FROM analysis_results", fetch_one=True)

    return render_template(
        "admin.html", users=users, skills=skills,
        total_users=stats["total_users"],
        total_resumes=resume_count["total_resumes"],
        avg_score=avg_score["avg_score"] or 0,
    )


@app.route("/admin/skills/add", methods=["POST"])
@login_required
@admin_required
def add_skill():
    skill_name = request.form.get("skill_name", "").strip()
    category = request.form.get("category", "General").strip() or "General"
    if skill_name:
        run_query(
            "INSERT IGNORE INTO skills_master (skill_name, category) VALUES (%s, %s)",
            (skill_name, category), commit=True,
        )
        flash(f"Added skill: {skill_name}", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/skills/<int:skill_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_skill(skill_id):
    run_query("DELETE FROM skills_master WHERE skill_id = %s", (skill_id,), commit=True)
    flash("Skill removed.", "success")
    return redirect(url_for("admin_panel"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)

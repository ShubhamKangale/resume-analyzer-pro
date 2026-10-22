"""
GitHub cross-verifier. No LLM involved.

Takes a GitHub username, calls  https://api.github.com/users/{username}/repos
, reads each repo's `language` field and checks whether the programming
languages claimed on the resume really appear in the candidate's projects.

Limitation: GitHub's `language` field is a repo's *primary* language only.
"""
import re
from collections import defaultdict

import requests

from config import GITHUB_TOKEN

API_URL = "https://api.github.com/users/{username}/repos"
USERNAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
MAX_PAGES = 3          # 3 x 100 = up to 300 repos
TIMEOUT = 10


class GitHubError(Exception):
    """Raised with a user-friendly message."""


# Languages we look for in the resume. Short/ambiguous names (C, R, Go)
# are matched case-sensitively to avoid false hits on ordinary words.
RESUME_LANGUAGES = [
    "Python", "Java", "JavaScript", "TypeScript", "C", "C++", "C#", "Go", "Rust",
    "Ruby", "PHP", "Swift", "Kotlin", "Scala", "R", "Dart", "HTML", "CSS", "SQL",
    "Shell", "MATLAB", "Perl", "Lua", "Haskell",
]
CASE_SENSITIVE = {"C", "R", "Go"}
RESUME_ALIASES = {"Golang": "Go"}

# GitHub language names that count as evidence for a resume language.
GITHUB_ALIASES = {
    "Python": {"Python", "Jupyter Notebook"},
    "CSS": {"CSS", "SCSS", "Less"},
    "SQL": {"PLpgSQL", "TSQL", "PLSQL", "SQL"},
    "Shell": {"Shell", "PowerShell", "Batchfile"},
}


def _pattern(term):
    flags = 0 if term in CASE_SENSITIVE else re.IGNORECASE
    return re.compile(r"(?<![A-Za-z0-9+#])" + re.escape(term) + r"(?![A-Za-z0-9+#])", flags)


_PATTERNS = {lang: _pattern(lang) for lang in RESUME_LANGUAGES}
_PATTERNS.update({alias: _pattern(alias) for alias in RESUME_ALIASES})


def languages_in_resume(resume_text):
    found = []
    for lang in RESUME_LANGUAGES:
        if _PATTERNS[lang].search(resume_text):
            found.append(lang)
    for alias, canonical in RESUME_ALIASES.items():
        if canonical not in found and _PATTERNS[alias].search(resume_text):
            found.append(canonical)
    return found


def fetch_repos(username):
    """Return the list of public repos (JSON dicts) for `username`."""
    username = (username or "").strip().lstrip("@")
    if not USERNAME_RE.match(username):
        raise GitHubError("That doesn't look like a valid GitHub username.")

    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ai-resume-analyzer"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    repos = []
    for page in range(1, MAX_PAGES + 1):
        try:
            resp = requests.get(
                API_URL.format(username=username),
                headers=headers,
                params={"per_page": 100, "page": page},
                timeout=TIMEOUT,
            )
        except requests.RequestException:
            raise GitHubError("Could not reach GitHub. Please try again in a moment.")

        if resp.status_code == 404:
            raise GitHubError(f"GitHub user '{username}' was not found.")
        if resp.status_code in (403, 429):
            raise GitHubError("GitHub rate limit reached. Try again later or set GITHUB_TOKEN on the server.")
        if resp.status_code != 200:
            raise GitHubError(f"GitHub returned an unexpected error ({resp.status_code}).")

        batch = resp.json()
        repos.extend(batch)
        if len(batch) < 100:
            break
    return repos


def verify_languages(resume_text, repos):
    """Compare resume languages with the `language` field of the repos."""
    # Forks aren't the candidate's own work, so they don't count as evidence.
    own = [r for r in repos if not r.get("fork")]

    by_language = defaultdict(list)
    for repo in own:
        lang = repo.get("language")
        if lang:
            by_language[lang].append(repo.get("name", ""))

    claimed = languages_in_resume(resume_text)

    verified, unverified = [], []
    matched_github_langs = set()
    for lang in claimed:
        accepted = GITHUB_ALIASES.get(lang, {lang})
        names = []
        for gh_lang in accepted:
            if gh_lang in by_language:
                names.extend(by_language[gh_lang])
                matched_github_langs.add(gh_lang)
        if names:
            verified.append({"language": lang, "repo_count": len(names), "sample_repos": names[:3]})
        else:
            unverified.append(lang)

    not_on_resume = sorted(l for l in by_language if l not in matched_github_langs)
    pct = round(len(verified) / len(claimed) * 100) if claimed else 0

    return {
        "repos_checked": len(own),
        "forks_skipped": len(repos) - len(own),
        "claimed_languages": claimed,
        "verified": verified,
        "unverified": unverified,
        "github_only_languages": not_on_resume,
        "verified_percent": pct,
    }


def cross_verify(username, resume_text):
    repos = fetch_repos(username)
    result = verify_languages(resume_text, repos)
    result["username"] = username.strip().lstrip("@")
    return result

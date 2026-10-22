// AI career tools + GitHub verifier UI (runs on /upload after an analysis).
// All text is inserted with textContent -- never innerHTML -- so LLM output can't inject markup.

const aiOutput = document.getElementById("aiOutput");
const aiOutputTitle = document.getElementById("aiOutputTitle");
const aiOutputBody = document.getElementById("aiOutputBody");
const aiError = document.getElementById("aiError");
const aiRegenBtn = document.getElementById("aiRegenBtn");
const githubUser = document.getElementById("githubUser");
const githubBtn = document.getElementById("githubBtn");

const TITLES = {
  star_rewrite: "STAR method rewrites",
  roadmap: "4-week learning roadmap",
  interview: "Mock interview questions",
  red_flags: "Red flags & buzzwords",
  pitch: "Elevator pitch",
  trap: "Interviewer trap predictor",
  rejection: "Why you might get rejected",
  projects: "Project ideas to close your skill gaps",
  roles: "Best-fit roles for your resume",
  hr_email: "HR email drafts",
  linkedin: "LinkedIn headline & About",
  github: "GitHub cross-verification",
};

let lastFeature = null;
let busyButton = null;

// Reset the tools panel whenever a fresh analysis finishes
document.addEventListener("analysis:ready", () => {
  aiOutput.hidden = true;
  aiOutputBody.innerHTML = "";
});

document.querySelectorAll("[data-feature]").forEach((btn) =>
  btn.addEventListener("click", () => runFeature(btn.dataset.feature, false, btn))
);
aiRegenBtn.addEventListener("click", () => {
  if (lastFeature && lastFeature !== "github") runFeature(lastFeature, true, aiRegenBtn);
});
githubBtn.addEventListener("click", runGithub);
githubUser.addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); runGithub(); }
});

async function runFeature(feature, refresh, btn) {
  await callApi(`/api/ai/${feature}`, { result_id: window.currentResultId, refresh }, feature, btn);
}

async function runGithub() {
  await callApi(
    "/api/github-verify",
    { result_id: window.currentResultId, username: githubUser.value },
    "github",
    githubBtn
  );
}

async function callApi(url, body, feature, btn) {
  if (busyButton) return;
  lastFeature = feature;
  busyButton = btn;
  const originalLabel = btn.textContent;
  setAllDisabled(true);
  btn.textContent = "Working...";

  showOutput(feature);
  aiOutputBody.textContent = "";
  aiError.hidden = true;

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const json = await res.json();
    if (!res.ok) {
      aiError.textContent = json.error || "Something went wrong.";
      aiError.hidden = false;
      return;
    }
    RENDERERS[feature](json.data);
    aiRegenBtn.hidden = feature === "github" || !!(json.data && json.data.empty);
  } catch (err) {
    aiError.textContent = "Could not reach the server. Please try again.";
    aiError.hidden = false;
  } finally {
    btn.textContent = originalLabel;
    setAllDisabled(false);
    busyButton = null;
    aiOutput.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}

function setAllDisabled(state) {
  document.querySelectorAll("#aiTools button").forEach((b) => (b.disabled = state));
}

function showOutput(feature) {
  aiOutput.hidden = false;
  aiOutputTitle.textContent = TITLES[feature];
  aiRegenBtn.hidden = true;
}

// ---- tiny DOM helpers ----
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function listOf(items, tag = "ul") {
  const list = el(tag, "ai-list");
  items.forEach((t) => list.appendChild(el("li", null, t)));
  return list;
}
function section(title, ...children) {
  const wrap = el("div", "ai-section");
  if (title) wrap.appendChild(el("h5", null, title));
  children.forEach((c) => wrap.appendChild(c));
  return wrap;
}
function emptyNote(text) { return el("p", "ai-muted", text); }
function copyButton(text, label) {
  const btn = el("button", "btn-ghost ai-copy", label);
  btn.type = "button";
  btn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(text);
      btn.textContent = "Copied!";
    } catch (e) {
      btn.textContent = "Copy failed";
    }
    setTimeout(() => (btn.textContent = label), 1500);
  });
  return btn;
}
function emailCard(heading, mail) {
  const card = el("div", "ai-card");
  card.appendChild(el("p", "ai-label", heading));
  card.appendChild(el("p", "ai-label", "Subject"));
  card.appendChild(el("p", "ai-strong", mail.subject));
  card.appendChild(el("p", "ai-label", "Body"));
  card.appendChild(el("p", "ai-email-body", mail.body));
  const row = el("div", "ai-copy-row");
  row.appendChild(copyButton(`Subject: ${mail.subject}\n\n${mail.body}`, "Copy email"));
  const open = el("a", "btn-ghost ai-copy", "Open in email app");
  open.href = `mailto:?subject=${encodeURIComponent(mail.subject)}&body=${encodeURIComponent(mail.body)}`;
  row.appendChild(open);
  card.appendChild(row);
  return card;
}

// ---- renderers ----
const RENDERERS = {
  star_rewrite(data) {
    data.rewrites.forEach((r, i) => {
      const card = el("div", "ai-card");
      card.appendChild(el("p", "ai-label", `Weak point #${i + 1}`));
      card.appendChild(el("p", "ai-original", r.original_point));
      card.appendChild(el("p", "ai-label ai-label-good", "STAR rewrite"));
      card.appendChild(el("p", "ai-rewritten", r.rewritten_point));
      aiOutputBody.appendChild(card);
    });
  },

  roadmap(data) {
    if (data.empty) { aiOutputBody.appendChild(emptyNote(data.message)); return; }
    aiOutputBody.appendChild(el("p", "ai-target", `Target skill: ${data.target_skill}`));
    for (let i = 1; i <= 4; i++) {
      const card = el("div", "ai-card");
      card.appendChild(el("p", "ai-label", `Week ${i}`));
      card.appendChild(el("p", null, data[`week_${i}`] || "—"));
      aiOutputBody.appendChild(card);
    }
  },

  interview(data) {
    aiOutputBody.appendChild(listOf(data.interview_questions, "ol"));
  },

  red_flags(data) {
    const chips = el("ul", "keyword-list keyword-miss");
    data.overused_buzzwords.forEach((w) => chips.appendChild(el("li", null, w)));
    aiOutputBody.appendChild(
      section("Overused buzzwords",
        data.overused_buzzwords.length ? chips : emptyNote("No overused buzzwords found."))
    );
    aiOutputBody.appendChild(
      section("Improvement suggestions",
        data.improvement_suggestions.length ? listOf(data.improvement_suggestions) : emptyNote("No suggestions."))
    );
  },

  pitch(data) {
    aiOutputBody.appendChild(el("blockquote", "ai-pitch", data.elevator_pitch));
    aiOutputBody.appendChild(el("p", "ai-muted", `${data.word_count} words`));
    const copy = el("button", "btn-ghost", "Copy pitch");
    copy.type = "button";
    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(data.elevator_pitch);
        copy.textContent = "Copied!";
      } catch (e) {
        copy.textContent = "Copy failed";
      }
      setTimeout(() => (copy.textContent = "Copy pitch"), 1500);
    });
    aiOutputBody.appendChild(copy);
  },

  trap(data) {
    data.traps.forEach((t, i) => {
      const card = el("div", "ai-card");
      card.appendChild(el("p", "ai-label", `Weak spot #${i + 1}`));
      card.appendChild(el("p", "ai-strong", t.weak_spot));
      if (t.why_risky) {
        card.appendChild(el("p", "ai-label", "Why it's risky"));
        card.appendChild(el("p", null, t.why_risky));
      }
      card.appendChild(el("p", "ai-label", "Interviewer will ask"));
      card.appendChild(el("p", "ai-question", t.likely_question));
      if (t.smart_answer_tip) {
        card.appendChild(el("p", "ai-label ai-label-good", "Smart answer tip"));
        card.appendChild(el("p", "ai-rewritten", t.smart_answer_tip));
      }
      aiOutputBody.appendChild(card);
    });
  },

  rejection(data) {
    if (data.verdict) aiOutputBody.appendChild(el("p", "ai-target", data.verdict));
    data.reasons.forEach((r, i) => {
      const card = el("div", "ai-card");
      const head = el("p", "ai-label", `Reason #${i + 1} `);
      head.appendChild(el("span", `ai-sev ai-sev-${r.severity.toLowerCase()}`, r.severity));
      card.appendChild(head);
      card.appendChild(el("p", "ai-strong", r.reason));
      if (r.how_to_fix) {
        card.appendChild(el("p", "ai-label ai-label-good", "How to fix"));
        card.appendChild(el("p", "ai-rewritten", r.how_to_fix));
      }
      aiOutputBody.appendChild(card);
    });
  },

  projects(data) {
    if (data.empty) { aiOutputBody.appendChild(emptyNote(data.message)); return; }
    data.projects.forEach((p, i) => {
      const card = el("div", "ai-card");
      card.appendChild(el("p", "ai-label", `Project #${i + 1}`));
      card.appendChild(el("p", "ai-strong", p.title));
      if (p.description) card.appendChild(el("p", null, p.description));
      if (p.skills_covered.length) {
        const chips = el("ul", "keyword-list");
        p.skills_covered.forEach((sk) => chips.appendChild(el("li", null, sk)));
        card.appendChild(el("p", "ai-label", "Skills you will cover"));
        card.appendChild(chips);
      }
      if (p.key_features.length) {
        card.appendChild(el("p", "ai-label", "Key features"));
        card.appendChild(listOf(p.key_features));
      }
      if (p.resume_bullet) {
        card.appendChild(el("p", "ai-label ai-label-good", "Resume bullet (after you build it)"));
        card.appendChild(el("blockquote", "ai-pitch", p.resume_bullet));
      }
      aiOutputBody.appendChild(card);
    });
  },

  roles(data) {
    data.roles.forEach((r) => {
      const card = el("div", "ai-card");
      card.appendChild(el("p", "ai-strong", r.role));
      const bar = el("div", "fit-bar");
      const fill = el("div", "fit-fill");
      fill.style.width = `${Number(r.fit_percent) || 0}%`;
      bar.appendChild(fill);
      card.appendChild(bar);
      card.appendChild(el("p", "ai-label", `${r.fit_percent}% fit`));
      if (r.reason) card.appendChild(el("p", null, r.reason));
      if (r.skills_to_add.length) {
        const chips = el("ul", "keyword-list keyword-miss");
        r.skills_to_add.forEach((sk) => chips.appendChild(el("li", null, sk)));
        card.appendChild(el("p", "ai-label", "Add these to raise your fit"));
        card.appendChild(chips);
      }
      aiOutputBody.appendChild(card);
    });
    aiOutputBody.appendChild(
      emptyNote("Fit % is an AI estimate based only on your resume text. Treat it as guidance, not a guarantee.")
    );
  },

  hr_email(data) {
    aiOutputBody.appendChild(emailCard("1. Job application email", data.application_email));
    if (data.followup_email) {
      aiOutputBody.appendChild(emailCard("2. Follow-up email (send after ~1 week)", data.followup_email));
    }
    aiOutputBody.appendChild(
      emptyNote("Replace [HR Name], [Your Name] and [Company Name] before sending, and attach your resume.")
    );
  },

  linkedin(data) {
    const hl = el("div", "ai-section");
    hl.appendChild(el("h5", null, "Headline options (pick one)"));
    data.headlines.forEach((h, i) => {
      const card = el("div", "ai-card");
      card.appendChild(el("p", "ai-label", `Option ${i + 1} - ${h.length}/220 characters`));
      card.appendChild(el("p", "ai-strong", h));
      card.appendChild(copyButton(h, "Copy headline"));
      hl.appendChild(card);
    });
    aiOutputBody.appendChild(hl);

    const about = el("div", "ai-section");
    about.appendChild(el("h5", null, "About section"));
    about.appendChild(el("blockquote", "ai-pitch ai-email-body", data.about));
    about.appendChild(el("p", "ai-muted", `${data.about_words} words`));
    about.appendChild(copyButton(data.about, "Copy About"));
    aiOutputBody.appendChild(about);

    if (data.top_skills.length) {
      const chips = el("ul", "keyword-list");
      data.top_skills.forEach((sk) => chips.appendChild(el("li", null, sk)));
      aiOutputBody.appendChild(section("Skills to pin on your profile", chips));
    }
    aiOutputBody.appendChild(
      emptyNote("Read it once and adjust anything that does not sound like you before you publish it.")
    );
  },

  github(data) {
    aiOutputBody.appendChild(
      el("p", "ai-target",
        `${data.verified_percent}% of resume languages verified ` +
        `(${data.repos_checked} original repos checked for @${data.username}` +
        `${data.forks_skipped ? `, ${data.forks_skipped} forks skipped` : ""})`)
    );

    if (!data.claimed_languages.length) {
      aiOutputBody.appendChild(emptyNote("No programming languages were detected in the resume text."));
    }

    if (data.verified.length) {
      const items = data.verified.map(
        (v) => `${v.language} — ${v.repo_count} repo(s), e.g. ${v.sample_repos.join(", ")}`
      );
      aiOutputBody.appendChild(section("✓ Verified in your repos", listOf(items)));
    }
    if (data.unverified.length) {
      const chips = el("ul", "keyword-list keyword-miss");
      data.unverified.forEach((l) => chips.appendChild(el("li", null, l)));
      aiOutputBody.appendChild(section("✗ On resume, but no matching repo found", chips));
    }
    if (data.github_only_languages.length) {
      aiOutputBody.appendChild(
        section("On GitHub but not on resume — consider adding", listOf(data.github_only_languages))
      );
    }
    aiOutputBody.appendChild(
      emptyNote("Note: GitHub reports only each repo's primary language, and only public repos are checked.")
    );
  },
};

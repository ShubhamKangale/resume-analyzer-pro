// Handles the resume upload + analysis flow on the /upload page.

const form = document.getElementById("analyzeForm");
const dropZone = document.getElementById("dropZone");
const dropText = document.getElementById("dropText");
const fileInput = document.getElementById("resumeFile");
const analyzeBtn = document.getElementById("analyzeBtn");
const formError = document.getElementById("formError");
const resultPanel = document.getElementById("resultPanel");

// ---- Drag & drop wiring ----
dropZone.addEventListener("click", () => fileInput.click());

["dragenter", "dragover"].forEach((evt) =>
  dropZone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropZone.classList.add("drag-over");
  })
);

["dragleave", "drop"].forEach((evt) =>
  dropZone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropZone.classList.remove("drag-over");
  })
);

dropZone.addEventListener("drop", (e) => {
  const files = e.dataTransfer.files;
  if (files.length) {
    fileInput.files = files;
    updateDropText();
  }
});

fileInput.addEventListener("change", updateDropText);

function updateDropText() {
  if (fileInput.files.length) {
    dropText.textContent = fileInput.files[0].name;
  }
}

// ---- Submit handler ----
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  formError.hidden = true;
  resultPanel.hidden = true;

  if (!fileInput.files.length) {
    showError("Please choose a resume file.");
    return;
  }

  const formData = new FormData(form);
  analyzeBtn.disabled = true;
  analyzeBtn.textContent = "Analyzing...";

  try {
    const response = await fetch("/api/analyze", { method: "POST", body: formData });
    const data = await response.json();

    if (!response.ok) {
      showError(data.error || "Something went wrong. Please try again.");
      return;
    }

    renderResult(data);
  } catch (err) {
    showError("Could not reach the server. Please try again.");
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = "Analyze resume";
  }
});

function showError(message) {
  formError.textContent = message;
  formError.hidden = false;
}

function renderResult(data) {
  window.currentResultId = data.result_id; // used by ai_tools.js
  document.dispatchEvent(new CustomEvent("analysis:ready"));
  resultPanel.hidden = false;
  animateScore(data.score);

  fillKeywordList("matchedList", data.matched_skills, "No direct keyword matches found.");
  fillKeywordList("missingList", data.missing_skills, "Nothing missing -- nice work!");

  const suggestionList = document.getElementById("suggestionList");
  suggestionList.innerHTML = "";
  data.suggestions.forEach((tip) => {
    const li = document.createElement("li");
    li.textContent = tip;
    suggestionList.appendChild(li);
  });

  const downloadBtn = document.getElementById("downloadReportBtn");
  downloadBtn.href = `/report/${data.result_id}`;
  downloadBtn.hidden = false;

  resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}

function fillKeywordList(elementId, items, emptyMessage) {
  const list = document.getElementById(elementId);
  list.innerHTML = "";
  if (!items.length) {
    const li = document.createElement("li");
    li.textContent = emptyMessage;
    list.appendChild(li);
    return;
  }
  items.forEach((skill) => {
    const li = document.createElement("li");
    li.textContent = skill;
    list.appendChild(li);
  });
}

function animateScore(target) {
  const el = document.getElementById("scoreValue");
  const duration = 700;
  const start = performance.now();

  function tick(now) {
    const progress = Math.min((now - start) / duration, 1);
    el.textContent = Math.round(progress * target);
    if (progress < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

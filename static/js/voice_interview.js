// Voice mock interview: questions come from the existing "interview" AI feature,
// answers are captured with the browser's Web Speech API (or typed), then scored by /api/voice-evaluate.
// All text is inserted with textContent -- never innerHTML.

(function () {
  const $ = (id) => document.getElementById(id);
  const panel = $("voicePanel");
  if (!panel) return;

  const launchBtn = $("voiceBtn"), closeBtn = $("voiceCloseBtn");
  const notice = $("voiceNotice"), errorEl = $("voiceError"), loading = $("voiceLoading");
  const stage = $("voiceStage"), summary = $("voiceSummary");
  const progress = $("voiceProgress"), questionEl = $("voiceQuestion");
  const speakQBtn = $("voiceSpeakQ"), langSel = $("voiceLang"), micBtn = $("voiceMicBtn");
  const statusEl = $("voiceStatus"), answerEl = $("voiceAnswer");
  const submitBtn = $("voiceSubmitBtn"), nextBtn = $("voiceNextBtn"), feedback = $("voiceFeedback");

  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  let questions = [], idx = 0, results = [];
  let recognition = null, listening = false, finalText = "";
  let speakingMs = 0, startedAt = 0, submitting = false;

  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function showError(msg) { errorEl.textContent = msg; errorEl.hidden = !msg; }

  // ---------- speech recognition ----------
  let restartTimer = null, quickEnds = 0, lastStart = 0;

  function stopListening() {
    if (!listening) return;
    listening = false;
    clearTimeout(restartTimer);
    speakingMs += Date.now() - startedAt;
    try { recognition && recognition.stop(); } catch (e) {}
    micBtn.textContent = "\uD83C\uDFA4 Start speaking";
    micBtn.classList.remove("is-recording");
    statusEl.hidden = true;
  }

  const FATAL = {
    "not-allowed": "Microphone permission is blocked. Click the lock icon next to the address bar, allow Microphone, then try again.",
    "service-not-allowed": "This browser blocked speech recognition. Use Chrome or Edge, or type your answer.",
    "audio-capture": "No working microphone was found. Check that a mic is connected and not used by another app.",
    "network": "Speech recognition needs a working internet connection (it runs on the browser's online service). Check your internet, or type your answer.",
    "language-not-supported": "This language is not supported for voice. Pick another language in the dropdown.",
  };

  // One recognition "session". Browsers end a session after a pause, so we
  // start a brand-new session (new object, short delay) until the user presses Stop.
  function beginSession() {
    recognition = new SR();
    recognition.lang = langSel.value;
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onstart = () => {
      lastStart = Date.now();
      statusEl.textContent = "\uD83C\uDF99 Mic is live. Speak now, press Stop when you are done.";
      statusEl.hidden = false;
    };
    recognition.onresult = (event) => {
      quickEnds = 0; // we are clearly hearing speech
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const text = event.results[i][0].transcript;
        if (event.results[i].isFinal) finalText += text.trim() + " ";
        else interim += text;
      }
      answerEl.value = finalText + interim;
    };
    recognition.onerror = (e) => {
      if (FATAL[e.error]) { showError(FATAL[e.error]); stopListening(); return; }
      // "no-speech" and "aborted" are harmless: onend will start a fresh session.
    };
    recognition.onend = () => {
      answerEl.value = finalText;
      if (!listening) return;
      const ranFor = Date.now() - lastStart;
      quickEnds = ranFor < 1500 ? quickEnds + 1 : 0;
      if (quickEnds >= 5) {
        showError("The microphone keeps stopping by itself. Try Chrome or Edge with internet on, or type your answer.");
        stopListening();
        return;
      }
      restartTimer = setTimeout(() => {
        if (!listening) return;
        try { beginSession(); } catch (err) {
          showError("Could not restart the microphone. Press Start speaking again.");
          stopListening();
        }
      }, 300);
    };
    recognition.start();
  }

  async function startListening() {
    if (!SR || listening) return;
    showError("");
    window.speechSynthesis && window.speechSynthesis.cancel();

    // Ask for mic permission first so we get a clear message if it is blocked or missing.
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach((t) => t.stop());
      } catch (err) {
        showError(err && err.name === "NotFoundError"
          ? FATAL["audio-capture"]
          : FATAL["not-allowed"]);
        return;
      }
    }

    finalText = answerEl.value.trim() ? answerEl.value.trim() + " " : "";
    quickEnds = 0;
    listening = true;
    startedAt = Date.now();
    lastStart = Date.now();
    micBtn.textContent = "\u23F9 Stop";
    micBtn.classList.add("is-recording");
    statusEl.textContent = "Starting microphone...";
    statusEl.hidden = false;
    try {
      beginSession();
    } catch (e) {
      showError("Could not start the microphone. Please try again.");
      stopListening();
    }
  }

  micBtn.addEventListener("click", () => (listening ? stopListening() : startListening()));

  speakQBtn.addEventListener("click", () => {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(questions[idx] || "");
    u.lang = langSel.value;
    window.speechSynthesis.speak(u);
  });

  // ---------- flow ----------
  function resetAll() {
    stopListening();
    window.speechSynthesis && window.speechSynthesis.cancel();
    questions = []; idx = 0; results = []; finalText = ""; speakingMs = 0; submitting = false;
    stage.hidden = true; summary.hidden = true; summary.textContent = "";
    feedback.textContent = ""; answerEl.value = ""; showError(""); loading.hidden = true;
  }

  function showQuestion() {
    stopListening();
    speakingMs = 0; finalText = "";
    answerEl.value = ""; answerEl.disabled = false;
    feedback.textContent = "";
    nextBtn.hidden = true;
    submitBtn.hidden = false; submitBtn.disabled = false; micBtn.disabled = !SR;
    progress.textContent = `Question ${idx + 1} of ${questions.length}`;
    questionEl.textContent = questions[idx];
    showError("");
  }

  async function open() {
    resetAll();
    if (!window.currentResultId) { panel.hidden = false; showError("Run an analysis first."); return; }
    panel.hidden = false;
    notice.textContent = SR
      ? "Allow microphone access when asked. Works best in Chrome or Edge. Browsers often skip filler sounds like \"umm\" and \"uh\", so the filler count is only approximate."
      : "Voice input is not supported in this browser (use Chrome or Edge). You can still type your answers.";
    micBtn.hidden = !SR;
    loading.hidden = false;
    panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    try {
      const res = await fetch("/api/ai/interview", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ result_id: window.currentResultId, refresh: false }),
      });
      const json = await res.json();
      if (!res.ok) { showError(json.error || "Could not load interview questions."); return; }
      questions = json.data.interview_questions || [];
      if (!questions.length) { showError("No questions were generated. Please try again."); return; }
      stage.hidden = false;
      showQuestion();
    } catch (e) {
      showError("Could not reach the server. Please try again.");
    } finally {
      loading.hidden = true;
    }
  }

  function scoreRow(label, value) {
    const row = el("div", "voice-score-row");
    row.appendChild(el("span", "voice-score-label", label));
    const bar = el("div", "fit-bar");
    const fill = el("div", "fit-fill");
    fill.style.width = `${(Number(value) || 0) * 10}%`;
    bar.appendChild(fill);
    row.appendChild(bar);
    row.appendChild(el("span", "voice-score-num", `${value}/10`));
    return row;
  }

  function renderFeedback(d) {
    feedback.textContent = "";
    const card = el("div", "ai-card");
    card.appendChild(el("p", "ai-target", `Overall: ${d.overall_score}/10`));
    card.appendChild(scoreRow("Relevance", d.relevance_score));
    card.appendChild(scoreRow("Clarity", d.clarity_score));
    card.appendChild(scoreRow("Confidence", d.confidence_score));

    const m = d.metrics || {};
    const bits = [`${m.word_count} words`];
    if (m.words_per_minute) bits.push(`${m.words_per_minute} words/min (ideal: 120-160)`);
    bits.push(`${m.filler_count} possible filler word(s)`);
    card.appendChild(el("p", "ai-muted", bits.join("  |  ")));
    const fillerKeys = Object.keys(m.fillers || {});
    if (fillerKeys.length) {
      card.appendChild(el("p", "ai-muted", "Fillers: " + fillerKeys.map((k) => `${k} x${m.fillers[k]}`).join(", ")));
    }
    if (d.strengths.length) {
      card.appendChild(el("p", "ai-label ai-label-good", "What went well"));
      const ul = el("ul", "ai-list"); d.strengths.forEach((t) => ul.appendChild(el("li", null, t))); card.appendChild(ul);
    }
    if (d.improvements.length) {
      card.appendChild(el("p", "ai-label", "Improve"));
      const ul = el("ul", "ai-list"); d.improvements.forEach((t) => ul.appendChild(el("li", null, t))); card.appendChild(ul);
    }
    if (d.better_answer) {
      card.appendChild(el("p", "ai-label ai-label-good", "A stronger version"));
      card.appendChild(el("blockquote", "ai-pitch", d.better_answer));
    }
    feedback.appendChild(card);
  }

  async function submitAnswer() {
    if (submitting) return;
    stopListening();
    const answer = answerEl.value.trim();
    if (answer.split(/\s+/).filter(Boolean).length < 5) {
      showError("Please give a longer answer (at least a couple of sentences).");
      return;
    }
    showError("");
    submitting = true;
    submitBtn.disabled = true; micBtn.disabled = true;
    const label = submitBtn.textContent;
    submitBtn.textContent = "Evaluating...";
    try {
      const res = await fetch("/api/voice-evaluate", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          result_id: window.currentResultId, question: questions[idx],
          answer, duration: speakingMs / 1000,
        }),
      });
      const json = await res.json();
      if (!res.ok) { showError(json.error || "Could not evaluate your answer."); submitBtn.disabled = false; micBtn.disabled = !SR; return; }
      results[idx] = { question: questions[idx], data: json.data };
      renderFeedback(json.data);
      answerEl.disabled = true;
      submitBtn.hidden = true;
      nextBtn.hidden = false;
      nextBtn.textContent = idx === questions.length - 1 ? "See summary" : "Next question";
    } catch (e) {
      showError("Could not reach the server. Please try again.");
      submitBtn.disabled = false; micBtn.disabled = !SR;
    } finally {
      submitBtn.textContent = label;
      submitting = false;
    }
  }

  function showSummary() {
    stage.hidden = true;
    summary.hidden = false;
    summary.textContent = "";
    const done = results.filter(Boolean);
    const avg = done.length ? (done.reduce((a, r) => a + r.data.overall_score, 0) / done.length).toFixed(1) : "0.0";
    summary.appendChild(el("p", "ai-target", `Interview complete. Average score: ${avg}/10`));
    done.forEach((r, i) => {
      const card = el("div", "ai-card");
      card.appendChild(el("p", "ai-label", `Question ${i + 1} - ${r.data.overall_score}/10`));
      card.appendChild(el("p", "ai-strong", r.question));
      if (r.data.improvements[0]) card.appendChild(el("p", null, "Focus on: " + r.data.improvements[0]));
      summary.appendChild(card);
    });
    const again = el("button", "btn-primary", "Practice again");
    again.type = "button";
    again.style.marginTop = "14px";
    again.addEventListener("click", open);
    summary.appendChild(again);
  }

  nextBtn.addEventListener("click", () => {
    if (idx >= questions.length - 1) { showSummary(); return; }
    idx += 1;
    showQuestion();
  });
  submitBtn.addEventListener("click", submitAnswer);
  launchBtn.addEventListener("click", open);
  closeBtn.addEventListener("click", () => { resetAll(); panel.hidden = true; });
  document.addEventListener("analysis:ready", () => { resetAll(); panel.hidden = true; });
  window.addEventListener("beforeunload", () => { try { recognition && recognition.abort(); } catch (e) {} });
})();

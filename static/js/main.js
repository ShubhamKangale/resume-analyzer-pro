// Shared front-end behaviour for AI Resume Analyzer

document.addEventListener("DOMContentLoaded", () => {
  // Auto-dismiss flash messages after a few seconds
  document.querySelectorAll(".flash").forEach((el) => {
    setTimeout(() => {
      el.style.transition = "opacity 0.4s ease";
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 400);
    }, 4000);
  });

  // Scroll-reveal animation for cards, steps, tables, forms
  const targets = document.querySelectorAll(
    ".steps h2, .step-list li, .feature, .latest-card, .stat, .data-table, .dash-head, .empty-state, .admin-grid > div, .analyze-form, .page-sub"
  );
  targets.forEach((el, i) => {
    el.classList.add("rv");
    el.style.setProperty("--d", `${(i % 3) * 0.1}s`);
  });
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
      });
    }, { threshold: 0.12 });
    targets.forEach((el) => io.observe(el));
  } else {
    targets.forEach((el) => el.classList.add("in"));
  }
});

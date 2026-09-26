/* WardrobeOS client enhancements - vanilla JS, no dependencies.
   Theme toggle, toasts, copy buttons, confirm dialogs, form shortcuts. */
(function () {
  "use strict";

  /* ---------- theme ---------- */
  var toggle = document.getElementById("theme-toggle");
  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    if (toggle) toggle.textContent = theme === "dark" ? "☀️" : "🌙";
  }
  try {
    var stored = localStorage.getItem("theme");
    if (stored) applyTheme(stored);
    else if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) applyTheme("dark");
  } catch (e) { /* storage unavailable - keep light */ }
  if (toggle) toggle.addEventListener("click", function () {
    var next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(next);
    try { localStorage.setItem("theme", next); } catch (e) {}
  });

  /* ---------- toasts (auto-dismiss) ---------- */
  document.querySelectorAll(".toast").forEach(function (el) {
    setTimeout(function () {
      el.classList.add("toast-hide");
      setTimeout(function () { el.remove(); }, 400);
    }, 4200);
  });

  /* ---------- copy buttons ---------- */
  function copyText(text, btn) {
    function done(ok) {
      if (!btn) return;
      var original = btn.textContent;
      btn.textContent = ok ? "✓ Copied" : "✕ Copy failed";
      setTimeout(function () { btn.textContent = original; }, 1600);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { done(true); }, function () { done(false); });
    } else {
      var ta = document.createElement("textarea");
      ta.value = text; document.body.appendChild(ta); ta.select();
      var ok = document.execCommand("copy");
      document.body.removeChild(ta); done(ok);
    }
  }
  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-copy]");
    if (btn) {
      var source = document.querySelector(btn.getAttribute("data-copy"));
      if (source) copyText(source.value !== undefined ? source.value : source.textContent, btn);
    }
  });

  /* ---------- confirm dialogs ---------- */
  document.addEventListener("submit", function (ev) {
    var form = ev.target;
    var message = form.getAttribute("data-confirm");
    if (message && !window.confirm(message)) ev.preventDefault();
  });

  /* ---------- keyboard shortcuts ---------- */
  var shortcutMap = {
    "1": "/", "2": "/wardrobe/", "3": "/outfits/", "4": "/planner/",
    "5": "/laundry/", "6": "/analytics/", "7": "/trips/",
    "8": "/lab/", "9": "/lab/library/"
  };
  document.addEventListener("keydown", function (ev) {
    if (ev.altKey && !ev.ctrlKey && !ev.metaKey && shortcutMap[ev.key]) {
      ev.preventDefault();
      window.location.href = shortcutMap[ev.key];
    }
    if ((ev.ctrlKey || ev.metaKey) && ev.key === "Enter") {
      var form = ev.target.closest("form");
      if (form) { ev.preventDefault(); form.submit(); }
    }
  });

  /* ---------- prompt type switch (studio) ---------- */
  var tabs = document.querySelectorAll("[data-tab-target]");
  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      var group = tab.getAttribute("data-tab-group");
      var target = tab.getAttribute("data-tab-target");
      document.querySelectorAll('[data-tab-group="' + group + '"]').forEach(function (el) {
        el.classList.toggle("active", el === tab);
      });
      document.querySelectorAll('[data-tab-panel="' + group + '"]').forEach(function (panel) {
        panel.hidden = panel.getAttribute("data-tab-panel") !== target &&
                       panel.getAttribute("data-tab-value") !== target;
      });
      document.querySelectorAll('[data-tab-pane="' + group + '"]').forEach(function (pane) {
        pane.hidden = pane.getAttribute("data-tab-pane") !== target;
      });
    });
  });
  /* ---------- wardrobe form: live image preview ---------- */
  var imageInput = document.getElementById("id_image");
  if (imageInput) {
    var preview = document.getElementById("image-preview");
    imageInput.addEventListener("change", function () {
      var file = imageInput.files && imageInput.files[0];
      if (!file || !preview) return;
      var reader = new FileReader();
      reader.onload = function (e) {
        preview.src = e.target.result;
        preview.hidden = false;
      };
      reader.readAsDataURL(file);
    });
  }
})();

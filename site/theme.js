/* Light/dark toggle. Loaded synchronously in <head> so the stored theme applies before first paint.
   Also opens the <details> matching the URL hash (used by the questions page). */
(function () {
  var KEY = "amicus-theme";
  var root = document.documentElement;
  try {
    var saved = localStorage.getItem(KEY);
    if (saved === "light" || saved === "dark") root.dataset.theme = saved;
  } catch (e) {}

  function effective() {
    if (root.dataset.theme === "light" || root.dataset.theme === "dark") return root.dataset.theme;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  function label(btn) {
    var dark = effective() === "dark";
    btn.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
  }
  function openHash() {
    var id = decodeURIComponent((location.hash || "").slice(1));
    if (!id) return;
    var el = document.getElementById(id);
    if (el && el.tagName === "DETAILS") {
      el.open = true;
      el.scrollIntoView();
    }
  }
  document.addEventListener("DOMContentLoaded", function () {
    var btn = document.getElementById("theme-toggle");
    if (btn) {
      label(btn);
      btn.addEventListener("click", function () {
        var next = effective() === "dark" ? "light" : "dark";
        root.dataset.theme = next;
        try { localStorage.setItem(KEY, next); } catch (e) {}
        label(btn);
      });
    }
    openHash();
  });
  window.addEventListener("hashchange", openHash);
})();

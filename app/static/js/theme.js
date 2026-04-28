(function () {
  function getTheme() {
    try { return localStorage.getItem('theme') || 'light'; } catch (e) { return 'light'; }
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-bs-theme', theme);
    var btn = document.getElementById('theme-toggle');
    if (btn) {
      btn.textContent = theme === 'dark' ? '☀️' : '🌙';
      btn.title = theme === 'dark' ? 'Hellmodus aktivieren' : 'Dunkelmodus aktivieren';
      btn.setAttribute('aria-label', btn.title);
    }
  }

  function toggle() {
    var next = getTheme() === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem('theme', next); } catch (e) {}
    applyTheme(next);
  }

  document.addEventListener('DOMContentLoaded', function () {
    applyTheme(getTheme());
    var btn = document.getElementById('theme-toggle');
    if (btn) { btn.addEventListener('click', toggle); }
  });
}());

// Notification-Center (Ticket wsco): Löschen einzelner Einträge und "alle löschen".
// Das Markieren-als-gelesen läuft serverseitig über den /go-Redirect (kein JS nötig).
document.addEventListener('DOMContentLoaded', function () {
  const menu = document.getElementById('notif-menu');
  if (!menu) return;

  const csrf = menu.dataset.csrf;
  const badge = document.getElementById('notif-badge');
  const deleteAllBtn = document.getElementById('notif-delete-all');

  function updateBadge(count) {
    if (!badge) return;
    badge.childNodes[0].nodeValue = count;
    badge.classList.toggle('d-none', !count || count <= 0);
  }

  function hasItemsLeft() {
    return menu.querySelectorAll('.notif-item').length > 0;
  }

  function showEmptyState() {
    if (deleteAllBtn) deleteAllBtn.classList.add('d-none');
    if (!document.getElementById('notif-empty')) {
      const li = document.createElement('li');
      li.id = 'notif-empty';
      li.innerHTML = '<span class="dropdown-item-text text-muted small">Keine Benachrichtigungen</span>';
      menu.querySelector('.dropdown-header').parentElement.after(li);
    }
  }

  function postJson(url) {
    return fetch(url, {
      method: 'POST',
      headers: { 'X-CSRFToken': csrf, 'Content-Type': 'application/json' },
    }).then(function (r) {
      if (!r.ok) throw new Error('request failed');
      return r.json();
    });
  }

  // Einzelnes Löschen (✕ je Eintrag)
  menu.querySelectorAll('.notif-delete').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      const item = btn.closest('.notif-item');
      postJson(btn.dataset.deleteUrl)
        .then(function (data) {
          if (item) item.remove();
          updateBadge(data.unread_count);
          if (!hasItemsLeft()) showEmptyState();
        })
        .catch(function () {});
    });
  });

  // Alle löschen
  if (deleteAllBtn) {
    deleteAllBtn.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      postJson(menu.dataset.deleteAllUrl)
        .then(function () {
          menu.querySelectorAll('.notif-item').forEach(function (el) { el.remove(); });
          updateBadge(0);
          showEmptyState();
        })
        .catch(function () {});
    });
  }
});

document.addEventListener('DOMContentLoaded', function() {
  // Create form: invite users select-all
  const createSelectAll = document.getElementById('invite-select-all');
  const createCheckboxes = document.querySelectorAll('.invite-checkbox');

  if (createSelectAll && createCheckboxes.length > 0) {
    createSelectAll.addEventListener('change', function() {
      createCheckboxes.forEach(checkbox => {
        checkbox.checked = this.checked;
      });
    });

    createCheckboxes.forEach(checkbox => {
      checkbox.addEventListener('change', function() {
        const allChecked = Array.from(createCheckboxes).every(cb => cb.checked);
        createSelectAll.checked = allChecked;
      });
    });
  }

  // Detail form: invite users select-all
  const detailSelectAll = document.getElementById('detail-invite-select-all');
  const detailCheckboxes = document.querySelectorAll('.detail-invite-checkbox');

  if (detailSelectAll && detailCheckboxes.length > 0) {
    detailSelectAll.addEventListener('change', function() {
      detailCheckboxes.forEach(checkbox => {
        checkbox.checked = this.checked;
      });
    });

    detailCheckboxes.forEach(checkbox => {
      checkbox.addEventListener('change', function() {
        const allChecked = Array.from(detailCheckboxes).every(cb => cb.checked);
        detailSelectAll.checked = allChecked;
      });
    });
  }
});

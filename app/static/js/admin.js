(function () {
  const modal = document.getElementById('pgc-modal');
  if (!modal) return;
  const msgEl = document.getElementById('pgc-modal-msg');
  const titleEl = document.getElementById('pgc-modal-title');
  const okBtn = document.getElementById('pgc-modal-ok');
  let pending = null;

  function openModal(message, title) {
    titleEl.textContent = title || 'Confirm delete';
    msgEl.textContent = message || 'Are you sure?';
    modal.hidden = false;
    document.body.style.overflow = 'hidden';
    okBtn.focus();
  }

  function closeModal() {
    modal.hidden = true;
    document.body.style.overflow = '';
    pending = null;
  }

  modal.querySelectorAll('[data-pgc-cancel]').forEach(el => {
    el.addEventListener('click', closeModal);
  });

  okBtn.addEventListener('click', function () {
    if (!pending) { closeModal(); return; }
    const p = pending;
    closeModal();
    if (p.type === 'form') {
      p.el.dataset.pgcConfirmed = '1';
      if (p.submitter) {
        // native submit with specific button
        if (typeof p.el.requestSubmit === 'function') {
          p.el.requestSubmit(p.submitter);
        } else {
          p.el.submit();
        }
      } else {
        p.el.requestSubmit ? p.el.requestSubmit() : p.el.submit();
      }
    } else if (p.type === 'button') {
      p.el.dataset.pgcConfirmed = '1';
      p.el.click();
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && !modal.hidden) closeModal();
  });

  // Only elements with data-confirm that are DELETE actions (not checkboxes/links)
  document.addEventListener('click', function (e) {
    // never intercept checkbox / radio / links without data-confirm
    if (e.target.closest('input, select, textarea, a')) return;

    const btn = e.target.closest('button[data-confirm], input[type="submit"][data-confirm]');
    if (!btn) return;
    if (btn.dataset.pgcConfirmed === '1') {
      btn.dataset.pgcConfirmed = '';
      return;
    }
    e.preventDefault();
    e.stopPropagation();
    pending = { type: 'button', el: btn };
    openModal(
      btn.getAttribute('data-confirm') || 'Delete this item?',
      btn.getAttribute('data-confirm-title') || 'Confirm delete'
    );
  }, true);

  document.addEventListener('submit', function (e) {
    const form = e.target;
    if (!form || !form.hasAttribute('data-confirm')) return;
    if (form.dataset.pgcConfirmed === '1') {
      form.dataset.pgcConfirmed = '';
      return;
    }
    // Only confirm when the submitter is a delete action
    const submitter = e.submitter;
    if (submitter && !submitter.hasAttribute('data-confirm') && !submitter.classList.contains('js-bulk-delete')) {
      // e.g. Confirm payment button inside same form — allow without modal
      return;
    }
    e.preventDefault();
    pending = { type: 'form', el: form, submitter: submitter };
    openModal(
      form.getAttribute('data-confirm') || 'Delete selected items?',
      form.getAttribute('data-confirm-title') || 'Confirm delete'
    );
  }, true);
})();


// Mobile: wrap tables for horizontal scroll
document.querySelectorAll('.main table').forEach(function (t) {
  if (t.parentElement && t.parentElement.classList.contains('table-wrap')) return;
  var w = document.createElement('div');
  w.className = 'table-wrap';
  t.parentNode.insertBefore(w, t);
  w.appendChild(t);
});

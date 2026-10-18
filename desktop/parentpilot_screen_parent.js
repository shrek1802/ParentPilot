/* ParentPilot parent dashboard: update only the screenshot panel, not the whole page. */
(() => {
  'use strict';
  const status = document.getElementById('screen-status');
  const preview = document.getElementById('screen-preview');
  const link = document.getElementById('screen-preview-link');
  const previewBox = document.getElementById('screen-preview-container');
  const saveForm = document.getElementById('save-screen-form');
  const dialog = document.getElementById('screen-modal');
  const modalImage = document.getElementById('screen-modal-image');
  const modalArea = document.getElementById('screen-modal-area');
  if (!status || !preview || !link || !previewBox || !saveForm || !dialog) return;
  let previous = status.textContent.trim();
  let zoom = 1;
  let stopped = false;
  const setZoom = amount => {
    zoom = Math.max(0.5, Math.min(5, amount));
    modalImage.style.width = (100 * zoom) + '%';
    modalImage.style.height = 'auto';
  };
  function showImage(url) {
    if (typeof dialog.showModal !== 'function') {
      window.open(url, '_blank', 'noopener');
      return;
    }
    modalImage.src = url;
    setZoom(1);
    dialog.showModal();
    modalArea.scrollTop = 0;
    modalArea.scrollLeft = 0;
  }
  document.querySelectorAll('a.open-screen-viewer').forEach(anchor => {
    anchor.addEventListener('click', event => {
      event.preventDefault();
      showImage(anchor.dataset.screenSrc || anchor.href);
    });
  });
  document.getElementById('screen-close').addEventListener('click', () => dialog.close());
  document.getElementById('screen-zoom-in').addEventListener('click', () => setZoom(zoom + 0.5));
  document.getElementById('screen-zoom-out').addEventListener('click', () => setZoom(zoom - 0.5));
  document.getElementById('screen-zoom-fit').addEventListener('click', () => setZoom(1));
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
  document.querySelectorAll('form[data-delete-screen]').forEach(form => {
    form.addEventListener('submit', event => {
      if (!window.confirm('Permanently delete this saved picture?')) event.preventDefault();
    });
  });
  const updatePreview = ready => {
    previewBox.hidden = !ready;
    saveForm.hidden = !ready;
    preview.hidden = !ready;
  };
  async function poll() {
    let delay = 6000;
    try {
      const response = await fetch('/api/parent-screen', {cache: 'no-store', credentials: 'same-origin'});
      if (response.status === 403) {
        status.textContent = 'Sign in again to view pictures.';
        updatePreview(false);
        stopped = true;
        return;
      }
      if (!response.ok) throw new Error('Screen status unavailable');
      const data = await response.json();
      const current = data.screen_status || 'unavailable';
      status.textContent = current;
      if (current !== previous) {
        previous = current;
        if (current === 'ready') {
          const src = '/screen.jpg?t=' + Date.now();
          preview.src = src;
          link.href = src;
          link.dataset.screenSrc = src;
        }
      }
      updatePreview(current === 'ready');
      delay = current === 'pending' ? 1200 : current === 'ready' ? 2700 : 6500;
    } catch (_) {
      status.textContent = 'Unable to check screen status; timer controls remain available.';
      delay = 7500;
    }
    if (!stopped) window.setTimeout(poll, delay);
  }
  window.setTimeout(poll, 900);
})();

(function () {
  'use strict';

  function getPendingButtonLabel(button) {
    if (!button || typeof button !== 'object') {
      return 'Working...';
    }
    const pendingLabel = button.dataset && typeof button.dataset.pendingLabel === 'string'
      ? button.dataset.pendingLabel.trim()
      : '';
    return pendingLabel || 'Working...';
  }

  function getDefaultButtonLabel(button) {
    if (!button || typeof button !== 'object') {
      return '';
    }
    const defaultLabel = button.dataset && typeof button.dataset.label === 'string'
      ? button.dataset.label.trim()
      : '';
    if (defaultLabel) {
      return defaultLabel;
    }
    return typeof button.textContent === 'string' ? button.textContent.trim() : '';
  }

  function setPendingState(button, statusEl) {
    if (button) {
      button.disabled = true;
      button.setAttribute('aria-busy', 'true');
      button.textContent = getPendingButtonLabel(button);
    }
    if (statusEl) {
      statusEl.className = 'ads-reports-status ads-reports-status--pending';
      statusEl.textContent = 'Working...';
    }
  }

  function clearPendingState(button, statusEl, errorMessage) {
    if (button) {
      button.disabled = false;
      button.removeAttribute('aria-busy');
      button.textContent = getDefaultButtonLabel(button);
    }
    if (statusEl) {
      statusEl.className = 'ads-reports-status ads-reports-status--info';
      statusEl.textContent = errorMessage || '';
    }
  }

  function initAdsReportsPage(options) {
    const rootId = options && options.rootId ? String(options.rootId) : 'adsReportsContent';
    const root = document.getElementById(rootId);
    if (!root) {
      return null;
    }

    async function submitActionForm(form) {
      const actionButton = form.querySelector('button[type="submit"]');
      const statusEl = root.querySelector('.ads-reports-status');
      const selectedInput = form.querySelector('input[name="selected_report_name"]');
      const selectedReportName = selectedInput ? String(selectedInput.value || '') : '';

      setPendingState(actionButton, statusEl);

      try {
        const response = await fetch(form.action, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            selected_report_name: selectedReportName,
          }),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || 'Request failed');
        }
        if (typeof data.content_html !== 'string') {
          throw new Error('Response content missing');
        }
        root.innerHTML = data.content_html;
      } catch (error) {
        clearPendingState(
          actionButton,
          statusEl,
          error && error.message ? error.message : 'Request failed',
        );
      }
    }

    root.addEventListener('submit', function (event) {
      const form = event.target.closest('#adsReportsActionForm');
      if (!form) {
        return;
      }
      event.preventDefault();
      submitActionForm(form);
    });

    root.addEventListener('click', function (event) {
      const row = event.target.closest('.ads-reports-report-row[data-report-url]');
      if (!row) {
        return;
      }
      const destination = row.dataset.reportUrl;
      if (destination) {
        window.location.assign(destination);
      }
    });

    root.addEventListener('keydown', function (event) {
      const row = event.target.closest('.ads-reports-report-row[data-report-url]');
      if (!row) {
        return;
      }
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        const destination = row.dataset.reportUrl;
        if (destination) {
          window.location.assign(destination);
        }
      }
    });

    return {
      rootId: rootId,
    };
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      clearPendingState,
      getDefaultButtonLabel,
      getPendingButtonLabel,
      initAdsReportsPage,
      setPendingState,
    };
  }

  if (typeof window !== 'undefined') {
    window.initAdsReportsPage = initAdsReportsPage;
  }
})();

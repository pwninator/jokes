(function () {
  'use strict';

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

      if (actionButton) {
        actionButton.disabled = true;
      }
      if (statusEl) {
        statusEl.textContent = 'Working...';
      }

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
        if (statusEl) {
          statusEl.textContent = error && error.message ? error.message : 'Request failed';
        }
        if (actionButton) {
          actionButton.disabled = false;
        }
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
      initAdsReportsPage,
    };
  }

  window.initAdsReportsPage = initAdsReportsPage;
})();

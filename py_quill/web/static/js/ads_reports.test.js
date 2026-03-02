const assert = require('node:assert/strict');
const test = require('node:test');

const {
  FakeDocument,
  FakeElement,
  append,
  createDeferred,
  createFetchResponse,
} = require('./test_utils.js');
const {
  clearPendingState,
  getDefaultButtonLabel,
  getPendingButtonLabel,
  initAdsReportsPage,
  setPendingState,
} = require('./ads_reports.js');

function createButton({ label, pendingLabel, textContent }) {
  const button = new FakeElement({ tagName: 'button' });
  button.dataset.label = label || '';
  button.dataset.pendingLabel = pendingLabel || '';
  button.textContent = textContent || '';
  button.setAttribute('type', 'submit');
  return button;
}

function createStatusEl() {
  return new FakeElement({ className: 'ads-reports-status' });
}

function createAdsReportsDom() {
  const body = new FakeElement({ tagName: 'body' });
  const document = new FakeDocument(body);
  const root = append(body, new FakeElement({ id: 'adsReportsContent' }));
  const form = append(root, new FakeElement({ id: 'adsReportsActionForm', tagName: 'form' }));
  const selectedInput = append(form, new FakeElement({ tagName: 'input' }));
  selectedInput.setAttribute('name', 'selected_report_name');
  selectedInput.value = 'report-1';
  const submitButton = append(form, createButton({
    label: 'Process Reports',
    pendingLabel: 'Processing...',
    textContent: 'Process Reports',
  }));
  const statusEl = append(root, createStatusEl());
  const reportRow = append(
    root,
    new FakeElement({ className: 'ads-reports-report-row', tagName: 'div' }),
  );
  reportRow.setAttribute('data-report-url', '/reports/daily');
  const reportRowText = append(reportRow, new FakeElement({ tagName: 'span' }));
  form.action = '/ads/reports/request';

  return {
    document,
    form,
    reportRow,
    reportRowText,
    root,
    selectedInput,
    statusEl,
    submitButton,
  };
}

async function flushAsyncWork() {
  await Promise.resolve();
  await Promise.resolve();
}

test('getPendingButtonLabel falls back to working text', () => {
  assert.equal(getPendingButtonLabel(null), 'Working...');
  assert.equal(getPendingButtonLabel(createButton({ pendingLabel: '' })), 'Working...');
  assert.equal(
    getPendingButtonLabel(createButton({ pendingLabel: 'Processing...' })),
    'Processing...',
  );
});

test('setPendingState updates button and status text', () => {
  const button = createButton({
    label: 'Process Reports',
    pendingLabel: 'Processing...',
    textContent: 'Process Reports',
  });
  const statusEl = createStatusEl();

  setPendingState(button, statusEl);

  assert.equal(button.disabled, true);
  assert.equal(button.textContent, 'Processing...');
  assert.equal(button.getAttribute('aria-busy'), 'true');
  assert.equal(statusEl.className, 'ads-reports-status ads-reports-status--pending');
  assert.equal(statusEl.textContent, 'Working...');
});

test('clearPendingState restores button label and shows error text', () => {
  const button = createButton({
    label: 'Request Reports',
    pendingLabel: 'Requesting...',
    textContent: 'Requesting...',
  });
  const statusEl = createStatusEl();

  setPendingState(button, statusEl);
  clearPendingState(button, statusEl, 'Request failed');

  assert.equal(button.disabled, false);
  assert.equal(button.textContent, 'Request Reports');
  assert.equal(button.getAttribute('aria-busy'), null);
  assert.equal(statusEl.className, 'ads-reports-status ads-reports-status--info');
  assert.equal(statusEl.textContent, 'Request failed');
  assert.equal(getDefaultButtonLabel(button), 'Request Reports');
});

test('initAdsReportsPage submits selected report and replaces content on success', async () => {
  const originalDocument = global.document;
  const originalFetch = global.fetch;
  const originalWindow = global.window;
  const { document, form, root, statusEl, submitButton } = createAdsReportsDom();
  const response = createDeferred();

  global.document = document;
  global.fetch = async (url, options) => {
    response.request = { options, url };
    return response.promise;
  };
  global.window = {
    location: {
      assign() {},
    },
  };

  try {
    initAdsReportsPage({ rootId: 'adsReportsContent' });

    await root.dispatch('submit', { target: form });
    assert.equal(submitButton.disabled, true);
    assert.equal(statusEl.textContent, 'Working...');

    response.resolve(createFetchResponse({
      json: {
        content_html: '<section class="replacement">Updated reports</section>',
      },
    }));
    await flushAsyncWork();

    assert.equal(response.request.url, '/ads/reports/request');
    assert.deepEqual(JSON.parse(response.request.options.body), {
      selected_report_name: 'report-1',
    });
    assert.equal(root.innerHTML, '<section class="replacement">Updated reports</section>');
  } finally {
    global.document = originalDocument;
    global.fetch = originalFetch;
    global.window = originalWindow;
  }
});

test('initAdsReportsPage restores button state and error text on failed submit', async () => {
  const originalDocument = global.document;
  const originalFetch = global.fetch;
  const originalWindow = global.window;
  const { document, form, root, statusEl, submitButton } = createAdsReportsDom();

  global.document = document;
  global.fetch = async () => {
    return createFetchResponse({
      ok: false,
      status: 500,
      json: {
        error: 'Request failed',
      },
    });
  };
  global.window = {
    location: {
      assign() {},
    },
  };

  try {
    initAdsReportsPage({ rootId: 'adsReportsContent' });

    await root.dispatch('submit', { target: form });
    await flushAsyncWork();

    assert.equal(submitButton.disabled, false);
    assert.equal(submitButton.textContent, 'Process Reports');
    assert.equal(statusEl.className, 'ads-reports-status ads-reports-status--info');
    assert.equal(statusEl.textContent, 'Request failed');
  } finally {
    global.document = originalDocument;
    global.fetch = originalFetch;
    global.window = originalWindow;
  }
});

test('initAdsReportsPage navigates to a report when a row is clicked', async () => {
  const originalDocument = global.document;
  const originalWindow = global.window;
  const { document, reportRowText, root } = createAdsReportsDom();
  const destinations = [];

  global.document = document;
  global.window = {
    location: {
      assign(url) {
        destinations.push(url);
      },
    },
  };

  try {
    initAdsReportsPage({ rootId: 'adsReportsContent' });
    await root.dispatch('click', { target: reportRowText });

    assert.deepEqual(destinations, ['/reports/daily']);
  } finally {
    global.document = originalDocument;
    global.window = originalWindow;
  }
});

test('initAdsReportsPage navigates to a report on keyboard activation', async () => {
  const originalDocument = global.document;
  const originalWindow = global.window;
  const { document, reportRowText, root } = createAdsReportsDom();
  const destinations = [];

  global.document = document;
  global.window = {
    location: {
      assign(url) {
        destinations.push(url);
      },
    },
  };

  try {
    initAdsReportsPage({ rootId: 'adsReportsContent' });
    const event = await root.dispatch('keydown', {
      key: 'Enter',
      target: reportRowText,
    });

    assert.equal(event.defaultPrevented, true);
    assert.deepEqual(destinations, ['/reports/daily']);
  } finally {
    global.document = originalDocument;
    global.window = originalWindow;
  }
});

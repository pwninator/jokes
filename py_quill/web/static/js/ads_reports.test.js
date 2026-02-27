const assert = require('node:assert/strict');
const test = require('node:test');

const {
  clearPendingState,
  getDefaultButtonLabel,
  getPendingButtonLabel,
  setPendingState,
} = require('./ads_reports.js');

function createButton({ label, pendingLabel, textContent }) {
  const attributes = new Map();
  return {
    dataset: {
      label: label || '',
      pendingLabel: pendingLabel || '',
    },
    textContent: textContent || '',
    disabled: false,
    setAttribute(name, value) {
      attributes.set(name, value);
    },
    removeAttribute(name) {
      attributes.delete(name);
    },
    getAttribute(name) {
      return attributes.get(name);
    },
  };
}

function createStatusEl() {
  return {
    className: '',
    textContent: '',
  };
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
  assert.equal(button.getAttribute('aria-busy'), undefined);
  assert.equal(statusEl.className, 'ads-reports-status ads-reports-status--info');
  assert.equal(statusEl.textContent, 'Request failed');
  assert.equal(getDefaultButtonLabel(button), 'Request Reports');
});

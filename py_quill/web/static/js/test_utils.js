'use strict';

class FakeClassList {
  constructor(initialTokens = []) {
    this._tokens = new Set(initialTokens.filter(Boolean));
  }

  add(...tokens) {
    tokens.forEach((token) => this._tokens.add(token));
  }

  remove(...tokens) {
    tokens.forEach((token) => this._tokens.delete(token));
  }

  toggle(token, force) {
    if (force === undefined) {
      if (this._tokens.has(token)) {
        this._tokens.delete(token);
        return false;
      }
      this._tokens.add(token);
      return true;
    }
    if (force) {
      this._tokens.add(token);
      return true;
    }
    this._tokens.delete(token);
    return false;
  }

  contains(token) {
    return this._tokens.has(token);
  }

  toString() {
    return Array.from(this._tokens).join(' ');
  }
}

class FakeStyle {
  constructor() {
    this._values = new Map();
  }

  setProperty(name, value) {
    this._values.set(name, String(value));
  }

  getPropertyValue(name) {
    return this._values.get(name) || '';
  }
}

function decodeHtmlEntities(value) {
  return String(value || '')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, '\'')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&');
}

class FakeElement {
  constructor({ id = '', className = '', tagName = 'div', parent = null } = {}) {
    this.id = id;
    this.tagName = String(tagName).toUpperCase();
    this.nodeType = 1;
    this.parentNode = parent;
    this.parentElement = parent;
    this.children = [];
    this.dataset = {};
    this.attributes = new Map();
    this.classList = new FakeClassList(className.split(/\s+/));
    this.listeners = new Map();
    this.style = new FakeStyle();
    this.value = '';
    this.textContent = '';
    this.disabled = false;
    this.hidden = false;
    this.src = '';
    this.alt = '';
    this.width = 0;
    this.height = 0;
    this.loading = '';
    this.type = '';
    this.focused = false;
    this.clientWidth = 0;
    this.scrollWidth = 0;
    this.scrollLeft = 0;
    this.offsetLeft = 0;
    this._innerHTML = '';
    this._rect = {
      left: 0,
      width: 0,
    };
    this._scrollIntoViewCalls = [];
  }

  get className() {
    return this.classList.toString();
  }

  set className(value) {
    this.classList = new FakeClassList(String(value).split(/\s+/));
    this.attributes.set('class', this.classList.toString());
  }

  get innerHTML() {
    return this._innerHTML;
  }

  set innerHTML(value) {
    this._innerHTML = String(value);
    this.children = [];
    if (this.tagName === 'TEXTAREA') {
      this.value = decodeHtmlEntities(this._innerHTML);
    }
  }

  appendChild(child) {
    child.parentNode = this;
    child.parentElement = this;
    this.children.push(child);
    return child;
  }

  insertBefore(child, referenceNode) {
    child.parentNode = this;
    child.parentElement = this;
    if (!referenceNode) {
      this.children.push(child);
      return child;
    }
    const index = this.children.indexOf(referenceNode);
    if (index < 0) {
      this.children.push(child);
      return child;
    }
    this.children.splice(index, 0, child);
    return child;
  }

  removeChild(child) {
    const index = this.children.indexOf(child);
    if (index >= 0) {
      this.children.splice(index, 1);
      child.parentNode = null;
      child.parentElement = null;
    }
    return child;
  }

  removeAttribute(name) {
    this.attributes.delete(name);
    if (name === 'src') {
      this.src = '';
    }
    if (name.startsWith('data-')) {
      const dataKey = name
        .slice(5)
        .replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
      delete this.dataset[dataKey];
    }
  }

  setAttribute(name, value) {
    const stringValue = String(value);
    this.attributes.set(name, stringValue);
    if (name === 'id') {
      this.id = stringValue;
      return;
    }
    if (name === 'class') {
      this.className = stringValue;
      return;
    }
    if (name === 'src') {
      this.src = stringValue;
      return;
    }
    if (name === 'alt') {
      this.alt = stringValue;
      return;
    }
    if (name === 'width') {
      this.width = Number(stringValue);
      return;
    }
    if (name === 'height') {
      this.height = Number(stringValue);
      return;
    }
    if (name.startsWith('data-')) {
      const dataKey = name
        .slice(5)
        .replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
      this.dataset[dataKey] = stringValue;
    }
  }

  getAttribute(name) {
    if (name === 'class') {
      return this.classList.toString();
    }
    if (name === 'src') {
      return this.src || null;
    }
    if (name === 'alt') {
      return this.alt || null;
    }
    return this.attributes.get(name) || null;
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) || [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  async dispatch(type, event = {}) {
    const listeners = this.listeners.get(type) || [];
    const actualEvent = {
      target: this,
      currentTarget: this,
      defaultPrevented: false,
      preventDefault() {
        this.defaultPrevented = true;
      },
      ...event,
    };
    for (const listener of listeners) {
      // eslint-disable-next-line no-await-in-loop
      await listener(actualEvent);
    }
    return actualEvent;
  }

  focus() {
    this.focused = true;
  }

  checkValidity() {
    return true;
  }

  reportValidity() {
    return true;
  }

  contains(node) {
    let current = node;
    while (current) {
      if (current === this) {
        return true;
      }
      current = current.parentNode || null;
    }
    return false;
  }

  closest(selector) {
    let current = this;
    while (current) {
      if (current.matches(selector)) {
        return current;
      }
      current = current.parentElement || null;
    }
    return null;
  }

  matches(selector) {
    const idOnlyMatch = selector.match(/^#([a-zA-Z0-9_-]+)$/);
    if (idOnlyMatch) {
      return this.id === idOnlyMatch[1];
    }

    const tagOnlyMatch = selector.match(/^[a-zA-Z]+$/);
    if (tagOnlyMatch) {
      return this.tagName === tagOnlyMatch[0].toUpperCase();
    }

    const classAttrMatch = selector.match(/^\.([a-zA-Z0-9_-]+)(\[.+\])?$/);
    if (classAttrMatch) {
      if (!this.classList.contains(classAttrMatch[1])) {
        return false;
      }
      return this._matchesAttributeSelector(classAttrMatch[2] || '');
    }

    const tagAttrMatch = selector.match(/^([a-zA-Z]+)(\[.+\])$/);
    if (tagAttrMatch) {
      if (this.tagName !== tagAttrMatch[1].toUpperCase()) {
        return false;
      }
      return this._matchesAttributeSelector(tagAttrMatch[2]);
    }

    if (selector.startsWith('[') && selector.endsWith(']')) {
      return this._matchesAttributeSelector(selector);
    }

    return false;
  }

  _matchesAttributeSelector(selector) {
    if (!selector) {
      return true;
    }

    const exactMatch = selector.match(/^\[([^=\]]+)="([^"]*)"\]$/);
    if (exactMatch) {
      const [, attrName, expected] = exactMatch;
      return (this.getAttribute(attrName) || '') === expected;
    }

    const suffixMatch = selector.match(/^\[([^=\]]+)\$="([^"]*)"\]$/);
    if (suffixMatch) {
      const [, attrName, expectedSuffix] = suffixMatch;
      return (this.getAttribute(attrName) || '').endsWith(expectedSuffix);
    }

    const presenceMatch = selector.match(/^\[([^=\]]+)\]$/);
    if (presenceMatch) {
      return this.getAttribute(presenceMatch[1]) !== null;
    }

    return false;
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }

  querySelectorAll(selector) {
    if (selector.includes(' ')) {
      const [ancestorSelector, descendantSelector] = selector.split(/\s+(.+)/);
      const results = [];
      this.querySelectorAll(ancestorSelector).forEach((ancestor) => {
        results.push(...ancestor.querySelectorAll(descendantSelector));
      });
      return results;
    }

    const results = [];
    this._collectDescendants((element) => element.matches(selector), results);
    return results;
  }

  _collectDescendants(predicate, results) {
    this.children.forEach((child) => {
      if (predicate(child)) {
        results.push(child);
      }
      child._collectDescendants(predicate, results);
    });
  }

  getBoundingClientRect() {
    return {
      left: this._rect.left,
      width: this._rect.width,
    };
  }

  setBoundingRect(rect) {
    this._rect = {
      ...this._rect,
      ...rect,
    };
  }

  scrollIntoView(options) {
    this._scrollIntoViewCalls.push(options);
  }
}

class FakeDocument {
  constructor(root = new FakeElement({ tagName: 'body' })) {
    this.body = root;
    this.readyState = 'complete';
    this.listeners = new Map();
  }

  getElementById(id) {
    return this._findElement((element) => element.id === id);
  }

  querySelector(selector) {
    return this.body.querySelector(selector);
  }

  querySelectorAll(selector) {
    return this.body.querySelectorAll(selector);
  }

  createElement(tagName) {
    return new FakeElement({ tagName });
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) || [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  async dispatch(type, event = {}) {
    const listeners = this.listeners.get(type) || [];
    const actualEvent = {
      defaultPrevented: false,
      preventDefault() {
        this.defaultPrevented = true;
      },
      ...event,
    };
    for (const listener of listeners) {
      // eslint-disable-next-line no-await-in-loop
      await listener(actualEvent);
    }
    return actualEvent;
  }

  _findElement(predicate) {
    const queue = [...this.body.children];
    while (queue.length) {
      const current = queue.shift();
      if (predicate(current)) {
        return current;
      }
      queue.push(...current.children);
    }
    return null;
  }
}

function createFetchResponse({ ok = true, status = 200, json = {} }) {
  return {
    ok,
    status,
    async json() {
      return json;
    },
  };
}

function createDeferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function createFetchMock(initialResponses = []) {
  const calls = [];
  const queue = initialResponses.slice();

  async function fetchMock(url, options = {}) {
    calls.push({ url: String(url), options });
    if (!queue.length) {
      throw new Error(`No mocked fetch response for ${url}`);
    }
    const next = queue.shift();
    if (next && typeof next.then === 'function') {
      return next;
    }
    if (typeof next === 'function') {
      return next(url, options, calls);
    }
    if (next && typeof next === 'object' && typeof next.json !== 'function') {
      return createFetchResponse(next);
    }
    return next;
  }

  fetchMock.calls = calls;
  fetchMock.enqueue = (response) => {
    queue.push(response);
  };
  return fetchMock;
}

function createDataTransfer() {
  const data = new Map();
  return {
    effectAllowed: '',
    dropEffect: '',
    setData(type, value) {
      data.set(type, value);
    },
    getData(type) {
      return data.get(type);
    },
  };
}

function createFixedDateClass(isoString) {
  const RealDate = Date;
  const fixedTime = new RealDate(isoString).getTime();
  return class FixedDate extends RealDate {
    constructor(...args) {
      if (args.length === 0) {
        super(fixedTime);
        return;
      }
      super(...args);
    }

    static now() {
      return fixedTime;
    }
  };
}

function createFakeClock() {
  let now = 0;
  let nextTimerId = 1;
  const timers = new Map();

  function setTimeoutFake(callback, delay = 0) {
    const timerId = nextTimerId;
    nextTimerId += 1;
    timers.set(timerId, {
      callback,
      dueAt: now + Math.max(0, Number(delay) || 0),
      timerId,
    });
    return timerId;
  }

  function clearTimeoutFake(timerId) {
    timers.delete(timerId);
  }

  function tick(durationMs) {
    const targetTime = now + Math.max(0, Number(durationMs) || 0);

    while (true) {
      let nextTimer = null;
      timers.forEach((timer) => {
        if (timer.dueAt > targetTime) {
          return;
        }
        if (
          !nextTimer
          || timer.dueAt < nextTimer.dueAt
          || (timer.dueAt === nextTimer.dueAt && timer.timerId < nextTimer.timerId)
        ) {
          nextTimer = timer;
        }
      });

      if (!nextTimer) {
        break;
      }

      timers.delete(nextTimer.timerId);
      now = nextTimer.dueAt;
      nextTimer.callback();
    }

    now = targetTime;
  }

  return {
    clearTimeout: clearTimeoutFake,
    pendingCount() {
      return timers.size;
    },
    setTimeout: setTimeoutFake,
    tick,
  };
}

function append(parent, child) {
  parent.appendChild(child);
  return child;
}

module.exports = {
  FakeClassList,
  FakeDocument,
  FakeElement,
  FakeStyle,
  append,
  createDataTransfer,
  createDeferred,
  createFakeClock,
  createFetchMock,
  createFetchResponse,
  createFixedDateClass,
};

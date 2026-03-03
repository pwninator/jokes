(function (factory) {
  const exports = factory();
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = exports;
  }
  if (typeof window !== 'undefined') {
    window.initAdminJokesCalendar = exports.initAdminJokesCalendar;
  }
}(function () {
  'use strict';

  const EDGE_LOAD_THRESHOLD_PX = 180;
  const EDGE_SCROLL_STEP_PX = 28;
  const EDGE_SCROLL_THRESHOLD_PX = 90;
  const WEEKDAY_HEADERS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

  function formatMonthId(year, month) {
    return `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}`;
  }

  function parseMonthId(monthId) {
    const parts = String(monthId || '').split('-');
    if (parts.length !== 2) {
      return null;
    }
    const year = parseInt(parts[0], 10);
    const month = parseInt(parts[1], 10);
    if (Number.isNaN(year) || Number.isNaN(month) || month < 1 || month > 12) {
      return null;
    }
    return { year, month };
  }

  function monthIdFromDate(date) {
    return formatMonthId(date.getFullYear(), date.getMonth() + 1);
  }

  function compareMonthIds(left, right) {
    if (left === right) {
      return 0;
    }
    return left < right ? -1 : 1;
  }

  function addMonths(monthId, delta) {
    const parsed = parseMonthId(monthId);
    if (!parsed) {
      return monthId;
    }
    const totalMonths = (parsed.year * 12) + (parsed.month - 1) + delta;
    const year = Math.floor(totalMonths / 12);
    const month = (totalMonths % 12) + 1;
    return formatMonthId(year, month);
  }

  function isMonthIdWithinBounds(bounds, monthId) {
    if (bounds.earliestMonthId && compareMonthIds(monthId, bounds.earliestMonthId) < 0) {
      return false;
    }
    if (bounds.latestMonthId && compareMonthIds(monthId, bounds.latestMonthId) > 0) {
      return false;
    }
    return true;
  }

  function normalizeMonth(month) {
    return {
      month_id: month.month_id,
      year: month.year,
      month: month.month,
      days_in_month: month.days_in_month,
      first_weekday: month.first_weekday,
      entries: { ...(month.entries || {}) },
      movable_day_keys: Array.isArray(month.movable_day_keys)
        ? month.movable_day_keys.slice()
        : [],
    };
  }

  function dayKey(dayNumber) {
    return String(dayNumber).padStart(2, '0');
  }

  function parseIsoDateParts(isoDate) {
    const match = String(isoDate || '').match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!match) {
      return null;
    }
    return {
      monthId: `${match[1]}-${match[2]}`,
      dayKey: match[3],
    };
  }

  function isMovableDay(month, key) {
    return Array.isArray(month && month.movable_day_keys)
      && month.movable_day_keys.indexOf(key) !== -1;
  }

  function sortedMonthIds(monthsById) {
    return Array.from(monthsById.keys()).sort(compareMonthIds);
  }

  function buildMonthFetchPlan(state, startMonthId, endMonthId) {
    if (!startMonthId || !endMonthId) {
      return [];
    }
    const monthsToFetch = [];
    let current = startMonthId;
    while (compareMonthIds(current, endMonthId) <= 0) {
      if (isMonthIdWithinBounds(state.bounds, current)
          && !state.monthsById.has(current)
          && !state.loadingMonthIds.has(current)) {
        monthsToFetch.push(current);
      }
      current = addMonths(current, 1);
    }
    return monthsToFetch;
  }

  function mergeMonthsById(monthsById, months) {
    const merged = new Map(monthsById);
    (months || []).forEach((month) => {
      merged.set(month.month_id, normalizeMonth(month));
    });
    return merged;
  }

  function findCenteredMonthId(monthCards, scrollLeft, clientWidth) {
    if (!monthCards.length) {
      return null;
    }
    const viewportCenter = scrollLeft + (clientWidth / 2);
    let bestId = null;
    let bestDistance = Number.POSITIVE_INFINITY;
    monthCards.forEach((card) => {
      const center = card.offsetLeft + (card.clientWidth / 2);
      const distance = Math.abs(center - viewportCenter);
      if (distance < bestDistance) {
        bestDistance = distance;
        bestId = card.getAttribute('data-month-id');
      }
    });
    return bestId;
  }

  function isValidDropTargetForMonth(month, key) {
    if (!month || !key || month.entries[key]) {
      return false;
    }
    return isMovableDay(month, key);
  }

  function applyOptimisticMoveToMonths(
    monthsById,
    sourceMonthId,
    sourceDayKey,
    targetMonthId,
    targetDayKey,
  ) {
    const sourceMonth = monthsById.get(sourceMonthId);
    const targetMonth = monthsById.get(targetMonthId);
    if (!sourceMonth || !targetMonth) {
      return null;
    }

    const sourceEntry = sourceMonth.entries[sourceDayKey];
    if (!sourceEntry) {
      return null;
    }

    const snapshot = {
      sourceSnapshot: {
        monthId: sourceMonthId,
        dayKey: sourceDayKey,
        entry: sourceEntry,
      },
      targetSnapshot: {
        monthId: targetMonthId,
        dayKey: targetDayKey,
        entry: targetMonth.entries[targetDayKey] || null,
      },
    };

    const nextMonthsById = new Map(monthsById);
    const nextSourceEntries = { ...sourceMonth.entries };
    const nextTargetEntries = sourceMonthId === targetMonthId
      ? nextSourceEntries
      : { ...targetMonth.entries };
    delete nextSourceEntries[sourceDayKey];
    nextTargetEntries[targetDayKey] = sourceEntry;

    nextMonthsById.set(sourceMonthId, {
      ...sourceMonth,
      entries: nextSourceEntries,
    });
    nextMonthsById.set(targetMonthId, {
      ...targetMonth,
      entries: nextTargetEntries,
    });

    return { monthsById: nextMonthsById, snapshot };
  }

  function revertOptimisticMoveInMonths(monthsById, snapshot) {
    if (!snapshot) {
      return monthsById;
    }
    const sourceMonth = monthsById.get(snapshot.sourceSnapshot.monthId);
    const targetMonth = monthsById.get(snapshot.targetSnapshot.monthId);
    if (!sourceMonth || !targetMonth) {
      return monthsById;
    }

    const nextMonthsById = new Map(monthsById);
    const nextSourceEntries = { ...sourceMonth.entries };
    const nextTargetEntries = snapshot.sourceSnapshot.monthId === snapshot.targetSnapshot.monthId
      ? nextSourceEntries
      : { ...targetMonth.entries };

    nextSourceEntries[snapshot.sourceSnapshot.dayKey] = snapshot.sourceSnapshot.entry;
    if (snapshot.targetSnapshot.entry) {
      nextTargetEntries[snapshot.targetSnapshot.dayKey] = snapshot.targetSnapshot.entry;
    } else {
      delete nextTargetEntries[snapshot.targetSnapshot.dayKey];
    }

    nextMonthsById.set(snapshot.sourceSnapshot.monthId, {
      ...sourceMonth,
      entries: nextSourceEntries,
    });
    nextMonthsById.set(snapshot.targetSnapshot.monthId, {
      ...targetMonth,
      entries: nextTargetEntries,
    });
    return nextMonthsById;
  }

  function syncDailyJokeEntryInMonths(monthsById, change) {
    const nextMonthsById = new Map(monthsById);

    function applyDateUpdate(isoDate, entry) {
      const parts = parseIsoDateParts(isoDate);
      if (!parts) {
        return;
      }
      const month = nextMonthsById.get(parts.monthId);
      if (!month) {
        return;
      }
      const nextEntries = { ...month.entries };
      if (entry) {
        nextEntries[parts.dayKey] = { ...entry };
      } else {
        delete nextEntries[parts.dayKey];
      }
      nextMonthsById.set(parts.monthId, {
        ...month,
        entries: nextEntries,
      });
    }

    applyDateUpdate(change && change.removeDate, null);
    if (change && change.addDate && change.entry) {
      applyDateUpdate(change.addDate, change.entry);
    }

    return nextMonthsById;
  }

  function escapeHtml(text) {
    return String(text || '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll('\'', '&#39;');
  }

  function monthLabel(month) {
    const date = new Date(month.year, month.month - 1, 1);
    return date.toLocaleDateString(undefined, {
      month: 'long',
      year: 'numeric',
    });
  }

  function renderDayHtml(month, dayNumber, todayIsoDate) {
    const key = dayKey(dayNumber);
    const isoDate = `${month.month_id}-${key}`;
    const entry = month.entries[key] || null;
    const isMovable = entry && isMovableDay(month, key);
    const dayClasses = ['admin-jokes-calendar-day'];
    if (isoDate === todayIsoDate) {
      dayClasses.push('admin-jokes-calendar-day--today');
    }
    if (entry) {
      dayClasses.push('admin-jokes-calendar-day--occupied');
    }
    if (entry && !isMovable) {
      dayClasses.push('admin-jokes-calendar-day--locked');
    }

    const imageHtml = entry && entry.thumbnail_url
      ? `<img class="admin-jokes-calendar-day-image" src="${escapeHtml(entry.thumbnail_url)}" alt="" loading="lazy">`
      : '<div class="admin-jokes-calendar-day-fill"></div>';
    const shadeHtml = entry ? '<div class="admin-jokes-calendar-day-shade"></div>' : '';

    return `
      <div class="${dayClasses.join(' ')}" data-month-id="${month.month_id}" data-day-key="${key}" data-date="${isoDate}">
        <div class="admin-jokes-calendar-day-button"
          ${entry ? `data-joke-id="${escapeHtml(entry.joke_id)}"` : ''}
          draggable="${isMovable ? 'true' : 'false'}">
          ${imageHtml}
          ${shadeHtml}
          <div class="admin-jokes-calendar-day-number">${dayNumber}</div>
        </div>
      </div>
    `;
  }

  function renderMonthHtml(month, todayIsoDate) {
    const totalCells = month.first_weekday + month.days_in_month;
    const rowCount = Math.ceil(totalCells / 7);
    const cellCount = rowCount * 7;
    const weekdayHtml = WEEKDAY_HEADERS.map((label) =>
      `<div class="admin-jokes-calendar-weekday">${label}</div>`).join('');
    const dayCells = [];
    for (let index = 0; index < cellCount; index += 1) {
      const dayNumber = index - month.first_weekday + 1;
      if (dayNumber < 1 || dayNumber > month.days_in_month) {
        dayCells.push('<div class="admin-jokes-calendar-day admin-jokes-calendar-day--out-of-month"></div>');
        continue;
      }
      dayCells.push(renderDayHtml(month, dayNumber, todayIsoDate));
    }

    return `
      <section class="admin-jokes-calendar-month" data-month-id="${month.month_id}">
        <div class="admin-jokes-calendar-month-header">
          <h4 class="admin-jokes-calendar-month-name">${escapeHtml(monthLabel(month))}</h4>
        </div>
        <div class="admin-jokes-calendar-weekdays">${weekdayHtml}</div>
        <div class="admin-jokes-calendar-grid">${dayCells.join('')}</div>
      </section>
    `;
  }

  function initAdminJokesCalendar(options) {
    if (window.__adminJokesCalendarInitialized) {
      return;
    }

    const config = options || {};
    if (!config.calendarDataUrl || !config.calendarMoveUrl) {
      throw new Error('calendarDataUrl and calendarMoveUrl are required');
    }
    const toggleButton = document.getElementById('admin-jokes-calendar-toggle-button');
    const panel = document.getElementById('admin-jokes-calendar-panel');
    const picker = document.getElementById('admin-jokes-calendar-month-picker');
    const errorBox = document.getElementById('admin-jokes-calendar-error');
    const loadingBox = document.getElementById('admin-jokes-calendar-loading');
    const scrollContainer = document.getElementById('admin-jokes-calendar-scroll');
    const monthsContainer = document.getElementById('admin-jokes-calendar-months');
    if (!toggleButton || !panel || !picker || !errorBox || !loadingBox
        || !scrollContainer || !monthsContainer) {
      return;
    }

    window.__adminJokesCalendarInitialized = true;

    const state = {
      isOpen: false,
      hasLoaded: false,
      loadingCount: 0,
      monthsById: new Map(),
      loadingMonthIds: new Set(),
      bounds: {
        earliestMonthId: null,
        latestMonthId: null,
        initialMonthId: null,
      },
      todayIsoDate: null,
      dragPayload: null,
    };

    function setError(message) {
      if (!message) {
        errorBox.hidden = true;
        errorBox.textContent = '';
        return;
      }
      errorBox.hidden = false;
      errorBox.textContent = message;
    }

    function incrementLoading() {
      state.loadingCount += 1;
      loadingBox.hidden = false;
    }

    function decrementLoading() {
      state.loadingCount = Math.max(0, state.loadingCount - 1);
      loadingBox.hidden = state.loadingCount === 0;
    }

    function render() {
      const monthIds = sortedMonthIds(state.monthsById);
      if (!monthIds.length) {
        monthsContainer.innerHTML = '';
        scrollContainer.hidden = true;
        return;
      }
      monthsContainer.innerHTML = monthIds.map((monthId) =>
        renderMonthHtml(state.monthsById.get(monthId), state.todayIsoDate)).join('');
      scrollContainer.hidden = false;
    }

    function updatePickerBounds() {
      if (state.bounds.earliestMonthId) {
        picker.min = state.bounds.earliestMonthId;
      }
      if (state.bounds.latestMonthId) {
        picker.max = state.bounds.latestMonthId;
      }
      if (!picker.value && state.bounds.initialMonthId) {
        picker.value = state.bounds.initialMonthId;
      }
    }

    function scrollToMonth(monthId) {
      if (!monthId) {
        return;
      }
      window.requestAnimationFrame(() => {
        const target = monthsContainer.querySelector(`[data-month-id="${monthId}"]`);
        if (!target) {
          return;
        }
        target.scrollIntoView({
          behavior: 'smooth',
          block: 'nearest',
          inline: 'center',
        });
      });
    }

    async function fetchRange(startMonthId, endMonthId, preferredScrollMonthId) {
      const monthsToFetch = buildMonthFetchPlan(state, startMonthId, endMonthId);
      if (!monthsToFetch.length) {
        if (preferredScrollMonthId) {
          scrollToMonth(preferredScrollMonthId);
        }
        return;
      }

      monthsToFetch.forEach((monthId) => state.loadingMonthIds.add(monthId));
      incrementLoading();
      setError('');

      const fetchStart = monthsToFetch[0];
      const fetchEnd = monthsToFetch[monthsToFetch.length - 1];
      const url = new URL(config.calendarDataUrl, window.location.origin);
      url.searchParams.set('start_month', fetchStart);
      url.searchParams.set('end_month', fetchEnd);

      try {
        const response = await fetch(url.toString(), {
          method: 'GET',
          headers: { Accept: 'application/json' },
          credentials: 'include',
        });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.error || 'Failed to load calendar data');
        }

        state.bounds.earliestMonthId = payload.earliest_month_id || state.bounds.earliestMonthId;
        state.bounds.latestMonthId = payload.latest_month_id || state.bounds.latestMonthId;
        state.bounds.initialMonthId = payload.initial_month_id || state.bounds.initialMonthId;
        state.todayIsoDate = payload.today_iso_date || state.todayIsoDate;
        state.monthsById = mergeMonthsById(state.monthsById, payload.months);
        updatePickerBounds();

        if (!(payload.months || []).length
            && payload.initial_month_id
            && !state.monthsById.has(payload.initial_month_id)) {
          await fetchRange(
            addMonths(payload.initial_month_id, -1),
            addMonths(payload.initial_month_id, 1),
            payload.initial_month_id,
          );
          return;
        }

        render();
        picker.value = preferredScrollMonthId || payload.initial_month_id || picker.value;
        scrollToMonth(preferredScrollMonthId || payload.initial_month_id);
      } catch (error) {
        setError(error instanceof Error ? error.message : 'Failed to load calendar data');
      } finally {
        monthsToFetch.forEach((monthId) => state.loadingMonthIds.delete(monthId));
        decrementLoading();
      }
    }

    async function openCalendar() {
      state.isOpen = true;
      toggleButton.setAttribute('aria-expanded', 'true');
      panel.hidden = false;
      if (!state.hasLoaded) {
        state.hasLoaded = true;
        const currentMonthId = monthIdFromDate(new Date());
        await fetchRange(addMonths(currentMonthId, -3), addMonths(currentMonthId, 3), null);
      }
    }

    function closeCalendar() {
      state.isOpen = false;
      toggleButton.setAttribute('aria-expanded', 'false');
      panel.hidden = true;
      setError('');
    }

    async function ensureMonthLoaded(monthId) {
      if (!monthId || state.monthsById.has(monthId) || !isMonthIdWithinBounds(state.bounds, monthId)) {
        return;
      }
      await fetchRange(monthId, monthId, null);
    }

    async function ensureMonthVisible(monthId) {
      if (!monthId || !isMonthIdWithinBounds(state.bounds, monthId)) {
        return;
      }
      await fetchRange(addMonths(monthId, -1), addMonths(monthId, 1), monthId);
    }

    function updatePickerToVisibleMonth() {
      const bestId = findCenteredMonthId(
        Array.from(monthsContainer.querySelectorAll('.admin-jokes-calendar-month')),
        scrollContainer.scrollLeft,
        scrollContainer.clientWidth,
      );
      if (bestId) {
        picker.value = bestId;
      }
    }

    async function maybeLoadMoreMonths() {
      const ids = sortedMonthIds(state.monthsById);
      if (!ids.length) {
        return;
      }

      if (scrollContainer.scrollLeft <= EDGE_LOAD_THRESHOLD_PX) {
        const previousMonthId = addMonths(ids[0], -1);
        if (isMonthIdWithinBounds(state.bounds, previousMonthId)) {
          await fetchRange(previousMonthId, previousMonthId, null);
        }
      }

      const remainingRight = scrollContainer.scrollWidth
        - scrollContainer.clientWidth
        - scrollContainer.scrollLeft;
      if (remainingRight <= EDGE_LOAD_THRESHOLD_PX) {
        const nextMonthId = addMonths(ids[ids.length - 1], 1);
        if (isMonthIdWithinBounds(state.bounds, nextMonthId)) {
          await fetchRange(nextMonthId, nextMonthId, null);
        }
      }
    }

    function clearDropIndicators() {
      monthsContainer
        .querySelectorAll('.admin-jokes-calendar-day--droppable')
        .forEach((node) => node.classList.remove('admin-jokes-calendar-day--droppable'));
    }

    function getMonthForCell(cell) {
      const monthId = cell.getAttribute('data-month-id');
      return monthId ? state.monthsById.get(monthId) : null;
    }

    function isValidDropTarget(cell) {
      if (!cell) {
        return false;
      }
      return isValidDropTargetForMonth(
        getMonthForCell(cell),
        cell.getAttribute('data-day-key'),
      );
    }

    async function persistMove(payload) {
      const response = await fetch(config.calendarMoveUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify(payload),
      });
      const json = await response.json();
      if (!response.ok) {
        throw new Error(json.error || 'Failed to move joke');
      }
    }

    window.syncAdminJokesCalendarJokeState = async (change) => {
      if (!state.isOpen || !state.hasLoaded || !change) {
        return;
      }

      const addDateParts = parseIsoDateParts(change.addDate);
      if (addDateParts) {
        await ensureMonthLoaded(addDateParts.monthId);
      }

      state.monthsById = syncDailyJokeEntryInMonths(state.monthsById, change);
      render();
    };

    toggleButton.addEventListener('click', async () => {
      if (state.isOpen) {
        closeCalendar();
        return;
      }
      await openCalendar();
    });

    picker.addEventListener('change', async () => {
      await ensureMonthVisible(picker.value);
    });

    scrollContainer.addEventListener('scroll', async () => {
      updatePickerToVisibleMonth();
      await maybeLoadMoreMonths();
    });

    scrollContainer.addEventListener('dragover', async (event) => {
      const rect = scrollContainer.getBoundingClientRect();
      const x = event.clientX - rect.left;
      if (x < EDGE_SCROLL_THRESHOLD_PX) {
        scrollContainer.scrollLeft -= EDGE_SCROLL_STEP_PX;
      } else if ((rect.width - x) < EDGE_SCROLL_THRESHOLD_PX) {
        scrollContainer.scrollLeft += EDGE_SCROLL_STEP_PX;
      }
      await maybeLoadMoreMonths();
    });

    monthsContainer.addEventListener('dragstart', (event) => {
      const tile = event.target.closest('.admin-jokes-calendar-day-button[draggable="true"]');
      if (!tile) {
        return;
      }
      const cell = tile.closest('.admin-jokes-calendar-day');
      if (!cell) {
        return;
      }
      state.dragPayload = {
        jokeId: tile.getAttribute('data-joke-id'),
        sourceDate: cell.getAttribute('data-date'),
        sourceMonthId: cell.getAttribute('data-month-id'),
        sourceDayKey: cell.getAttribute('data-day-key'),
      };
      cell.classList.add('admin-jokes-calendar-day--dragging');
      if (event.dataTransfer) {
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData('text/plain', state.dragPayload.jokeId || '');
      }
    });

    monthsContainer.addEventListener('dragend', (event) => {
      const cell = event.target.closest('.admin-jokes-calendar-day');
      if (cell) {
        cell.classList.remove('admin-jokes-calendar-day--dragging');
      }
      clearDropIndicators();
      state.dragPayload = null;
    });

    monthsContainer.addEventListener('dragenter', (event) => {
      const cell = event.target.closest('.admin-jokes-calendar-day');
      if (!cell || !state.dragPayload || !isValidDropTarget(cell)) {
        return;
      }
      cell.classList.add('admin-jokes-calendar-day--droppable');
    });

    monthsContainer.addEventListener('dragleave', (event) => {
      const cell = event.target.closest('.admin-jokes-calendar-day');
      if (!cell) {
        return;
      }
      if (event.relatedTarget && cell.contains(event.relatedTarget)) {
        return;
      }
      cell.classList.remove('admin-jokes-calendar-day--droppable');
    });

    monthsContainer.addEventListener('dragover', (event) => {
      const cell = event.target.closest('.admin-jokes-calendar-day');
      if (!cell || !state.dragPayload || !isValidDropTarget(cell)) {
        return;
      }
      event.preventDefault();
      if (event.dataTransfer) {
        event.dataTransfer.dropEffect = 'move';
      }
      cell.classList.add('admin-jokes-calendar-day--droppable');
    });

    monthsContainer.addEventListener('drop', async (event) => {
      const cell = event.target.closest('.admin-jokes-calendar-day');
      clearDropIndicators();
      if (!cell || !state.dragPayload || !isValidDropTarget(cell)) {
        return;
      }
      event.preventDefault();

      const targetDate = cell.getAttribute('data-date');
      const targetMonthId = cell.getAttribute('data-month-id');
      const targetDayKey = cell.getAttribute('data-day-key');
      if (!targetDate || !targetMonthId || !targetDayKey) {
        return;
      }

      const moveResult = applyOptimisticMoveToMonths(
        state.monthsById,
        state.dragPayload.sourceMonthId,
        state.dragPayload.sourceDayKey,
        targetMonthId,
        targetDayKey,
      );
      if (!moveResult) {
        return;
      }

      state.monthsById = moveResult.monthsById;
      render();

      try {
        setError('');
        await persistMove({
          joke_id: state.dragPayload.jokeId,
          source_date: state.dragPayload.sourceDate,
          target_date: targetDate,
        });
      } catch (error) {
        state.monthsById = revertOptimisticMoveInMonths(state.monthsById, moveResult.snapshot);
        render();
        setError(error instanceof Error ? error.message : 'Failed to move joke');
      } finally {
        state.dragPayload = null;
      }
    });
  }

  return {
    addMonths,
    applyOptimisticMoveToMonths,
    buildMonthFetchPlan,
    compareMonthIds,
    dayKey,
    findCenteredMonthId,
    formatMonthId,
    initAdminJokesCalendar,
    isMonthIdWithinBounds,
    isMovableDay,
    isValidDropTargetForMonth,
    mergeMonthsById,
    monthIdFromDate,
    normalizeMonth,
    parseMonthId,
    parseIsoDateParts,
    renderMonthHtml,
    revertOptimisticMoveInMonths,
    syncDailyJokeEntryInMonths,
  };
}));

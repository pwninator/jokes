(function () {
  'use strict';

  const WEEKDAY_HEADERS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];
  const EDGE_LOAD_THRESHOLD_PX = 180;
  const EDGE_SCROLL_THRESHOLD_PX = 90;
  const EDGE_SCROLL_STEP_PX = 28;

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

    function incrementLoading() {
      state.loadingCount += 1;
      loadingBox.hidden = false;
    }

    function decrementLoading() {
      state.loadingCount = Math.max(0, state.loadingCount - 1);
      loadingBox.hidden = state.loadingCount === 0;
    }

    function setError(message) {
      if (!message) {
        errorBox.hidden = true;
        errorBox.textContent = '';
        return;
      }
      errorBox.hidden = false;
      errorBox.textContent = message;
    }

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

    function isWithinBounds(monthId) {
      const earliest = state.bounds.earliestMonthId;
      const latest = state.bounds.latestMonthId;
      if (earliest && compareMonthIds(monthId, earliest) < 0) {
        return false;
      }
      if (latest && compareMonthIds(monthId, latest) > 0) {
        return false;
      }
      return true;
    }

    function sortedMonthIds() {
      return Array.from(state.monthsById.keys()).sort(compareMonthIds);
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

    function isMovableDay(month, key) {
      return Array.isArray(month.movable_day_keys)
        && month.movable_day_keys.indexOf(key) !== -1;
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

    function monthLabel(month) {
      const date = new Date(month.year, month.month - 1, 1);
      return date.toLocaleDateString(undefined, {
        month: 'long',
        year: 'numeric',
      });
    }

    function escapeHtml(text) {
      return String(text || '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    }

    function render() {
      const monthIds = sortedMonthIds();
      if (!monthIds.length) {
        monthsContainer.innerHTML = '';
        scrollContainer.hidden = true;
        return;
      }

      const html = monthIds.map((monthId) => renderMonth(state.monthsById.get(monthId))).join('');
      monthsContainer.innerHTML = html;
      scrollContainer.hidden = false;
    }

    function renderMonth(month) {
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
        dayCells.push(renderDay(month, dayNumber));
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

    function renderDay(month, dayNumber) {
      const key = dayKey(dayNumber);
      const isoDate = `${month.month_id}-${key}`;
      const entry = month.entries[key] || null;
      const isMovable = entry && isMovableDay(month, key);
      const dayClasses = ['admin-jokes-calendar-day'];
      if (isoDate === state.todayIsoDate) {
        dayClasses.push('admin-jokes-calendar-day--today');
      }
      if (entry) {
        dayClasses.push('admin-jokes-calendar-day--occupied');
      }
      if (entry && !isMovable) {
        dayClasses.push('admin-jokes-calendar-day--locked');
      }

      const contentClasses = ['admin-jokes-calendar-day-button'];
      const imageHtml = entry && entry.thumbnail_url
        ? `<img class="admin-jokes-calendar-day-image" src="${escapeHtml(entry.thumbnail_url)}" alt="" loading="lazy">`
        : `<div class="admin-jokes-calendar-day-fill"></div>`;
      const shadeHtml = entry ? '<div class="admin-jokes-calendar-day-shade"></div>' : '';

      return `
        <div class="${dayClasses.join(' ')}" data-month-id="${month.month_id}" data-day-key="${key}" data-date="${isoDate}">
          <div class="${contentClasses.join(' ')}"
            ${entry ? `data-joke-id="${escapeHtml(entry.joke_id)}"` : ''}
            draggable="${isMovable ? 'true' : 'false'}">
            ${imageHtml}
            ${shadeHtml}
            <div class="admin-jokes-calendar-day-number">${dayNumber}</div>
          </div>
        </div>
      `;
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
      if (!startMonthId || !endMonthId) {
        return;
      }

      const monthsToFetch = [];
      let current = startMonthId;
      while (compareMonthIds(current, endMonthId) <= 0) {
        if (isWithinBounds(current)
            && !state.monthsById.has(current)
            && !state.loadingMonthIds.has(current)) {
          monthsToFetch.push(current);
          state.loadingMonthIds.add(current);
        }
        current = addMonths(current, 1);
      }
      if (!monthsToFetch.length) {
        if (preferredScrollMonthId) {
          scrollToMonth(preferredScrollMonthId);
        }
        return;
      }

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
        updatePickerBounds();

        (payload.months || []).forEach((month) => {
          state.monthsById.set(month.month_id, normalizeMonth(month));
        });

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

    async function ensureMonthVisible(monthId) {
      if (!monthId || !isWithinBounds(monthId)) {
        return;
      }
      await fetchRange(addMonths(monthId, -1), addMonths(monthId, 1), monthId);
    }

    function updatePickerToVisibleMonth() {
      const monthCards = Array.from(monthsContainer.querySelectorAll('.admin-jokes-calendar-month'));
      if (!monthCards.length) {
        return;
      }
      const viewportCenter = scrollContainer.scrollLeft + (scrollContainer.clientWidth / 2);
      let bestId = null;
      let bestDistance = Number.POSITIVE_INFINITY;
      monthCards.forEach((card) => {
        const left = card.offsetLeft;
        const center = left + (card.clientWidth / 2);
        const distance = Math.abs(center - viewportCenter);
        if (distance < bestDistance) {
          bestDistance = distance;
          bestId = card.getAttribute('data-month-id');
        }
      });
      if (bestId) {
        picker.value = bestId;
      }
    }

    async function maybeLoadMoreMonths() {
      const ids = sortedMonthIds();
      if (!ids.length) {
        return;
      }

      if (scrollContainer.scrollLeft <= EDGE_LOAD_THRESHOLD_PX) {
        const previousMonthId = addMonths(ids[0], -1);
        if (isWithinBounds(previousMonthId)) {
          await fetchRange(previousMonthId, previousMonthId, null);
        }
      }

      const remainingRight = scrollContainer.scrollWidth
        - scrollContainer.clientWidth
        - scrollContainer.scrollLeft;
      if (remainingRight <= EDGE_LOAD_THRESHOLD_PX) {
        const nextMonthId = addMonths(ids[ids.length - 1], 1);
        if (isWithinBounds(nextMonthId)) {
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
      const month = getMonthForCell(cell);
      if (!month) {
        return false;
      }
      const key = cell.getAttribute('data-day-key');
      if (!key || month.entries[key]) {
        return false;
      }
      return isMovableDay(month, key);
    }

    function applyOptimisticMove(sourceMonthId, sourceDayKey, targetMonthId, targetDayKey) {
      const sourceMonth = state.monthsById.get(sourceMonthId);
      const targetMonth = state.monthsById.get(targetMonthId);
      if (!sourceMonth || !targetMonth) {
        return null;
      }

      const sourceEntry = sourceMonth.entries[sourceDayKey];
      if (!sourceEntry) {
        return null;
      }

      const sourceSnapshot = {
        monthId: sourceMonthId,
        dayKey: sourceDayKey,
        entry: sourceEntry,
      };
      const targetSnapshot = {
        monthId: targetMonthId,
        dayKey: targetDayKey,
        entry: targetMonth.entries[targetDayKey] || null,
      };

      const nextSourceEntries = { ...sourceMonth.entries };
      const nextTargetEntries = sourceMonthId === targetMonthId
        ? nextSourceEntries
        : { ...targetMonth.entries };

      delete nextSourceEntries[sourceDayKey];
      nextTargetEntries[targetDayKey] = sourceEntry;

      state.monthsById.set(sourceMonthId, {
        ...sourceMonth,
        entries: nextSourceEntries,
      });
      state.monthsById.set(targetMonthId, {
        ...targetMonth,
        entries: nextTargetEntries,
      });

      render();
      return { sourceSnapshot, targetSnapshot };
    }

    function revertOptimisticMove(snapshot) {
      if (!snapshot) {
        return;
      }
      const sourceMonth = state.monthsById.get(snapshot.sourceSnapshot.monthId);
      const targetMonth = state.monthsById.get(snapshot.targetSnapshot.monthId);
      if (!sourceMonth || !targetMonth) {
        return;
      }

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

      state.monthsById.set(snapshot.sourceSnapshot.monthId, {
        ...sourceMonth,
        entries: nextSourceEntries,
      });
      state.monthsById.set(snapshot.targetSnapshot.monthId, {
        ...targetMonth,
        entries: nextTargetEntries,
      });
      render();
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

      const snapshot = applyOptimisticMove(
        state.dragPayload.sourceMonthId,
        state.dragPayload.sourceDayKey,
        targetMonthId,
        targetDayKey,
      );
      if (!snapshot) {
        return;
      }

      try {
        setError('');
        await persistMove({
          joke_id: state.dragPayload.jokeId,
          source_date: state.dragPayload.sourceDate,
          target_date: targetDate,
        });
      } catch (error) {
        revertOptimisticMove(snapshot);
        setError(error instanceof Error ? error.message : 'Failed to move joke');
      } finally {
        state.dragPayload = null;
      }
    });
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      initAdminJokesCalendar,
    };
  }

  if (typeof window !== 'undefined') {
    window.initAdminJokesCalendar = initAdminJokesCalendar;
  }
})();

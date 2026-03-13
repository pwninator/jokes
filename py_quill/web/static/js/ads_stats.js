(function () {
  'use strict';

  const DAYS_OF_WEEK_MODE = 'Days of Week';
  const TIMELINE_MODE = 'Timeline';
  const DAYS_OF_WEEK_LABELS = Object.freeze([
    'Sun',
    'Mon',
    'Tue',
    'Wed',
    'Thu',
    'Fri',
    'Sat',
  ]);
  const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
  const ADS_STATS_PAGE_DATA_ELEMENT_ID = 'adsStatsPageData';
  const RESERVED_RIGHT_GUTTER_PX = 56;
  const COLOR_ADS = '#ef6c00';
  const COLOR_MATCHED = '#1565c0';
  const COLOR_UNMATCHED = '#c62828';
  const COLOR_RECONCILED = '#2e7d32';
  const COLOR_FREE_DOWNLOADS = '#000000';
  const CAMPAIGN_STATUS_STORAGE_KEY = 'adsStatsCampaignStatuses';
  const INLINE_KENP_PROFIT_TOOLTIP_OPTIONS = Object.freeze({ inlineKenpPages: true });
  const SEARCH_TERM_DIMENSION_COLUMNS = Object.freeze([
    { key: 'campaign_name', label: 'Campaign' },
    { key: 'search_term', label: 'Search Term' },
    { key: 'targeting', label: 'Targeting' },
    { key: 'keyword', label: 'Keyword' },
    { key: 'keyword_type', label: 'Keyword Type' },
    { key: 'match_type', label: 'Match Type' },
  ]);
  const SEARCH_TERM_DIMENSION_DEFAULTS = Object.freeze(['search_term']);
  const SEARCH_TERM_METRIC_COLUMNS = Object.freeze([
    { key: 'impressions', label: 'Impr', format: 'number' },
    { key: 'clicks', label: 'Clicks', format: 'number' },
    { key: 'ctr', label: 'CTR', format: 'percent' },
    { key: 'cpc', label: 'CPC', format: 'currency' },
    { key: 'cost_usd', label: 'Cost', format: 'currency' },
    { key: 'sales14d_usd', label: 'Sales', format: 'currency' },
    { key: 'purchases14d', label: 'Orders', format: 'number' },
    { key: 'cvr', label: 'CVR', format: 'percent' },
    { key: 'acos', label: 'ACOS', format: 'percent' },
    { key: 'roas', label: 'ROAS', format: 'ratio' },
  ]);
  const AMAZON_DP_URL_PREFIX = 'https://www.amazon.com/dp/';
  const ALPHANUMERIC_SINGLE_WORD_RE = /^[A-Za-z0-9]+$/;
  const PLACEMENT_DIMENSION_COLUMNS = Object.freeze([
    { key: 'placement_classification', label: 'Placement' },
    { key: 'campaign_name', label: 'Campaign' },
  ]);
  const PLACEMENT_DIMENSION_DEFAULTS = Object.freeze(['placement_classification']);
  const PLACEMENT_METRIC_COLUMNS = Object.freeze([
    { key: 'impressions', label: 'Impr', format: 'number' },
    { key: 'clicks', label: 'Clicks', format: 'number' },
    { key: 'ctr', label: 'CTR', format: 'percent' },
    { key: 'cpc', label: 'CPC', format: 'currency' },
    { key: 'cost_usd', label: 'Cost', format: 'currency' },
    { key: 'sales14d_usd', label: 'Sales', format: 'currency' },
    { key: 'purchases14d', label: 'Orders', format: 'number' },
    { key: 'cvr', label: 'CVR', format: 'percent' },
    { key: 'acos', label: 'ACOS', format: 'percent' },
    { key: 'roas', label: 'ROAS', format: 'ratio' },
  ]);

  function getChartTypeForMode(mode) {
    return mode === DAYS_OF_WEEK_MODE ? 'bar' : 'line';
  }

  function isIsoDateString(value) {
    return ISO_DATE_RE.test(String(value || ''));
  }

  function normalizeAdsEvent(rawEvent) {
    if (!rawEvent || typeof rawEvent !== 'object') {
      return null;
    }

    const dateValue = String(rawEvent.date || '').trim();
    const titleValue = String(rawEvent.title || '').trim();
    const keyValue = String(rawEvent.key || '').trim();
    if (!isIsoDateString(dateValue) || !titleValue) {
      return null;
    }

    return {
      key: keyValue || null,
      date: dateValue,
      title: titleValue,
    };
  }

  function groupAdsEventsByDate(adsEvents) {
    const groupedByDate = {};
    (adsEvents || []).forEach((rawEvent) => {
      const event = normalizeAdsEvent(rawEvent);
      if (!event) {
        return;
      }
      if (!groupedByDate[event.date]) {
        groupedByDate[event.date] = [];
      }
      groupedByDate[event.date].push(event.title);
    });

    return Object.keys(groupedByDate).sort().map((dateValue) => {
      return {
        date: dateValue,
        titles: groupedByDate[dateValue],
      };
    });
  }

  function getAdsEventLinesForLabel(label, adsEventGroups) {
    if (!isIsoDateString(label)) {
      return [];
    }
    const eventGroup = arrayOrEmpty(adsEventGroups).find((group) => group && group.date === label);
    if (!eventGroup) {
      return [];
    }
    return arrayOrEmpty(eventGroup.titles)
      .map((title) => String(title || '').trim())
      .filter(Boolean)
      .map((title) => `EVENT: ${title}`);
  }

  function chartDataToCsv(chart) {
    if (!chart || !chart.data) {
      return '';
    }
    const labels = chart.data.labels || [];
    const datasets = chart.data.datasets || [];
    if (labels.length === 0 && datasets.length === 0) {
      return '';
    }
    const escapeCsv = (val) => {
      const s = String(val);
      return s.includes(',') || s.includes('"') || s.includes('\n')
        ? `"${s.replace(/"/g, '""')}"`
        : s;
    };
    const headerCols = ['Date', ...datasets.map((d) => d.label || '')];
    const rows = [headerCols.map(escapeCsv).join(',')];
    for (let i = 0; i < labels.length; i += 1) {
      const row = [
        escapeCsv(labels[i]),
        ...datasets.map((d) => escapeCsv(d.data[i] != null ? d.data[i] : '')),
      ];
      rows.push(row.join(','));
    }
    return rows.join('\n');
  }

  function escapeCsvValue(value) {
    const stringValue = String(value == null ? '' : value);
    return stringValue.includes(',') || stringValue.includes('"') || stringValue.includes('\n')
      ? `"${stringValue.replace(/"/g, '""')}"`
      : stringValue;
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function isAmazonAsinGuessTerm(value) {
    const normalized = String(value || '').trim();
    return Boolean(normalized) && ALPHANUMERIC_SINGLE_WORD_RE.test(normalized);
  }

  function buildAmazonDpUrl(value) {
    return `${AMAZON_DP_URL_PREFIX}${encodeURIComponent(String(value || '').trim())}`;
  }

  function toNumber(value) {
    const parsedValue = Number(value);
    return Number.isFinite(parsedValue) ? parsedValue : 0;
  }

  function formatCountValue(value) {
    return Math.round(toNumber(value)).toLocaleString('en-US');
  }

  function formatAmountValue(value) {
    return `$${toNumber(value).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  }

  function formatAsinCountryLabel(detail, formatSuffix) {
    if (!detail || typeof detail !== 'object') {
      return null;
    }
    const countryCode = String(detail.country_code || '??').trim() || '??';
    const asin = String(detail.asin || '').trim();
    const bookKey = String(detail.book_key || 'unknown').trim() || 'unknown';
    const bookFormat = String(detail.book_format || 'Unknown').trim() || 'Unknown';
    if (!asin) {
      return null;
    }
    const normalizedSuffix = String(formatSuffix || '').trim();
    const formatLabel = normalizedSuffix ? `${bookFormat} ${normalizedSuffix}` : bookFormat;
    return `${countryCode} ${asin} - ${bookKey} (${formatLabel})`;
  }

  function formatCountDetailLines(detail) {
    const label = formatAsinCountryLabel(
      detail,
      detail && detail.is_kenp ? 'KENP Pages' : '',
    );
    if (!label) {
      return [];
    }
    const count = toNumber(detail.count);
    if (count <= 0) {
      return [];
    }
    return [`${label}: ${formatCountValue(count)}`];
  }

  function formatAmountDetailLines(detail, options) {
    const resolvedOptions = options || {};
    const inlineKenpPages = Boolean(resolvedOptions.inlineKenpPages);
    const baseLabel = formatAsinCountryLabel(
      detail,
      detail && detail.is_kenp ? 'KENP' : '',
    );
    if (!baseLabel) {
      return [];
    }
    const lines = [];
    const amount = toNumber(detail.amount_usd);
    if (Math.abs(amount) >= 1e-9) {
      lines.push(`${baseLabel}: ${formatAmountValue(amount)}`);
    }
    if (detail && detail.is_kenp) {
      const pages = toNumber(detail.kenp_pages_count);
      if (inlineKenpPages) {
        if (Math.abs(amount) >= 1e-9 || pages > 0) {
          const compactAmount = `${formatAmountValue(amount)}${
            pages > 0 ? ` (${formatCountValue(pages)})` : ''
          }`;
          lines.length = 0;
          lines.push(`${baseLabel}: ${compactAmount}`);
        }
      } else {
        const pagesLabel = formatAsinCountryLabel(detail, 'KENP Pages');
        if (pagesLabel && pages > 0) {
          lines.push(`${pagesLabel}: ${formatCountValue(pages)}`);
        }
      }
    }
    return lines;
  }

  function formatUnmatchedAdsTooltipLine(detail) {
    const lines = formatCountDetailLines(detail);
    return lines.length > 0 ? lines[0] : '';
  }

  function buildCountTooltipLines(details) {
    if (!Array.isArray(details)) {
      return [];
    }
    return details.flatMap((detail) => formatCountDetailLines(detail));
  }

  function buildProfitAmountTooltipLines(details, options) {
    if (!Array.isArray(details)) {
      return [];
    }
    return details.flatMap((detail) => formatAmountDetailLines(detail, options));
  }

  function buildSectionedProfitTooltipLines(adsDetails, organicDetails) {
    const adsLines = buildProfitAmountTooltipLines(adsDetails, INLINE_KENP_PROFIT_TOOLTIP_OPTIONS);
    const organicLines = buildProfitAmountTooltipLines(
      organicDetails, INLINE_KENP_PROFIT_TOOLTIP_OPTIONS,
    );
    if (adsLines.length === 0 || organicLines.length === 0) {
      return [...adsLines, ...organicLines];
    }
    return ['Ads:', ...adsLines, 'Organic:', ...organicLines];
  }

  function buildSectionedCountTooltipLines(adsDetails, organicDetails) {
    const adsLines = buildCountTooltipLines(adsDetails);
    const organicLines = buildCountTooltipLines(organicDetails);
    if (adsLines.length === 0 || organicLines.length === 0) {
      return [...adsLines, ...organicLines];
    }
    return ['Ads:', ...adsLines, 'Organic:', ...organicLines];
  }

  function arrayOrEmpty(value) {
    return Array.isArray(value) ? value : [];
  }

  function getArrayField(obj, key) {
    return arrayOrEmpty(obj && obj[key]);
  }

  function isKenpDetail(detail) {
    return Boolean(detail && detail.is_kenp);
  }

  function filterKenpDetails(details) {
    if (!Array.isArray(details)) {
      return [];
    }
    return details.filter((detail) => isKenpDetail(detail));
  }

  function filterBookSalesDetails(details) {
    if (!Array.isArray(details)) {
      return [];
    }
    return details.filter((detail) => !isKenpDetail(detail));
  }

  function sumCountDetails(details) {
    if (!Array.isArray(details)) {
      return 0;
    }
    return details.reduce((total, detail) => {
      return total + toNumber(detail && detail.count);
    }, 0);
  }

  function sumAmountDetails(details) {
    if (!Array.isArray(details)) {
      return 0;
    }
    return details.reduce((total, detail) => {
      return total + toNumber(detail && detail.amount_usd);
    }, 0);
  }

  function dayOfWeekIndexForDate(dateKey) {
    const dateParts = String(dateKey || '').split('-').map((part) => Number(part));
    const year = dateParts[0];
    const month = dateParts[1];
    const day = dateParts[2];
    return new Date(Date.UTC(year, month - 1, day)).getUTCDay();
  }

  function average(sum, count) {
    return count > 0 ? sum / count : 0;
  }

  function reserveScaleWidth(scale, width) {
    const reservedWidth = Number(width);
    if (!scale || !Number.isFinite(reservedWidth) || reservedWidth <= 0) {
      return;
    }
    scale.width = Math.max(scale.width || 0, reservedWidth);
  }

  function calculatePoas(grossProfitBeforeAds, cost) {
    const dayCost = toNumber(cost);
    return dayCost > 0 ? toNumber(grossProfitBeforeAds) / dayCost : 0;
  }

  function calculateTpoas(grossProfitBeforeAds, organicProfit, cost) {
    const dayCost = toNumber(cost);
    return dayCost > 0
      ? (toNumber(grossProfitBeforeAds) + toNumber(organicProfit)) / dayCost
      : 0;
  }

  function normalizeCampaignStatus(value) {
    const raw = String(value || '').trim();
    if (!raw) {
      return 'Unknown';
    }
    if (raw.toUpperCase() === 'ALL') {
      return 'All';
    }
    return raw.toUpperCase();
  }

  function normalizeCampaignStatusSelection(value) {
    if (Array.isArray(value)) {
      return Array.from(new Set(value
        .map((item) => normalizeCampaignStatus(item))
        .filter((item) => item && item !== 'All')));
    }
    const normalized = normalizeCampaignStatus(value || 'All');
    return normalized === 'All' ? null : [normalized];
  }

  function areSameStringSets(leftValues, rightValues) {
    const leftSet = new Set(leftValues || []);
    const rightSet = new Set(rightValues || []);
    if (leftSet.size !== rightSet.size) {
      return false;
    }
    return Array.from(leftSet).every((value) => rightSet.has(value));
  }

  function getEffectiveCampaignStatusFilter(campaignStatuses, availableCampaignStatuses) {
    const normalizedSelection = normalizeCampaignStatusSelection(campaignStatuses);
    if (normalizedSelection === null) {
      return null;
    }
    const normalizedAvailable = normalizeCampaignStatusSelection(availableCampaignStatuses) || [];
    if (normalizedAvailable.length > 0
      && areSameStringSets(normalizedSelection, normalizedAvailable)) {
      return null;
    }
    return normalizedSelection;
  }

  function matchesCampaignStatusFilter(campaign, campaignStatuses, availableCampaignStatuses) {
    const activeStatuses = getEffectiveCampaignStatusFilter(
      campaignStatuses,
      availableCampaignStatuses,
    );
    if (activeStatuses === null) {
      return true;
    }
    return activeStatuses.includes(normalizeCampaignStatus(campaign && campaign.campaign_status));
  }

  function getDailyStatsForCampaign(
    adsStatsData, campaignName, campaignStatuses, availableCampaignStatuses,
  ) {
    const data = adsStatsData || {};
    const labels = Array.isArray(data.labels) ? data.labels : [];
    const activeStatusFilter = getEffectiveCampaignStatusFilter(
      campaignStatuses,
      availableCampaignStatuses,
    );
    return labels.map((dateKey, index) => {
      let dayImpressions = 0;
      let dayClicks = 0;
      let dayCost = 0;
      let daySales = 0;
      let dayUnitsSold = 0;
      let dayGpPreAd = 0;
      let dayGp = 0;
      const dailyCampaigns = data.daily_campaigns || {};
      const campaigns = Array.isArray(dailyCampaigns[dateKey]) ? dailyCampaigns[dateKey] : [];

      if (campaignName === 'All') {
        if (campaigns.length > 0) {
          campaigns.forEach((camp) => {
            if (!matchesCampaignStatusFilter(
              camp,
              campaignStatuses,
              availableCampaignStatuses,
            )) {
              return;
            }
            dayImpressions += toNumber(camp.impressions);
            dayClicks += toNumber(camp.clicks);
            dayCost += toNumber(camp.spend);
            daySales += toNumber(camp.total_attributed_sales_usd);
            dayUnitsSold += toNumber(camp.total_units_sold);
            dayGpPreAd += toNumber(camp.gross_profit_before_ads_usd);
            dayGp += toNumber(camp.gross_profit_usd);
          });
        } else if (activeStatusFilter === null) {
          const impressions = Array.isArray(data.impressions) ? data.impressions : [];
          const clicks = Array.isArray(data.clicks) ? data.clicks : [];
          const cost = Array.isArray(data.cost) ? data.cost : [];
          const sales = Array.isArray(data.sales_usd) ? data.sales_usd : [];
          const unitsSold = Array.isArray(data.units_sold) ? data.units_sold : [];
          const grossProfitBeforeAds = Array.isArray(data.gross_profit_before_ads_usd)
            ? data.gross_profit_before_ads_usd
            : [];
          const grossProfit = Array.isArray(data.gross_profit_usd) ? data.gross_profit_usd : [];
          dayImpressions = toNumber(impressions[index]);
          dayClicks = toNumber(clicks[index]);
          dayCost = toNumber(cost[index]);
          daySales = toNumber(sales[index]);
          dayUnitsSold = toNumber(unitsSold[index]);
          dayGpPreAd = toNumber(grossProfitBeforeAds[index]);
          dayGp = toNumber(grossProfit[index]);
        }
      } else {
        campaigns.forEach((camp) => {
          if (camp.campaign_name === campaignName
            && matchesCampaignStatusFilter(
              camp,
              campaignStatuses,
              availableCampaignStatuses,
            )) {
            dayImpressions += toNumber(camp.impressions);
            dayClicks += toNumber(camp.clicks);
            dayCost += toNumber(camp.spend);
            daySales += toNumber(camp.total_attributed_sales_usd);
            dayUnitsSold += toNumber(camp.total_units_sold);
            dayGpPreAd += toNumber(camp.gross_profit_before_ads_usd);
            dayGp += toNumber(camp.gross_profit_usd);
          }
        });
      }

      return {
        dateKey: dateKey,
        impressions: dayImpressions,
        clicks: dayClicks,
        cost: dayCost,
        sales_usd: daySales,
        units_sold: dayUnitsSold,
        free_units_downloaded: toNumber((Array.isArray(data.free_units_downloaded)
          ? data.free_units_downloaded
          : [])[index]),
        gross_profit_before_ads_usd: dayGpPreAd,
        gross_profit_usd: dayGp,
      };
    });
  }

  function calculateTotals(dailyStats) {
    const totals = {
      impressions: 0,
      clicks: 0,
      cost: 0,
      sales_usd: 0,
      units_sold: 0,
      gross_profit_before_ads_usd: 0,
      gross_profit_usd: 0,
    };

    (dailyStats || []).forEach((day) => {
      totals.impressions += toNumber(day.impressions);
      totals.clicks += toNumber(day.clicks);
      totals.cost += toNumber(day.cost);
      totals.sales_usd += toNumber(day.sales_usd);
      totals.units_sold += toNumber(day.units_sold);
      totals.gross_profit_before_ads_usd += toNumber(day.gross_profit_before_ads_usd);
      totals.gross_profit_usd += toNumber(day.gross_profit_usd);
    });

    return totals;
  }

  function calculateReconciledTotals(reconciledDailyStats) {
    const totals = {
      cost: 0,
      ads_profit_before_ads_usd: 0,
      matched_ads_profit_before_ads_usd: 0,
      gross_profit_before_ads_usd: 0,
      reconciled_profit_before_ads_usd: 0,
      organic_profit_usd: 0,
      unmatched_pre_ad_profit_usd: 0,
      gross_profit_usd: 0,
    };

    (reconciledDailyStats || []).forEach((day) => {
      totals.cost += toNumber(day.cost);
      totals.ads_profit_before_ads_usd += toNumber(day.ads_profit_before_ads_usd);
      totals.matched_ads_profit_before_ads_usd += toNumber(day.matched_ads_profit_before_ads_usd);
      totals.gross_profit_before_ads_usd += toNumber(day.gross_profit_before_ads_usd);
      totals.reconciled_profit_before_ads_usd += toNumber(day.reconciled_profit_before_ads_usd);
      totals.organic_profit_usd += toNumber(day.organic_profit_usd);
      totals.unmatched_pre_ad_profit_usd += toNumber(day.unmatched_pre_ad_profit_usd);
      totals.gross_profit_usd += toNumber(day.gross_profit_usd);
    });
    return totals;
  }

  function buildTimelineSeries(adsStatsData, dailyStats) {
    const rows = dailyStats || [];
    const labels = Array.isArray(adsStatsData && adsStatsData.labels)
      ? adsStatsData.labels.slice()
      : [];
    const impressions = rows.map((day) => toNumber(day.impressions));
    const clicks = rows.map((day) => toNumber(day.clicks));
    const cost = rows.map((day) => toNumber(day.cost));
    const sales = rows.map((day) => toNumber(day.sales_usd));
    const unitsSold = rows.map((day) => toNumber(day.units_sold));
    const freeUnitsDownloaded = rows.map((day) => toNumber(day.free_units_downloaded));
    const grossProfitBeforeAds = rows.map((day) => toNumber(day.gross_profit_before_ads_usd));
    const grossProfit = rows.map((day) => toNumber(day.gross_profit_usd));

    return {
      labels: labels,
      impressions: impressions,
      clicks: clicks,
      cost: cost,
      sales_usd: sales,
      units_sold: unitsSold,
      free_units_downloaded: freeUnitsDownloaded,
      gross_profit_before_ads_usd: grossProfitBeforeAds,
      gross_profit_usd: grossProfit,
      poas: rows.map((day) => {
        return calculatePoas(day.gross_profit_before_ads_usd, day.cost);
      }),
      cpc: rows.map((day) => {
        const dayClicks = toNumber(day.clicks);
        return dayClicks > 0 ? toNumber(day.cost) / dayClicks : 0;
      }),
      ctr: rows.map((day) => {
        const dayImpressions = toNumber(day.impressions);
        return dayImpressions > 0 ? (toNumber(day.clicks) / dayImpressions) * 100 : 0;
      }),
      conversion_rate: rows.map((day) => {
        const dayClicks = toNumber(day.clicks);
        return dayClicks > 0 ? (toNumber(day.units_sold) / dayClicks) * 100 : 0;
      }),
    };
  }

  function buildDaysOfWeekSeries(dailyStats) {
    const weekdayBuckets = DAYS_OF_WEEK_LABELS.map(() => ({
      count: 0,
      impressions: 0,
      clicks: 0,
      cost: 0,
      sales_usd: 0,
      units_sold: 0,
      free_units_downloaded: 0,
      gross_profit_before_ads_usd: 0,
      gross_profit_usd: 0,
    }));

    (dailyStats || []).forEach((day) => {
      if (toNumber(day.impressions) <= 0) {
        return;
      }
      const weekdayIndex = dayOfWeekIndexForDate(day.dateKey);
      const bucket = weekdayBuckets[weekdayIndex];
      bucket.count += 1;
      bucket.impressions += toNumber(day.impressions);
      bucket.clicks += toNumber(day.clicks);
      bucket.cost += toNumber(day.cost);
      bucket.sales_usd += toNumber(day.sales_usd);
      bucket.units_sold += toNumber(day.units_sold);
      bucket.free_units_downloaded += toNumber(day.free_units_downloaded);
      bucket.gross_profit_before_ads_usd += toNumber(day.gross_profit_before_ads_usd);
      bucket.gross_profit_usd += toNumber(day.gross_profit_usd);
    });

    const impressions = weekdayBuckets.map((bucket) => average(bucket.impressions, bucket.count));
    const clicks = weekdayBuckets.map((bucket) => average(bucket.clicks, bucket.count));
    const cost = weekdayBuckets.map((bucket) => average(bucket.cost, bucket.count));
    const sales = weekdayBuckets.map((bucket) => average(bucket.sales_usd, bucket.count));
    const unitsSold = weekdayBuckets.map((bucket) => average(bucket.units_sold, bucket.count));
    const freeUnitsDownloaded = weekdayBuckets.map((bucket) => (
      average(bucket.free_units_downloaded, bucket.count)
    ));
    const grossProfitBeforeAds = weekdayBuckets.map((bucket) => average(bucket.gross_profit_before_ads_usd, bucket.count));
    const grossProfit = weekdayBuckets.map((bucket) => average(bucket.gross_profit_usd, bucket.count));

    const poas = weekdayBuckets.map((bucket) => {
      const avgCost = average(bucket.cost, bucket.count);
      const avgGrossProfitBeforeAds = average(bucket.gross_profit_before_ads_usd, bucket.count);
      return calculatePoas(avgGrossProfitBeforeAds, avgCost);
    });
    const cpc = weekdayBuckets.map((bucket) => {
      const avgCost = average(bucket.cost, bucket.count);
      const avgClicks = average(bucket.clicks, bucket.count);
      return avgClicks > 0 ? avgCost / avgClicks : 0;
    });
    const ctr = weekdayBuckets.map((bucket) => {
      const avgImpressions = average(bucket.impressions, bucket.count);
      const avgClicks = average(bucket.clicks, bucket.count);
      return avgImpressions > 0 ? (avgClicks / avgImpressions) * 100 : 0;
    });
    const conversionRate = weekdayBuckets.map((bucket) => {
      const avgUnitsSold = average(bucket.units_sold, bucket.count);
      const avgClicks = average(bucket.clicks, bucket.count);
      return avgClicks > 0 ? (avgUnitsSold / avgClicks) * 100 : 0;
    });

    return {
      labels: DAYS_OF_WEEK_LABELS.slice(),
      impressions: impressions,
      clicks: clicks,
      cost: cost,
      sales_usd: sales,
      units_sold: unitsSold,
      free_units_downloaded: freeUnitsDownloaded,
      gross_profit_before_ads_usd: grossProfitBeforeAds,
      gross_profit_usd: grossProfit,
      poas: poas,
      cpc: cpc,
      ctr: ctr,
      conversion_rate: conversionRate,
    };
  }

  function buildStatsFromDaily(adsStatsData, dailyStats, mode) {
    const totals = calculateTotals(dailyStats);
    const series = mode === DAYS_OF_WEEK_MODE
      ? buildDaysOfWeekSeries(dailyStats)
      : buildTimelineSeries(adsStatsData, dailyStats);

    return {
      labels: series.labels,
      impressions: series.impressions,
      clicks: series.clicks,
      cost: series.cost,
      sales_usd: series.sales_usd,
      units_sold: series.units_sold,
      free_units_downloaded: series.free_units_downloaded,
      gross_profit_before_ads_usd: series.gross_profit_before_ads_usd,
      gross_profit_usd: series.gross_profit_usd,
      poas: series.poas,
      cpc: series.cpc,
      ctr: series.ctr,
      conversion_rate: series.conversion_rate,
      totals: totals,
    };
  }

  function buildChartStats(
    adsStatsData, campaignName, campaignStatuses, mode, availableCampaignStatuses,
  ) {
    if (mode === undefined) {
      mode = campaignStatuses; // eslint-disable-line no-param-reassign
      campaignStatuses = 'All'; // eslint-disable-line no-param-reassign
    }
    const dailyStats = getDailyStatsForCampaign(
      adsStatsData,
      campaignName,
      campaignStatuses,
      availableCampaignStatuses,
    );
    return buildStatsFromDaily(adsStatsData, dailyStats, mode);
  }

  function getReconciledDailyStats(baseDailyStats, reconciledChartData) {
    const data = reconciledChartData || {};
    const labels = getArrayField(data, 'labels');
    const gpPreAd = getArrayField(data, 'gross_profit_before_ads_usd');
    const organicProfit = getArrayField(data, 'organic_profit_usd');
    const reconciledMatchedProfitBeforeAds = getArrayField(
      data,
      'reconciled_matched_profit_before_ads_usd',
    );
    const matchedAdsSalesCount = getArrayField(data, 'matched_ads_sales_count');
    const organicSalesCount = getArrayField(data, 'organic_sales_count');
    const reconciledSalesCount = getArrayField(data, 'reconciled_sales_count');
    const unmatchedAdsSalesCount = getArrayField(data, 'unmatched_ads_sales_count');
    const adsSalesDetails = getArrayField(data, 'ads_sales_details');
    const matchedAdsSalesDetails = getArrayField(data, 'matched_ads_sales_details');
    const reconciledSalesDetails = getArrayField(data, 'reconciled_sales_details');
    const unmatchedAdsSalesDetails = getArrayField(data, 'unmatched_ads_sales_details');
    const adsProfitDetails = getArrayField(data, 'ads_profit_details');
    const matchedAdsProfitDetails = getArrayField(data, 'matched_ads_profit_details');
    const reconciledMatchedProfitDetails = getArrayField(
      data,
      'reconciled_matched_profit_details',
    );
    const profitBeforeAdsReconciledDetails = getArrayField(
      data,
      'profit_before_ads_reconciled_details',
    );
    const organicProfitDetails = getArrayField(data, 'organic_profit_details');
    const organicSalesDetails = getArrayField(data, 'organic_sales_details');
    const rowsByDate = {};

    labels.forEach((dateKey, index) => {
      const dayAdsSalesDetails = adsSalesDetails[index];
      const dayMatchedAdsSalesDetails = matchedAdsSalesDetails[index];
      const dayReconciledSalesDetails = reconciledSalesDetails[index];
      const dayUnmatchedAdsSalesDetails = unmatchedAdsSalesDetails[index];
      const dayOrganicSalesDetails = organicSalesDetails[index];
      const dayAdsBookSalesDetails = filterBookSalesDetails(dayAdsSalesDetails);
      const dayMatchedBookSalesDetails = filterBookSalesDetails(dayMatchedAdsSalesDetails);
      const dayOrganicBookSalesDetails = filterBookSalesDetails(dayOrganicSalesDetails);
      const dayReconciledBookSalesDetails = filterBookSalesDetails(dayReconciledSalesDetails);
      const dayUnmatchedBookSalesDetails = filterBookSalesDetails(dayUnmatchedAdsSalesDetails);
      const dayAdsKenpDetails = filterKenpDetails(dayAdsSalesDetails);
      const dayMatchedKenpDetails = filterKenpDetails(dayMatchedAdsSalesDetails);
      const dayOrganicKenpDetails = filterKenpDetails(dayOrganicSalesDetails);
      const dayUnmatchedKenpDetails = filterKenpDetails(dayUnmatchedAdsSalesDetails);
      const dayReconciledKenpDetails = filterKenpDetails(dayReconciledSalesDetails);
      const dayAdsProfitDetails = adsProfitDetails[index];
      const dayMatchedAdsProfitDetails = matchedAdsProfitDetails[index];
      const dayReconciledMatchedProfitDetails = reconciledMatchedProfitDetails[index];
      const dayProfitBeforeAdsReconciledDetails = profitBeforeAdsReconciledDetails[index];
      const dayRows = {
        gross_profit_before_ads_usd: toNumber(gpPreAd[index]),
        reconciled_matched_profit_before_ads_usd: toNumber(
          reconciledMatchedProfitBeforeAds[index],
        ),
        organic_profit_usd: toNumber(organicProfit[index]),
        matched_ads_sales_count: toNumber(matchedAdsSalesCount[index]),
        organic_sales_count: toNumber(organicSalesCount[index]),
        reconciled_sales_count: toNumber(reconciledSalesCount[index]),
        unmatched_ads_sales_count: toNumber(unmatchedAdsSalesCount[index]),
        ads_sales_tooltip_lines: buildCountTooltipLines(dayAdsBookSalesDetails),
        matched_ads_sales_tooltip_lines: buildCountTooltipLines(dayMatchedBookSalesDetails),
        reconciled_sales_tooltip_lines: buildSectionedCountTooltipLines(
          dayMatchedBookSalesDetails,
          dayOrganicBookSalesDetails,
        ),
        unmatched_ads_sales_tooltip_lines: buildCountTooltipLines(dayUnmatchedBookSalesDetails),
        ads_kenp_pages_tooltip_lines: buildCountTooltipLines(dayAdsKenpDetails),
        matched_ads_kenp_pages_tooltip_lines: buildCountTooltipLines(dayMatchedKenpDetails),
        unmatched_ads_kenp_pages_tooltip_lines: buildCountTooltipLines(dayUnmatchedKenpDetails),
        reconciled_kenp_pages_tooltip_lines: buildSectionedCountTooltipLines(
          dayMatchedKenpDetails,
          dayOrganicKenpDetails,
        ),
        ads_profit_tooltip_lines: buildProfitAmountTooltipLines(
          adsProfitDetails[index],
          INLINE_KENP_PROFIT_TOOLTIP_OPTIONS,
        ),
        matched_ads_profit_tooltip_lines: buildProfitAmountTooltipLines(
          matchedAdsProfitDetails[index],
          INLINE_KENP_PROFIT_TOOLTIP_OPTIONS,
        ),
        reconciled_matched_profit_tooltip_lines: buildSectionedProfitTooltipLines(
          matchedAdsProfitDetails[index],
          organicProfitDetails[index],
        ),
        profit_before_ads_reconciled_tooltip_lines: buildSectionedProfitTooltipLines(
          matchedAdsProfitDetails[index],
          organicProfitDetails[index],
        ),
        ads_kenp_pages_count: sumCountDetails(dayAdsKenpDetails),
        matched_ads_kenp_pages_count: sumCountDetails(dayMatchedKenpDetails),
        unmatched_ads_kenp_pages_count: sumCountDetails(dayUnmatchedKenpDetails),
        reconciled_kenp_pages_count: sumCountDetails(dayReconciledKenpDetails),
      };
      if (Array.isArray(dayAdsProfitDetails) && dayAdsProfitDetails.length > 0) {
        dayRows.ads_profit_before_ads_from_details_usd = sumAmountDetails(dayAdsProfitDetails);
      }
      if (Array.isArray(dayMatchedAdsProfitDetails) && dayMatchedAdsProfitDetails.length > 0) {
        dayRows.matched_ads_profit_before_ads_from_details_usd = (
          sumAmountDetails(dayMatchedAdsProfitDetails)
        );
      }
      if (Array.isArray(dayReconciledMatchedProfitDetails)
        && dayReconciledMatchedProfitDetails.length > 0) {
        dayRows.reconciled_matched_profit_before_ads_from_details_usd = (
          sumAmountDetails(dayReconciledMatchedProfitDetails)
        );
      }
      if (Array.isArray(dayProfitBeforeAdsReconciledDetails)
        && dayProfitBeforeAdsReconciledDetails.length > 0) {
        dayRows.reconciled_profit_before_ads_from_details_usd = (
          sumAmountDetails(dayProfitBeforeAdsReconciledDetails)
        );
      }
      rowsByDate[dateKey] = dayRows;
    });

    return (baseDailyStats || []).map((day) => {
      const reconciledDay = rowsByDate[day.dateKey] || {};
      const dayCost = toNumber(day.cost);
      const dayMatchedAdsProfitBeforeAds = Object.prototype.hasOwnProperty.call(
        reconciledDay,
        'matched_ads_profit_before_ads_from_details_usd',
      )
        ? toNumber(reconciledDay.matched_ads_profit_before_ads_from_details_usd)
        : toNumber(reconciledDay.gross_profit_before_ads_usd);
      const dayOrganicProfit = toNumber(reconciledDay.organic_profit_usd);
      const dayAdsProfitBeforeAds = Object.prototype.hasOwnProperty.call(
        reconciledDay,
        'ads_profit_before_ads_from_details_usd',
      )
        ? toNumber(reconciledDay.ads_profit_before_ads_from_details_usd)
        : toNumber(day.gross_profit_before_ads_usd);
      const dayReconciledMatchedProfitBeforeAds = Object.prototype.hasOwnProperty.call(
        reconciledDay,
        'reconciled_matched_profit_before_ads_from_details_usd',
      )
        ? toNumber(reconciledDay.reconciled_matched_profit_before_ads_from_details_usd)
        : Object.prototype.hasOwnProperty.call(
          reconciledDay,
        'reconciled_matched_profit_before_ads_usd',
      )
          ? toNumber(reconciledDay.reconciled_matched_profit_before_ads_usd)
          : (dayMatchedAdsProfitBeforeAds + dayOrganicProfit);
      const dayUnmatchedAdsProfitBeforeAds = (
        dayAdsProfitBeforeAds - dayMatchedAdsProfitBeforeAds
      );
      const dayReconciledProfitBeforeAds = Object.prototype.hasOwnProperty.call(
        reconciledDay,
        'reconciled_profit_before_ads_from_details_usd',
      )
        ? toNumber(reconciledDay.reconciled_profit_before_ads_from_details_usd)
        : (
          dayMatchedAdsProfitBeforeAds
          + dayUnmatchedAdsProfitBeforeAds
          + dayOrganicProfit
        );
      return {
        dateKey: day.dateKey,
        cost: dayCost,
        raw_gross_profit_before_ads_usd: dayAdsProfitBeforeAds,
        ads_profit_before_ads_usd: dayAdsProfitBeforeAds,
        matched_ads_profit_before_ads_usd: dayMatchedAdsProfitBeforeAds,
        gross_profit_before_ads_usd: dayMatchedAdsProfitBeforeAds,
        reconciled_matched_profit_before_ads_usd: dayReconciledMatchedProfitBeforeAds,
        reconciled_profit_before_ads_usd: dayReconciledProfitBeforeAds,
        organic_profit_usd: dayOrganicProfit,
        unmatched_pre_ad_profit_usd: dayUnmatchedAdsProfitBeforeAds,
        matched_ads_sales_count: toNumber(reconciledDay.matched_ads_sales_count),
        organic_sales_count: toNumber(reconciledDay.organic_sales_count),
        reconciled_sales_count: Object.prototype.hasOwnProperty.call(
          reconciledDay,
          'reconciled_sales_count',
        )
          ? toNumber(reconciledDay.reconciled_sales_count)
          : (toNumber(reconciledDay.matched_ads_sales_count)
            + toNumber(reconciledDay.organic_sales_count)),
        unmatched_ads_sales_count: toNumber(reconciledDay.unmatched_ads_sales_count),
        ads_kenp_pages_count: toNumber(reconciledDay.ads_kenp_pages_count),
        matched_ads_kenp_pages_count: toNumber(reconciledDay.matched_ads_kenp_pages_count),
        unmatched_ads_kenp_pages_count: toNumber(reconciledDay.unmatched_ads_kenp_pages_count),
        reconciled_kenp_pages_count: toNumber(reconciledDay.reconciled_kenp_pages_count),
        ads_sales_tooltip_lines: getArrayField(reconciledDay, 'ads_sales_tooltip_lines'),
        matched_ads_sales_tooltip_lines: getArrayField(
          reconciledDay,
          'matched_ads_sales_tooltip_lines',
        ),
        reconciled_sales_tooltip_lines: getArrayField(
          reconciledDay,
          'reconciled_sales_tooltip_lines',
        ),
        unmatched_ads_sales_tooltip_lines: getArrayField(
          reconciledDay,
          'unmatched_ads_sales_tooltip_lines',
        ),
        ads_kenp_pages_tooltip_lines: getArrayField(
          reconciledDay,
          'ads_kenp_pages_tooltip_lines',
        ),
        matched_ads_kenp_pages_tooltip_lines: getArrayField(
          reconciledDay,
          'matched_ads_kenp_pages_tooltip_lines',
        ),
        unmatched_ads_kenp_pages_tooltip_lines: getArrayField(
          reconciledDay,
          'unmatched_ads_kenp_pages_tooltip_lines',
        ),
        reconciled_kenp_pages_tooltip_lines: getArrayField(
          reconciledDay,
          'reconciled_kenp_pages_tooltip_lines',
        ),
        ads_profit_tooltip_lines: getArrayField(reconciledDay, 'ads_profit_tooltip_lines'),
        matched_ads_profit_tooltip_lines: getArrayField(
          reconciledDay,
          'matched_ads_profit_tooltip_lines',
        ),
        reconciled_matched_profit_tooltip_lines: getArrayField(
          reconciledDay,
          'reconciled_matched_profit_tooltip_lines',
        ),
        profit_before_ads_reconciled_tooltip_lines: getArrayField(
          reconciledDay,
          'profit_before_ads_reconciled_tooltip_lines',
        ),
        gross_profit_usd: dayReconciledProfitBeforeAds - dayCost,
        poas: dayCost > 0 ? dayAdsProfitBeforeAds / dayCost : 0,
        tpoas: dayCost > 0 ? dayReconciledProfitBeforeAds / dayCost : 0,
      };
    });
  }

  function buildReconciledDaysOfWeekSeries(dailyStats) {
    const weekdayBuckets = DAYS_OF_WEEK_LABELS.map(() => ({
      count: 0,
      cost: 0,
      raw_gross_profit_before_ads_usd: 0,
      ads_profit_before_ads_usd: 0,
      matched_ads_profit_before_ads_usd: 0,
      gross_profit_before_ads_usd: 0,
      reconciled_matched_profit_before_ads_usd: 0,
      reconciled_profit_before_ads_usd: 0,
      organic_profit_usd: 0,
      unmatched_pre_ad_profit_usd: 0,
      matched_ads_sales_count: 0,
      organic_sales_count: 0,
      reconciled_sales_count: 0,
      unmatched_ads_sales_count: 0,
      ads_kenp_pages_count: 0,
      matched_ads_kenp_pages_count: 0,
      unmatched_ads_kenp_pages_count: 0,
      reconciled_kenp_pages_count: 0,
      gross_profit_usd: 0,
    }));

    (dailyStats || []).forEach((day) => {
      if (toNumber(day.impressions) <= 0) {
        return;
      }
      const weekdayIndex = dayOfWeekIndexForDate(day.dateKey);
      const bucket = weekdayBuckets[weekdayIndex];
      bucket.count += 1;
      bucket.cost += toNumber(day.cost);
      bucket.raw_gross_profit_before_ads_usd += toNumber(day.raw_gross_profit_before_ads_usd);
      bucket.ads_profit_before_ads_usd += toNumber(day.ads_profit_before_ads_usd);
      bucket.matched_ads_profit_before_ads_usd += toNumber(day.matched_ads_profit_before_ads_usd);
      bucket.gross_profit_before_ads_usd += toNumber(day.gross_profit_before_ads_usd);
      bucket.reconciled_matched_profit_before_ads_usd += toNumber(
        day.reconciled_matched_profit_before_ads_usd,
      );
      bucket.reconciled_profit_before_ads_usd += toNumber(day.reconciled_profit_before_ads_usd);
      bucket.organic_profit_usd += toNumber(day.organic_profit_usd);
      bucket.unmatched_pre_ad_profit_usd += toNumber(day.unmatched_pre_ad_profit_usd);
      bucket.matched_ads_sales_count += toNumber(day.matched_ads_sales_count);
      bucket.organic_sales_count += toNumber(day.organic_sales_count);
      bucket.reconciled_sales_count += toNumber(day.reconciled_sales_count);
      bucket.unmatched_ads_sales_count += toNumber(day.unmatched_ads_sales_count);
      bucket.ads_kenp_pages_count += toNumber(day.ads_kenp_pages_count);
      bucket.matched_ads_kenp_pages_count += toNumber(day.matched_ads_kenp_pages_count);
      bucket.unmatched_ads_kenp_pages_count += toNumber(day.unmatched_ads_kenp_pages_count);
      bucket.reconciled_kenp_pages_count += toNumber(day.reconciled_kenp_pages_count);
      bucket.gross_profit_usd += toNumber(day.gross_profit_usd);
    });

    const cost = weekdayBuckets.map((bucket) => average(bucket.cost, bucket.count));
    const adsProfitBeforeAds = weekdayBuckets.map((bucket) =>
      average(bucket.ads_profit_before_ads_usd, bucket.count));
    const matchedAdsProfitBeforeAds = weekdayBuckets.map((bucket) =>
      average(bucket.matched_ads_profit_before_ads_usd, bucket.count));
    const grossProfitBeforeAds = weekdayBuckets.map((bucket) =>
      average(bucket.gross_profit_before_ads_usd, bucket.count));
    const reconciledMatchedProfitBeforeAds = weekdayBuckets.map((bucket) =>
      average(bucket.reconciled_matched_profit_before_ads_usd, bucket.count));
    const reconciledProfitBeforeAds = weekdayBuckets.map((bucket) =>
      average(bucket.reconciled_profit_before_ads_usd, bucket.count));
    const organicProfit = weekdayBuckets.map((bucket) =>
      average(bucket.organic_profit_usd, bucket.count));
    const unmatchedPreAdProfit = weekdayBuckets.map((bucket) =>
      average(bucket.unmatched_pre_ad_profit_usd, bucket.count));
    const matchedAdsSalesCount = weekdayBuckets.map((bucket) =>
      average(bucket.matched_ads_sales_count, bucket.count));
    const organicSalesCount = weekdayBuckets.map((bucket) =>
      average(bucket.organic_sales_count, bucket.count));
    const reconciledSalesCount = weekdayBuckets.map((bucket) =>
      average(bucket.reconciled_sales_count, bucket.count));
    const unmatchedAdsSalesCount = weekdayBuckets.map((bucket) =>
      average(bucket.unmatched_ads_sales_count, bucket.count));
    const adsKenpPagesCount = weekdayBuckets.map((bucket) =>
      average(bucket.ads_kenp_pages_count, bucket.count));
    const matchedAdsKenpPagesCount = weekdayBuckets.map((bucket) =>
      average(bucket.matched_ads_kenp_pages_count, bucket.count));
    const unmatchedAdsKenpPagesCount = weekdayBuckets.map((bucket) =>
      average(bucket.unmatched_ads_kenp_pages_count, bucket.count));
    const reconciledKenpPagesCount = weekdayBuckets.map((bucket) =>
      average(bucket.reconciled_kenp_pages_count, bucket.count));
    const grossProfit = weekdayBuckets.map((bucket) =>
      average(bucket.gross_profit_usd, bucket.count));

    return {
      labels: DAYS_OF_WEEK_LABELS.slice(),
      cost: cost,
      ads_profit_before_ads_usd: adsProfitBeforeAds,
      matched_ads_profit_before_ads_usd: matchedAdsProfitBeforeAds,
      gross_profit_before_ads_usd: grossProfitBeforeAds,
      reconciled_matched_profit_before_ads_usd: reconciledMatchedProfitBeforeAds,
      reconciled_profit_before_ads_usd: reconciledProfitBeforeAds,
      organic_profit_usd: organicProfit,
      unmatched_pre_ad_profit_usd: unmatchedPreAdProfit,
      matched_ads_sales_count: matchedAdsSalesCount,
      organic_sales_count: organicSalesCount,
      reconciled_sales_count: reconciledSalesCount,
      ads_kenp_pages_count: adsKenpPagesCount,
      matched_ads_kenp_pages_count: matchedAdsKenpPagesCount,
      unmatched_ads_kenp_pages_count: unmatchedAdsKenpPagesCount,
      reconciled_kenp_pages_count: reconciledKenpPagesCount,
      gross_profit_usd: grossProfit,
      unmatched_ads_sales_count: unmatchedAdsSalesCount,
      ads_sales_tooltip_lines: DAYS_OF_WEEK_LABELS.map(() => []),
      matched_ads_sales_tooltip_lines: DAYS_OF_WEEK_LABELS.map(() => []),
      reconciled_sales_tooltip_lines: DAYS_OF_WEEK_LABELS.map(() => []),
      unmatched_ads_sales_tooltip_lines: DAYS_OF_WEEK_LABELS.map(() => []),
      ads_kenp_pages_tooltip_lines: DAYS_OF_WEEK_LABELS.map(() => []),
      matched_ads_kenp_pages_tooltip_lines: DAYS_OF_WEEK_LABELS.map(() => []),
      unmatched_ads_kenp_pages_tooltip_lines: DAYS_OF_WEEK_LABELS.map(() => []),
      reconciled_kenp_pages_tooltip_lines: DAYS_OF_WEEK_LABELS.map(() => []),
      ads_profit_tooltip_lines: DAYS_OF_WEEK_LABELS.map(() => []),
      matched_ads_profit_tooltip_lines: DAYS_OF_WEEK_LABELS.map(() => []),
      reconciled_matched_profit_tooltip_lines: DAYS_OF_WEEK_LABELS.map(() => []),
      profit_before_ads_reconciled_tooltip_lines: DAYS_OF_WEEK_LABELS.map(() => []),
      poas: weekdayBuckets.map((bucket) => {
        const avgCost = average(bucket.cost, bucket.count);
        const avgRawGrossProfitBeforeAds = average(
          bucket.raw_gross_profit_before_ads_usd,
          bucket.count,
        );
        return calculatePoas(avgRawGrossProfitBeforeAds, avgCost);
      }),
      tpoas: weekdayBuckets.map((bucket) => {
        const avgCost = average(bucket.cost, bucket.count);
        const avgRawGrossProfitBeforeAds = average(
          bucket.raw_gross_profit_before_ads_usd,
          bucket.count,
        );
        const avgOrganicProfit = average(bucket.organic_profit_usd, bucket.count);
        return calculateTpoas(avgRawGrossProfitBeforeAds, avgOrganicProfit, avgCost);
      }),
    };
  }

  function buildReconciledChartStats(
    adsStatsData, campaignName, campaignStatuses, mode, reconciledChartData, availableCampaignStatuses,
  ) {
    if (reconciledChartData === undefined) {
      reconciledChartData = mode; // eslint-disable-line no-param-reassign
      mode = campaignStatuses; // eslint-disable-line no-param-reassign
      campaignStatuses = 'All'; // eslint-disable-line no-param-reassign
    }
    if (campaignName !== 'All') {
      const campaignStats = buildChartStats(
        adsStatsData,
        campaignName,
        campaignStatuses,
        mode,
        availableCampaignStatuses,
      );
      const adsOnlyPoas = (campaignStats.poas || []).map((value) => toNumber(value));
      return {
        labels: Array.isArray(campaignStats.labels) ? campaignStats.labels : [],
        cost: Array.isArray(campaignStats.cost) ? campaignStats.cost : [],
        ads_profit_before_ads_usd: Array.isArray(campaignStats.gross_profit_before_ads_usd)
          ? campaignStats.gross_profit_before_ads_usd
          : [],
        matched_ads_profit_before_ads_usd: [],
        gross_profit_before_ads_usd: Array.isArray(campaignStats.gross_profit_before_ads_usd)
          ? campaignStats.gross_profit_before_ads_usd
          : [],
        reconciled_matched_profit_before_ads_usd: [],
        reconciled_profit_before_ads_usd: Array.isArray(campaignStats.gross_profit_before_ads_usd)
          ? campaignStats.gross_profit_before_ads_usd
          : [],
        gross_profit_usd: Array.isArray(campaignStats.gross_profit_usd)
          ? campaignStats.gross_profit_usd
          : [],
        organic_profit_usd: adsOnlyPoas.map(() => 0),
        unmatched_pre_ad_profit_usd: adsOnlyPoas.map(() => 0),
        matched_ads_sales_count: adsOnlyPoas.map(() => 0),
        organic_sales_count: adsOnlyPoas.map(() => 0),
        reconciled_sales_count: adsOnlyPoas.map(() => 0),
        unmatched_ads_sales_count: adsOnlyPoas.map(() => 0),
        ads_kenp_pages_count: adsOnlyPoas.map(() => 0),
        matched_ads_kenp_pages_count: adsOnlyPoas.map(() => 0),
        unmatched_ads_kenp_pages_count: adsOnlyPoas.map(() => 0),
        reconciled_kenp_pages_count: adsOnlyPoas.map(() => 0),
        ads_sales_tooltip_lines: adsOnlyPoas.map(() => []),
        matched_ads_sales_tooltip_lines: adsOnlyPoas.map(() => []),
        reconciled_sales_tooltip_lines: adsOnlyPoas.map(() => []),
        unmatched_ads_sales_tooltip_lines: adsOnlyPoas.map(() => []),
        ads_kenp_pages_tooltip_lines: adsOnlyPoas.map(() => []),
        matched_ads_kenp_pages_tooltip_lines: adsOnlyPoas.map(() => []),
        unmatched_ads_kenp_pages_tooltip_lines: adsOnlyPoas.map(() => []),
        reconciled_kenp_pages_tooltip_lines: adsOnlyPoas.map(() => []),
        ads_profit_tooltip_lines: adsOnlyPoas.map(() => []),
        matched_ads_profit_tooltip_lines: adsOnlyPoas.map(() => []),
        reconciled_matched_profit_tooltip_lines: adsOnlyPoas.map(() => []),
        profit_before_ads_reconciled_tooltip_lines: adsOnlyPoas.map(() => []),
        poas: adsOnlyPoas,
        tpoas: adsOnlyPoas.map(() => 0),
        is_ads_only_campaign_series: true,
        totals: {
          cost: toNumber(campaignStats.totals && campaignStats.totals.cost),
          ads_profit_before_ads_usd: toNumber(
            campaignStats.totals && campaignStats.totals.gross_profit_before_ads_usd,
          ),
          matched_ads_profit_before_ads_usd: 0,
          gross_profit_before_ads_usd: toNumber(
            campaignStats.totals && campaignStats.totals.gross_profit_before_ads_usd,
          ),
          reconciled_profit_before_ads_usd: toNumber(
            campaignStats.totals && campaignStats.totals.gross_profit_before_ads_usd,
          ),
          organic_profit_usd: 0,
          unmatched_pre_ad_profit_usd: 0,
          gross_profit_usd: toNumber(campaignStats.totals && campaignStats.totals.gross_profit_usd),
        },
      };
    }

    const baseDailyStats = getDailyStatsForCampaign(
      adsStatsData,
      'All',
      campaignStatuses,
      availableCampaignStatuses,
    );
    const reconciledDailyStats = getReconciledDailyStats(baseDailyStats, reconciledChartData).map(
      (day, index) => ({
        dateKey: day.dateKey,
        impressions: toNumber(baseDailyStats[index] && baseDailyStats[index].impressions),
        cost: day.cost,
        raw_gross_profit_before_ads_usd: day.raw_gross_profit_before_ads_usd,
        ads_profit_before_ads_usd: day.ads_profit_before_ads_usd,
        matched_ads_profit_before_ads_usd: day.matched_ads_profit_before_ads_usd,
        gross_profit_before_ads_usd: day.gross_profit_before_ads_usd,
        reconciled_matched_profit_before_ads_usd: day.reconciled_matched_profit_before_ads_usd,
        reconciled_profit_before_ads_usd: day.reconciled_profit_before_ads_usd,
        organic_profit_usd: day.organic_profit_usd,
        unmatched_pre_ad_profit_usd: day.unmatched_pre_ad_profit_usd,
        matched_ads_sales_count: day.matched_ads_sales_count,
        organic_sales_count: day.organic_sales_count,
        reconciled_sales_count: day.reconciled_sales_count,
        unmatched_ads_sales_count: day.unmatched_ads_sales_count,
        ads_kenp_pages_count: day.ads_kenp_pages_count,
        matched_ads_kenp_pages_count: day.matched_ads_kenp_pages_count,
        unmatched_ads_kenp_pages_count: day.unmatched_ads_kenp_pages_count,
        reconciled_kenp_pages_count: day.reconciled_kenp_pages_count,
        ads_sales_tooltip_lines: day.ads_sales_tooltip_lines,
        matched_ads_sales_tooltip_lines: day.matched_ads_sales_tooltip_lines,
        reconciled_sales_tooltip_lines: day.reconciled_sales_tooltip_lines,
        unmatched_ads_sales_tooltip_lines: day.unmatched_ads_sales_tooltip_lines,
        ads_kenp_pages_tooltip_lines: day.ads_kenp_pages_tooltip_lines,
        matched_ads_kenp_pages_tooltip_lines: day.matched_ads_kenp_pages_tooltip_lines,
        unmatched_ads_kenp_pages_tooltip_lines: day.unmatched_ads_kenp_pages_tooltip_lines,
        reconciled_kenp_pages_tooltip_lines: day.reconciled_kenp_pages_tooltip_lines,
        ads_profit_tooltip_lines: day.ads_profit_tooltip_lines,
        matched_ads_profit_tooltip_lines: day.matched_ads_profit_tooltip_lines,
        reconciled_matched_profit_tooltip_lines: day.reconciled_matched_profit_tooltip_lines,
        profit_before_ads_reconciled_tooltip_lines:
          day.profit_before_ads_reconciled_tooltip_lines,
        gross_profit_usd: day.gross_profit_usd,
      }),
    );
    const totals = calculateReconciledTotals(reconciledDailyStats);

    if (mode === DAYS_OF_WEEK_MODE) {
      return {
        ...buildReconciledDaysOfWeekSeries(reconciledDailyStats),
        totals: totals,
      };
    }

    return {
      labels: baseDailyStats.map((day) => day.dateKey),
      cost: reconciledDailyStats.map((day) => day.cost),
      ads_profit_before_ads_usd: reconciledDailyStats.map(
        (day) => day.ads_profit_before_ads_usd),
      matched_ads_profit_before_ads_usd: reconciledDailyStats.map(
        (day) => day.matched_ads_profit_before_ads_usd),
      gross_profit_before_ads_usd: reconciledDailyStats.map(
        (day) => day.gross_profit_before_ads_usd),
      reconciled_matched_profit_before_ads_usd: reconciledDailyStats.map(
        (day) => day.reconciled_matched_profit_before_ads_usd),
      reconciled_profit_before_ads_usd: reconciledDailyStats.map(
        (day) => day.reconciled_profit_before_ads_usd),
      gross_profit_usd: reconciledDailyStats.map((day) => day.gross_profit_usd),
      organic_profit_usd: reconciledDailyStats.map((day) => day.organic_profit_usd),
      unmatched_pre_ad_profit_usd: reconciledDailyStats.map(
        (day) => day.unmatched_pre_ad_profit_usd),
      matched_ads_sales_count: reconciledDailyStats.map(
        (day) => day.matched_ads_sales_count),
      organic_sales_count: reconciledDailyStats.map(
        (day) => day.organic_sales_count),
      reconciled_sales_count: reconciledDailyStats.map(
        (day) => day.reconciled_sales_count),
      unmatched_ads_sales_count: reconciledDailyStats.map(
        (day) => day.unmatched_ads_sales_count),
      ads_kenp_pages_count: reconciledDailyStats.map(
        (day) => day.ads_kenp_pages_count),
      matched_ads_kenp_pages_count: reconciledDailyStats.map(
        (day) => day.matched_ads_kenp_pages_count),
      unmatched_ads_kenp_pages_count: reconciledDailyStats.map(
        (day) => day.unmatched_ads_kenp_pages_count),
      reconciled_kenp_pages_count: reconciledDailyStats.map(
        (day) => day.reconciled_kenp_pages_count),
      ads_sales_tooltip_lines: reconciledDailyStats.map(
        (day) => day.ads_sales_tooltip_lines),
      matched_ads_sales_tooltip_lines: reconciledDailyStats.map(
        (day) => day.matched_ads_sales_tooltip_lines),
      reconciled_sales_tooltip_lines: reconciledDailyStats.map(
        (day) => day.reconciled_sales_tooltip_lines),
      unmatched_ads_sales_tooltip_lines: reconciledDailyStats.map(
        (day) => day.unmatched_ads_sales_tooltip_lines),
      ads_kenp_pages_tooltip_lines: reconciledDailyStats.map(
        (day) => day.ads_kenp_pages_tooltip_lines),
      matched_ads_kenp_pages_tooltip_lines: reconciledDailyStats.map(
        (day) => day.matched_ads_kenp_pages_tooltip_lines),
      unmatched_ads_kenp_pages_tooltip_lines: reconciledDailyStats.map(
        (day) => day.unmatched_ads_kenp_pages_tooltip_lines),
      reconciled_kenp_pages_tooltip_lines: reconciledDailyStats.map(
        (day) => day.reconciled_kenp_pages_tooltip_lines),
      ads_profit_tooltip_lines: reconciledDailyStats.map(
        (day) => day.ads_profit_tooltip_lines),
      matched_ads_profit_tooltip_lines: reconciledDailyStats.map(
        (day) => day.matched_ads_profit_tooltip_lines),
      reconciled_matched_profit_tooltip_lines: reconciledDailyStats.map(
        (day) => day.reconciled_matched_profit_tooltip_lines),
      profit_before_ads_reconciled_tooltip_lines: reconciledDailyStats.map(
        (day) => day.profit_before_ads_reconciled_tooltip_lines),
      poas: reconciledDailyStats.map((day) => {
        return calculatePoas(day.raw_gross_profit_before_ads_usd, day.cost);
      }),
      tpoas: reconciledDailyStats.map((day) => {
        return calculateTpoas(day.raw_gross_profit_before_ads_usd, day.organic_profit_usd, day.cost);
      }),
      is_ads_only_campaign_series: false,
      totals: totals,
    };
  }

  function buildReconciliationDebugCsv(debugPayload) {
    if (typeof debugPayload === 'string') {
      return debugPayload;
    }
    const payload = debugPayload || {};
    const rows = Array.isArray(payload.rows) ? payload.rows : [];
    if (rows.length === 0) {
      return '';
    }
    const header = Object.keys(rows[0]);
    const lines = [header.map(escapeCsvValue).join(',')];
    rows.forEach((row) => {
      const line = header.map((key) => escapeCsvValue(row[key]));
      lines.push(line.join(','));
    });
    return lines.join('\n');
  }

  async function copyTextToClipboard(text) {
    const textValue = String(text == null ? '' : text);
    if (typeof navigator !== 'undefined'
      && navigator.clipboard
      && typeof navigator.clipboard.writeText === 'function') {
      await navigator.clipboard.writeText(textValue);
      return true;
    }

    if (typeof document === 'undefined' || !document.body || typeof document.createElement !== 'function') {
      return false;
    }

    const textarea = document.createElement('textarea');
    textarea.value = textValue;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.top = '-9999px';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    textarea.setSelectionRange(0, textarea.value.length);

    try {
      if (typeof document.execCommand !== 'function') {
        return false;
      }
      return document.execCommand('copy');
    } finally {
      textarea.remove();
    }
  }

  function showCopyFeedback(popup, options) {
    if (!popup) {
      return;
    }

    const config = options || {};
    const message = String(config.message || 'Copied to clipboard!');
    const visibleDurationMs = Number(config.visibleDurationMs) || 2000;
    const fadeDurationMs = Number(config.fadeDurationMs) || 1000;

    if (popup._copyFeedbackVisibleTimer) {
      clearTimeout(popup._copyFeedbackVisibleTimer);
    }
    if (popup._copyFeedbackHideTimer) {
      clearTimeout(popup._copyFeedbackHideTimer);
    }

    popup.textContent = message;
    popup.setAttribute('aria-hidden', 'false');
    popup.classList.remove('is-fading');
    popup.classList.add('is-visible');

    popup._copyFeedbackVisibleTimer = setTimeout(() => {
      popup.classList.add('is-fading');
      popup._copyFeedbackHideTimer = setTimeout(() => {
        popup.classList.remove('is-visible');
        popup.classList.remove('is-fading');
        popup.setAttribute('aria-hidden', 'true');
      }, fadeDurationMs);
    }, visibleDurationMs);
  }

  function normalizeSearchTermRow(rawRow) {
    if (!rawRow || typeof rawRow !== 'object') {
      return null;
    }

    const dateValue = String(rawRow.date || '').trim();
    const campaignName = String(rawRow.campaign_name || '').trim();
    const searchTerm = String(rawRow.search_term || '').trim();
    const keywordType = String(rawRow.keyword_type || '').trim();
    if (!isIsoDateString(dateValue) || !campaignName || !searchTerm || !keywordType) {
      return null;
    }

    return {
      key: String(rawRow.key || '').trim(),
      date: dateValue,
      campaign_id: String(rawRow.campaign_id || '').trim(),
      campaign_name: campaignName,
      campaign_status: normalizeCampaignStatus(rawRow.campaign_status),
      ad_group_id: String(rawRow.ad_group_id || '').trim(),
      ad_group_name: String(rawRow.ad_group_name || '').trim(),
      search_term: searchTerm,
      keyword_id: String(rawRow.keyword_id || '').trim(),
      keyword: String(rawRow.keyword || '').trim(),
      targeting: String(rawRow.targeting || '').trim(),
      keyword_type: keywordType,
      match_type: String(rawRow.match_type || '').trim(),
      ad_keyword_status: String(rawRow.ad_keyword_status || '').trim(),
      impressions: Math.max(0, Math.round(toNumber(rawRow.impressions))),
      clicks: Math.max(0, Math.round(toNumber(rawRow.clicks))),
      cost_usd: toNumber(rawRow.cost_usd),
      sales14d_usd: toNumber(rawRow.sales14d_usd),
      purchases14d: Math.max(0, Math.round(toNumber(rawRow.purchases14d))),
      units_sold_clicks14d: Math.max(0, Math.round(toNumber(rawRow.units_sold_clicks14d))),
      kenp_pages_read14d: Math.max(0, Math.round(toNumber(rawRow.kenp_pages_read14d))),
      kenp_royalties14d_usd: toNumber(rawRow.kenp_royalties14d_usd),
      currency_code: String(rawRow.currency_code || '').trim() || 'USD',
    };
  }

  function buildSearchTermAggregateKey(row, dimensionKeys) {
    const keys = Array.isArray(dimensionKeys) && dimensionKeys.length > 0
      ? dimensionKeys
      : SEARCH_TERM_DIMENSION_DEFAULTS;
    return keys.map((key) => String(row[key] || '').trim()).join('\u001f');
  }

  function buildSearchTermAggregates(rows, dimensionKeys) {
    const keys = Array.isArray(dimensionKeys) && dimensionKeys.length > 0
      ? dimensionKeys
      : [
        'campaign_name',
        'ad_group_name',
        'search_term',
        'keyword_type',
        'match_type',
        'keyword',
        'targeting',
      ];
    const aggregateByKey = {};
    (rows || []).forEach((rawRow) => {
      const row = normalizeSearchTermRow(rawRow);
      if (!row) {
        return;
      }
      const aggregateKey = buildSearchTermAggregateKey(row, keys);
      if (!aggregateByKey[aggregateKey]) {
        aggregateByKey[aggregateKey] = {
          aggregate_key: aggregateKey,
          campaign_id: row.campaign_id,
          campaign_name: row.campaign_name,
          campaign_status: row.campaign_status,
          ad_group_id: row.ad_group_id,
          ad_group_name: row.ad_group_name,
          search_term: row.search_term,
          keyword_id: row.keyword_id,
          keyword: row.keyword,
          targeting: row.targeting,
          keyword_type: row.keyword_type,
          match_type: row.match_type,
          impressions: 0,
          clicks: 0,
          cost_usd: 0,
          sales14d_usd: 0,
          purchases14d: 0,
          units_sold_clicks14d: 0,
          daily: {},
        };
        keys.forEach((key) => {
          aggregateByKey[aggregateKey][key] = row[key];
        });
      }

      const aggregate = aggregateByKey[aggregateKey];
      aggregate.impressions += row.impressions;
      aggregate.clicks += row.clicks;
      aggregate.cost_usd += row.cost_usd;
      aggregate.sales14d_usd += row.sales14d_usd;
      aggregate.purchases14d += row.purchases14d;
      aggregate.units_sold_clicks14d += row.units_sold_clicks14d;

      if (!aggregate.daily[row.date]) {
        aggregate.daily[row.date] = {
          impressions: 0,
          clicks: 0,
          cost_usd: 0,
          sales14d_usd: 0,
          purchases14d: 0,
          units_sold_clicks14d: 0,
        };
      }
      aggregate.daily[row.date].impressions += row.impressions;
      aggregate.daily[row.date].clicks += row.clicks;
      aggregate.daily[row.date].cost_usd += row.cost_usd;
      aggregate.daily[row.date].sales14d_usd += row.sales14d_usd;
      aggregate.daily[row.date].purchases14d += row.purchases14d;
      aggregate.daily[row.date].units_sold_clicks14d += row.units_sold_clicks14d;
    });

    return Object.values(aggregateByKey).map((aggregate) => {
      const clicks = toNumber(aggregate.clicks);
      const impressions = toNumber(aggregate.impressions);
      const cost = toNumber(aggregate.cost_usd);
      const sales = toNumber(aggregate.sales14d_usd);
      const orders = toNumber(aggregate.purchases14d);
      return {
        ...aggregate,
        ctr: impressions > 0 ? (clicks / impressions) * 100 : 0,
        cpc: clicks > 0 ? cost / clicks : 0,
        cvr: clicks > 0 ? (orders / clicks) * 100 : 0,
        acos: sales > 0 ? (cost / sales) * 100 : 0,
        roas: cost > 0 ? sales / cost : 0,
      };
    });
  }

  function filterSearchTermRows(rows, filters) {
    const filterConfig = filters || {};
    const campaignFilter = String(filterConfig.campaign || 'All').trim();
    const campaignStatusFilter = getEffectiveCampaignStatusFilter(
      filterConfig.campaignStatuses ?? filterConfig.campaignStatus ?? 'All',
      filterConfig.availableCampaignStatuses,
    );
    const keywordTypeFilter = String(filterConfig.keywordType || 'All').trim();
    const matchTypeFilter = String(filterConfig.matchType || 'All').trim();
    const textFilter = String(filterConfig.text || '').trim().toLowerCase();

    return (rows || []).map((rawRow) => normalizeSearchTermRow(rawRow)).filter((row) => {
      if (!row) {
        return false;
      }
      if (campaignFilter !== 'All' && row.campaign_name !== campaignFilter) {
        return false;
      }
      if (campaignStatusFilter !== null && !campaignStatusFilter.includes(row.campaign_status)) {
        return false;
      }
      if (keywordTypeFilter !== 'All' && row.keyword_type !== keywordTypeFilter) {
        return false;
      }
      if (matchTypeFilter !== 'All' && row.match_type !== matchTypeFilter) {
        return false;
      }
      if (!textFilter) {
        return true;
      }
      const haystack = [
        row.search_term,
        row.keyword,
        row.targeting,
        row.campaign_name,
      ].join(' ').toLowerCase();
      return haystack.includes(textFilter);
    });
  }

  function filterSearchTermAggregates(aggregates, filters) {
    const filterConfig = filters || {};
    const campaignFilter = String(filterConfig.campaign || 'All').trim();
    const campaignStatusFilter = getEffectiveCampaignStatusFilter(
      filterConfig.campaignStatuses ?? filterConfig.campaignStatus ?? 'All',
      filterConfig.availableCampaignStatuses,
    );
    const keywordTypeFilter = String(filterConfig.keywordType || 'All').trim();
    const matchTypeFilter = String(filterConfig.matchType || 'All').trim();
    const textFilter = String(filterConfig.text || '').trim().toLowerCase();

    return (aggregates || []).filter((aggregate) => {
      if (campaignFilter !== 'All' && aggregate.campaign_name !== campaignFilter) {
        return false;
      }
      if (campaignStatusFilter !== null
        && !campaignStatusFilter.includes(aggregate.campaign_status)) {
        return false;
      }
      if (keywordTypeFilter !== 'All' && aggregate.keyword_type !== keywordTypeFilter) {
        return false;
      }
      if (matchTypeFilter !== 'All' && aggregate.match_type !== matchTypeFilter) {
        return false;
      }
      if (!textFilter) {
        return true;
      }
      const haystack = [
        aggregate.search_term,
        aggregate.keyword,
        aggregate.targeting,
        aggregate.campaign_name,
      ].join(' ').toLowerCase();
      return haystack.includes(textFilter);
    });
  }

  function normalizePlacementClassification(value) {
    const raw = String(value || '').trim();
    if (!raw) {
      return '';
    }
    const upperValue = raw.toUpperCase();
    if ((upperValue.includes('TOP') && upperValue.includes('SEARCH'))
      || upperValue === 'PLACEMENT_TOP') {
      return 'Top of Search';
    }
    if (upperValue.includes('REST') && upperValue.includes('SEARCH')) {
      return 'Rest of Search';
    }
    if ((upperValue.includes('PRODUCT') && upperValue.includes('PAGE'))
      || upperValue.includes('DETAIL_PAGE')) {
      return 'Product Pages';
    }
    return raw
      .replace(/([a-z])([A-Z])/g, '$1 $2')
      .replace(/[_-]+/g, ' ')
      .split(/\s+/)
      .filter(Boolean)
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ');
  }

  function normalizePlacementRow(rawRow) {
    if (!rawRow || typeof rawRow !== 'object') {
      return null;
    }

    const dateValue = String(rawRow.date || '').trim();
    const campaignName = String(rawRow.campaign_name || '').trim();
    const placementClassification = normalizePlacementClassification(
      rawRow.placement_classification,
    );
    if (!isIsoDateString(dateValue) || !campaignName || !placementClassification) {
      return null;
    }

    return {
      key: String(rawRow.key || '').trim(),
      date: dateValue,
      campaign_id: String(rawRow.campaign_id || '').trim(),
      campaign_name: campaignName,
      campaign_status: normalizeCampaignStatus(rawRow.campaign_status),
      placement_classification: placementClassification,
      impressions: Math.max(0, Math.round(toNumber(rawRow.impressions))),
      clicks: Math.max(0, Math.round(toNumber(rawRow.clicks))),
      cost_usd: toNumber(rawRow.cost_usd),
      sales14d_usd: toNumber(rawRow.sales14d_usd),
      purchases14d: Math.max(0, Math.round(toNumber(rawRow.purchases14d))),
      units_sold_clicks14d: Math.max(0, Math.round(toNumber(rawRow.units_sold_clicks14d))),
      kenp_pages_read14d: Math.max(0, Math.round(toNumber(rawRow.kenp_pages_read14d))),
      kenp_royalties14d_usd: toNumber(rawRow.kenp_royalties14d_usd),
      currency_code: String(rawRow.currency_code || '').trim() || 'USD',
      top_of_search_impression_share: rawRow.top_of_search_impression_share == null
        ? null
        : toNumber(rawRow.top_of_search_impression_share),
    };
  }

  function buildPlacementAggregateKey(row, dimensionKeys) {
    const keys = Array.isArray(dimensionKeys) && dimensionKeys.length > 0
      ? dimensionKeys
      : PLACEMENT_DIMENSION_DEFAULTS;
    return keys.map((key) => String(row[key] || '').trim()).join('\u001f');
  }

  function buildPlacementAggregates(rows, dimensionKeys) {
    const keys = Array.isArray(dimensionKeys) && dimensionKeys.length > 0
      ? dimensionKeys
      : ['placement_classification', 'campaign_name'];
    const aggregateByKey = {};
    (rows || []).forEach((rawRow) => {
      const row = normalizePlacementRow(rawRow);
      if (!row) {
        return;
      }
      const aggregateKey = buildPlacementAggregateKey(row, keys);
      if (!aggregateByKey[aggregateKey]) {
        aggregateByKey[aggregateKey] = {
          aggregate_key: aggregateKey,
          campaign_id: row.campaign_id,
          campaign_name: row.campaign_name,
          campaign_status: row.campaign_status,
          placement_classification: row.placement_classification,
          impressions: 0,
          clicks: 0,
          cost_usd: 0,
          sales14d_usd: 0,
          purchases14d: 0,
          units_sold_clicks14d: 0,
          top_of_search_impression_share_sum: 0,
          top_of_search_impression_share_count: 0,
          daily: {},
        };
        keys.forEach((key) => {
          aggregateByKey[aggregateKey][key] = row[key];
        });
      }

      const aggregate = aggregateByKey[aggregateKey];
      aggregate.impressions += row.impressions;
      aggregate.clicks += row.clicks;
      aggregate.cost_usd += row.cost_usd;
      aggregate.sales14d_usd += row.sales14d_usd;
      aggregate.purchases14d += row.purchases14d;
      aggregate.units_sold_clicks14d += row.units_sold_clicks14d;
      if (row.top_of_search_impression_share != null) {
        aggregate.top_of_search_impression_share_sum += row.top_of_search_impression_share;
        aggregate.top_of_search_impression_share_count += 1;
      }

      if (!aggregate.daily[row.date]) {
        aggregate.daily[row.date] = {
          impressions: 0,
          clicks: 0,
          cost_usd: 0,
          sales14d_usd: 0,
          purchases14d: 0,
          units_sold_clicks14d: 0,
        };
      }
      aggregate.daily[row.date].impressions += row.impressions;
      aggregate.daily[row.date].clicks += row.clicks;
      aggregate.daily[row.date].cost_usd += row.cost_usd;
      aggregate.daily[row.date].sales14d_usd += row.sales14d_usd;
      aggregate.daily[row.date].purchases14d += row.purchases14d;
      aggregate.daily[row.date].units_sold_clicks14d += row.units_sold_clicks14d;
    });

    return Object.values(aggregateByKey).map((aggregate) => {
      const clicks = toNumber(aggregate.clicks);
      const impressions = toNumber(aggregate.impressions);
      const cost = toNumber(aggregate.cost_usd);
      const sales = toNumber(aggregate.sales14d_usd);
      const orders = toNumber(aggregate.purchases14d);
      const impressionShareCount = toNumber(aggregate.top_of_search_impression_share_count);
      return {
        ...aggregate,
        ctr: impressions > 0 ? (clicks / impressions) * 100 : 0,
        cpc: clicks > 0 ? cost / clicks : 0,
        cvr: clicks > 0 ? (orders / clicks) * 100 : 0,
        acos: sales > 0 ? (cost / sales) * 100 : 0,
        roas: cost > 0 ? sales / cost : 0,
        top_of_search_impression_share: impressionShareCount > 0
          ? aggregate.top_of_search_impression_share_sum / impressionShareCount
          : null,
      };
    });
  }

  function filterPlacementRows(rows, filters) {
    const filterConfig = filters || {};
    const campaignFilter = String(filterConfig.campaign || 'All').trim();
    const campaignStatusFilter = getEffectiveCampaignStatusFilter(
      filterConfig.campaignStatuses ?? filterConfig.campaignStatus ?? 'All',
      filterConfig.availableCampaignStatuses,
    );
    const placementFilter = normalizePlacementClassification(filterConfig.placement || 'All');
    const textFilter = String(filterConfig.text || '').trim().toLowerCase();

    return (rows || []).map((rawRow) => normalizePlacementRow(rawRow)).filter((row) => {
      if (!row) {
        return false;
      }
      if (campaignFilter !== 'All' && row.campaign_name !== campaignFilter) {
        return false;
      }
      if (campaignStatusFilter !== null && !campaignStatusFilter.includes(row.campaign_status)) {
        return false;
      }
      if (placementFilter !== 'All' && row.placement_classification !== placementFilter) {
        return false;
      }
      if (!textFilter) {
        return true;
      }
      return row.campaign_name.toLowerCase().includes(textFilter);
    });
  }

  function readAdsStatsPageOptionsFromDocument(doc) {
    const sourceDocument = doc || (typeof document !== 'undefined' ? document : null);
    if (!sourceDocument || typeof sourceDocument.getElementById !== 'function') {
      return null;
    }
    const dataElement = sourceDocument.getElementById(ADS_STATS_PAGE_DATA_ELEMENT_ID);
    if (!dataElement) {
      return null;
    }
    const rawText = String(dataElement.textContent || '').trim();
    if (!rawText) {
      return null;
    }
    try {
      return JSON.parse(rawText);
    } catch (error) {
      if (typeof console !== 'undefined' && typeof console.error === 'function') {
        console.error('Failed to parse ads stats page data', error);
      }
      return null;
    }
  }

  function initAdsStatsPage(options) {
    const config = options || readAdsStatsPageOptionsFromDocument() || {};
    const adsStatsData = config.chartData || {};
    const placementData = config.placementData || {};
    const searchTermData = config.searchTermData || {};
    const reconciledClickDateChartData = config.reconciledClickDateChartData || {};
    const reconciliationDebugCsv = buildReconciliationDebugCsv(config.reconciliationDebugCsv);
    let adsEvents = Array.isArray(config.adsEvents)
      ? config.adsEvents.map((event) => normalizeAdsEvent(event)).filter(Boolean)
      : [];
    let adsEventGroups = groupAdsEventsByDate(adsEvents);
    let renderSelectedView = null;

    function upsertAdsEvent(rawEvent) {
      const event = normalizeAdsEvent(rawEvent);
      if (!event) {
        return false;
      }

      const eventKey = event.key || `${event.date}__${event.title}`;
      const existingIndex = adsEvents.findIndex((item) => {
        const itemKey = item.key || `${item.date}__${item.title}`;
        return itemKey === eventKey;
      });
      if (existingIndex >= 0) {
        adsEvents[existingIndex] = event;
      } else {
        adsEvents.push(event);
      }
      adsEventGroups = groupAdsEventsByDate(adsEvents);
      if (typeof renderSelectedView === 'function') {
        renderSelectedView();
      }
      return true;
    }

    function formatCurrency(value) {
      return `$${Number(value).toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`;
    }

    function formatNumber(value) {
      return Number(value).toLocaleString('en-US', { maximumFractionDigits: 0 });
    }

    function formatPercentage(value) {
      return `${Number(value).toFixed(1)}%`;
    }

    function formatRatio(value) {
      return Number(value).toFixed(2);
    }

    function formatValueByType(formatType, value) {
      if (formatType === 'currency') {
        return formatCurrency(value);
      }
      if (formatType === 'percent') {
        return formatPercentage(value);
      }
      if (formatType === 'ratio') {
        return formatRatio(value);
      }
      return formatNumber(value);
    }

    function formatTickByType(formatType, value) {
      if (formatType === 'currency') {
        return `$${Number(value).toFixed(2)}`;
      }
      if (formatType === 'percent') {
        return `${Number(value).toFixed(1)}%`;
      }
      if (formatType === 'ratio') {
        return Number(value).toFixed(2);
      }
      return value;
    }

    function setCreateEventToggleExpandedState(button, isExpanded) {
      if (!button) {
        return;
      }
      button.setAttribute('aria-expanded', isExpanded ? 'true' : 'false');
    }

    function getStorage() {
      if (typeof window === 'undefined' || !window.localStorage) {
        return null;
      }
      return window.localStorage;
    }

    function loadStoredCampaignStatuses() {
      const storage = getStorage();
      if (!storage || typeof storage.getItem !== 'function') {
        return null;
      }
      try {
        const rawValue = storage.getItem(CAMPAIGN_STATUS_STORAGE_KEY);
        if (!rawValue) {
          return null;
        }
        const parsedValue = JSON.parse(rawValue);
        return Array.isArray(parsedValue) ? normalizeCampaignStatusSelection(parsedValue) || [] : null;
      } catch (_error) {
        return null;
      }
    }

    function persistCampaignStatuses(selectedStatuses) {
      const storage = getStorage();
      if (!storage || typeof storage.setItem !== 'function') {
        return;
      }
      try {
        storage.setItem(
          CAMPAIGN_STATUS_STORAGE_KEY,
          JSON.stringify(normalizeCampaignStatusSelection(selectedStatuses) || []),
        );
      } catch (_error) {
        // Ignore storage failures. The filter still works for the current session.
      }
    }

    function notifyCampaignStatusFilterChanged() {
      if (typeof document.dispatchEvent === 'function' && typeof Event === 'function') {
        document.dispatchEvent(new Event('adsstats:campaign-status-change'));
        return;
      }
      if (typeof document.dispatch === 'function') {
        document.dispatch('adsstats:campaign-status-change');
      }
    }

    function applyModeToggleState(modeToggleButton, modeValue) {
      const selectedMode = modeValue === DAYS_OF_WEEK_MODE ? DAYS_OF_WEEK_MODE : TIMELINE_MODE;
      if (modeToggleButton) {
        const nextMode = selectedMode === TIMELINE_MODE ? DAYS_OF_WEEK_MODE : TIMELINE_MODE;
        modeToggleButton.textContent = selectedMode;
        modeToggleButton.setAttribute(
          'aria-label',
          `Switch chart mode to ${nextMode}`,
        );
        modeToggleButton.setAttribute(
          'title',
          `Switch to ${nextMode}`,
        );
        modeToggleButton.setAttribute(
          'aria-pressed',
          selectedMode === DAYS_OF_WEEK_MODE ? 'true' : 'false',
        );
      }
    }

    function bindModeControls(modeSelectorInput) {
      const modeToggleButton = document.getElementById('adsStatsModeToggleButton');
      if (!modeSelectorInput || modeSelectorInput.dataset.adsStatsModeBound === 'true') {
        return;
      }

      function updateMode(modeValue) {
        const selectedMode = modeValue === DAYS_OF_WEEK_MODE ? DAYS_OF_WEEK_MODE : TIMELINE_MODE;
        const hasChanged = modeSelectorInput.value !== selectedMode;
        modeSelectorInput.value = selectedMode;
        applyModeToggleState(modeToggleButton, selectedMode);
        if (!hasChanged) {
          return;
        }
        if (typeof modeSelectorInput.dispatchEvent === 'function' && typeof Event === 'function') {
          modeSelectorInput.dispatchEvent(new Event('change'));
          return;
        }
        if (typeof modeSelectorInput.dispatch === 'function') {
          modeSelectorInput.dispatch('change');
        }
      }

      modeSelectorInput.dataset.adsStatsModeBound = 'true';
      applyModeToggleState(modeToggleButton, modeSelectorInput.value);
      modeSelectorInput.addEventListener('change', () => {
        applyModeToggleState(modeToggleButton, modeSelectorInput.value);
      });
      if (modeToggleButton) {
        modeToggleButton.addEventListener('click', () => {
          updateMode(
            modeSelectorInput.value === DAYS_OF_WEEK_MODE
              ? TIMELINE_MODE
              : DAYS_OF_WEEK_MODE,
          );
        });
      }
    }

    function bindCreateEventControls() {
      const createEventToggleButton = document.getElementById('adsStatsCreateEventToggleButton');
      const createEventForm = document.getElementById('adsStatsCreateEventForm');
      const createEventDateInput = document.getElementById('adsStatsEventDateInput');
      const createEventTitleInput = document.getElementById('adsStatsEventTitleInput');
      const createEventSubmitButton = document.getElementById('adsStatsEventCreateButton');
      const createEventStatus = document.getElementById('adsStatsCreateEventStatus');
      if (!createEventToggleButton || !createEventForm) {
        return;
      }
      if (createEventToggleButton.dataset.adsStatsCreateEventBound !== 'true') {
        setCreateEventToggleExpandedState(createEventToggleButton, !createEventForm.hidden);
        createEventToggleButton.addEventListener('click', () => {
          const isNowHidden = !createEventForm.hidden;
          createEventForm.hidden = isNowHidden;
          setCreateEventToggleExpandedState(createEventToggleButton, !isNowHidden);
          if (!isNowHidden && createEventDateInput) {
            createEventDateInput.focus();
          }
        });
        createEventToggleButton.dataset.adsStatsCreateEventBound = 'true';
      }

      if (!createEventDateInput
        || !createEventTitleInput
        || !createEventSubmitButton
        || !createEventStatus
        || createEventForm.dataset.adsStatsCreateEventSubmitBound === 'true') {
        return;
      }

      createEventForm.addEventListener('submit', async (event) => {
        event.preventDefault();

        const dateValue = createEventDateInput.value.trim();
        const titleValue = createEventTitleInput.value.trim();
        if (!ISO_DATE_RE.test(dateValue)) {
          createEventStatus.textContent = 'Date must be YYYY-MM-DD';
          return;
        }
        if (!titleValue) {
          createEventStatus.textContent = 'Title is required';
          return;
        }

        createEventSubmitButton.disabled = true;
        createEventStatus.textContent = 'Saving...';
        try {
          const response = await fetch('/admin/ads-stats/events', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              date: dateValue,
              title: titleValue,
            }),
          });
          const data = await response.json();
          if (!response.ok) {
            throw new Error(data.error || 'Failed to save event');
          }
          upsertAdsEvent(data.event || {});
          createEventTitleInput.value = '';
          createEventStatus.textContent = 'Saved';
        } catch (error) {
          createEventStatus.textContent = error && error.message
            ? error.message
            : 'Failed to save event';
        } finally {
          createEventSubmitButton.disabled = false;
        }
      });
      createEventForm.dataset.adsStatsCreateEventSubmitBound = 'true';
    }

    function bindKdpUploadControls() {
      const kdpUploadForm = document.getElementById('kdpUploadForm');
      const kdpFileInput = document.getElementById('kdpFileInput');
      const kdpUploadStatus = document.getElementById('kdpUploadStatus');
      if (!kdpUploadForm || !kdpFileInput || !kdpUploadStatus) {
        return;
      }
      if (kdpUploadForm.dataset.adsStatsKdpUploadBound === 'true') {
        return;
      }

      let kdpUploadInFlight = false;

      async function uploadSelectedKdpFile() {
        if (!kdpFileInput.files
          || kdpFileInput.files.length === 0
          || kdpUploadInFlight) {
          return;
        }
        const formData = new FormData();
        formData.append('file', kdpFileInput.files[0]);
        kdpUploadInFlight = true;
        kdpFileInput.disabled = true;
        kdpUploadStatus.textContent = 'Uploading...';
        try {
          const response = await fetch('/admin/ads-stats/upload-kdp', {
            method: 'POST',
            body: formData,
          });
          const data = await response.json();
          if (!response.ok) {
            throw new Error(data.error || 'Upload failed');
          }
          kdpUploadStatus.textContent = `Saved ${data.days_saved} days`;
          if (window.location && typeof window.location.reload === 'function') {
            window.location.reload();
          }
        } catch (error) {
          kdpUploadStatus.textContent = error && error.message
            ? error.message
            : 'Upload failed';
        } finally {
          kdpUploadInFlight = false;
          kdpFileInput.disabled = false;
          kdpFileInput.value = '';
        }
      }

      kdpUploadForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        await uploadSelectedKdpFile();
      });
      kdpFileInput.addEventListener('change', async () => {
        await uploadSelectedKdpFile();
      });
      kdpUploadForm.dataset.adsStatsKdpUploadBound = 'true';
    }

    function setup() {
      if (typeof window === 'undefined' || !window.document) {
        return;
      }
      const modeSelector = document.getElementById('modeSelector');
      bindModeControls(modeSelector);
      bindCreateEventControls();
      bindKdpUploadControls();

      const chartCtor = window.Chart;
      if (typeof chartCtor !== 'function') {
        return;
      }

      const campaignSelector = document.getElementById('campaignSelector');
      const campaignStatusFilters = document.getElementById('campaignStatusFilters');
      if (!campaignSelector || !campaignStatusFilters || !modeSelector) {
        return;
      }

      let availableCampaignStatuses = [];
      let selectedCampaignStatuses = [];

      function getActiveCampaignStatusFilters() {
        return [...selectedCampaignStatuses];
      }

      function renderCampaignStatusButtons() {
        campaignStatusFilters.innerHTML = '';
        availableCampaignStatuses.forEach((status) => {
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'ads-stats-status-toggle';
          button.setAttribute('data-campaign-status', status);
          button.setAttribute(
            'aria-pressed',
            selectedCampaignStatuses.includes(status) ? 'true' : 'false',
          );
          button.textContent = status;
          button.addEventListener('click', () => {
            if (selectedCampaignStatuses.includes(status)) {
              selectedCampaignStatuses = selectedCampaignStatuses.filter(
                (value) => value !== status,
              );
            } else {
              selectedCampaignStatuses = [...selectedCampaignStatuses, status].sort();
            }
            persistCampaignStatuses(selectedCampaignStatuses);
            renderCampaignStatusButtons();
            notifyCampaignStatusFilterChanged();
            if (typeof renderSelectedView === 'function') {
              renderSelectedView();
            }
          });
          campaignStatusFilters.appendChild(button);
        });
      }

      const charts = {};
      const adsEventsOverlayPlugin = {
        id: 'adsEventsOverlay',
        afterDraw: function (chart) {
          const pluginOptions = chart.options && chart.options.plugins
            ? chart.options.plugins.adsEventsOverlay
            : null;
          if (!pluginOptions || !pluginOptions.enabled) {
            return;
          }

          const chartArea = chart.chartArea;
          const xScale = chart.scales ? chart.scales.x : null;
          if (!chartArea || !xScale) {
            return;
          }

          const events = Array.isArray(pluginOptions.events) ? pluginOptions.events : [];
          const ctx = chart.ctx;
          ctx.save();
          events.forEach((eventGroup) => {
            const pixelX = xScale.getPixelForValue(eventGroup.date);
            if (!Number.isFinite(pixelX) || pixelX < chartArea.left || pixelX > chartArea.right) {
              return;
            }
            ctx.beginPath();
            ctx.moveTo(pixelX, chartArea.top);
            ctx.lineTo(pixelX, chartArea.bottom);
            ctx.lineWidth = 1;
            ctx.strokeStyle = '#8d99ae';
            ctx.stroke();
          });
          ctx.restore();
        },
      };

      function buildDefaultTooltipCallbacks() {
        return {
          title: function (tooltipItems) {
            const firstItem = Array.isArray(tooltipItems) ? tooltipItems[0] : null;
            return firstItem ? String(firstItem.label || '') : '';
          },
          afterTitle: function (tooltipItems) {
            const firstItem = Array.isArray(tooltipItems) ? tooltipItems[0] : null;
            return firstItem ? getAdsEventLinesForLabel(firstItem.label, adsEventGroups) : [];
          },
          label: function (context) {
            const formatType = context.dataset.formatType || 'number';
            return `${context.dataset.label}: ${formatValueByType(
              formatType,
              context.parsed.y,
            )}`;
          },
          afterLabel: function (context) {
            const tooltipLinesByIndex = context.dataset.tooltipLinesByIndex;
            if (!Array.isArray(tooltipLinesByIndex)) {
              return [];
            }
            const lines = tooltipLinesByIndex[context.dataIndex];
            return Array.isArray(lines) ? lines : [];
          },
        };
      }

      function buildAdsEventsOverlayOptions(mode, labels) {
        const hasTimelineLabels = Array.isArray(labels)
          && labels.every((label) => isIsoDateString(label));
        return {
          enabled: mode === TIMELINE_MODE && hasTimelineLabels,
          events: adsEventGroups,
        };
      }

      function createMultiLineChart(canvasId, labels, datasets, scales, mode) {
        const canvas = document.getElementById(canvasId);
        if (!canvas || typeof canvas.getContext !== 'function') {
          return;
        }
        const ctx = canvas.getContext('2d');
        const chartType = getChartTypeForMode(mode);
        const hasVisibleRightAxis = Boolean(
          scales
          && Object.values(scales).some((scale) => {
            return scale && scale.position === 'right' && scale.display !== false;
          }),
        );

        if (charts[canvasId]) {
          charts[canvasId].destroy();
        }

        charts[canvasId] = new chartCtor(ctx, {
          type: chartType,
          data: {
            labels: labels,
            datasets: datasets,
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: {
              padding: {
                right: hasVisibleRightAxis ? 0 : RESERVED_RIGHT_GUTTER_PX,
              },
            },
            scales: scales,
            plugins: {
              tooltip: {
                callbacks: buildDefaultTooltipCallbacks(),
              },
              adsEventsOverlay: buildAdsEventsOverlayOptions(mode, labels),
            },
          },
          plugins: [adsEventsOverlayPlugin],
        });
      }

      function createLineDataset(config, mode) {
        const datasetType = config.type || getChartTypeForMode(mode);
        const isBarDataset = datasetType === 'bar';
        const dataset = {
          type: datasetType,
          label: config.label,
          data: config.data,
          borderColor: config.borderColor,
          backgroundColor: config.backgroundColor
            || (isBarDataset ? `${config.borderColor}cc` : `${config.borderColor}22`),
          fill: isBarDataset ? false : (config.fill || false),
          tension: isBarDataset ? 0 : (config.tension == null ? 0.2 : config.tension),
          pointRadius: isBarDataset ? 0 : (config.pointRadius == null ? 3 : config.pointRadius),
          yAxisID: config.yAxisID || 'y',
          formatType: config.formatType || 'number',
        };
        if (config.borderWidth != null) {
          dataset.borderWidth = config.borderWidth;
        }
        if (config.order != null) {
          dataset.order = config.order;
        }
        if (config.tooltipLinesByIndex != null) {
          dataset.tooltipLinesByIndex = config.tooltipLinesByIndex;
        }
        if (isBarDataset) {
          dataset.borderRadius = config.borderRadius == null ? 4 : config.borderRadius;
          dataset.maxBarThickness = config.maxBarThickness == null ? 36 : config.maxBarThickness;
        }
        return dataset;
      }

      function createThresholdDataset(labels, mode) {
        return createLineDataset({
          label: 'POAS Threshold (1.0)',
          data: labels.map(() => 1.0),
          type: mode === DAYS_OF_WEEK_MODE ? 'line' : undefined,
          borderColor: '#c62828',
          fill: false,
          tension: 0,
          pointRadius: 0,
          borderWidth: 1,
          yAxisID: 'y',
          formatType: 'ratio',
        }, mode);
      }

      function buildSingleAxis(formatType, suggestedMax) {
        const axis = {
          beginAtZero: true,
          ticks: {
            callback: function (value) {
              return formatTickByType(formatType, value);
            },
          },
        };
        if (suggestedMax != null) {
          axis.suggestedMax = suggestedMax;
        }
        return { y: axis };
      }

      function buildDualAxis(leftFormatType, rightFormatType) {
        return {
          y: {
            beginAtZero: true,
            position: 'left',
            ticks: {
              callback: function (value) {
                return formatTickByType(leftFormatType, value);
              },
            },
          },
          y1: {
            beginAtZero: true,
            position: 'right',
            afterFit: function (scale) {
              reserveScaleWidth(scale, RESERVED_RIGHT_GUTTER_PX);
            },
            grid: {
              drawOnChartArea: false,
            },
            ticks: {
              callback: function (value) {
                return formatTickByType(rightFormatType, value);
              },
            },
          },
        };
      }

      function renderReconciledProfitChart(series, mode) {
        const datasets = [
          createLineDataset({
            label: 'Cost',
            data: series.cost,
            borderColor: '#c62828',
            formatType: 'currency',
          }, mode),
          createLineDataset({
            label: 'Profit Before Ads (ads)',
            data: series.ads_profit_before_ads_usd,
            borderColor: '#ef6c00',
            formatType: 'currency',
            tooltipLinesByIndex: series.ads_profit_tooltip_lines,
          }, mode),
          createLineDataset({
            label: 'Gross Profit',
            data: series.gross_profit_usd,
            borderColor: '#6a1b9a',
            fill: 'origin',
            formatType: 'currency',
          }, mode),
        ];
        if (!series.is_ads_only_campaign_series) {
          datasets.splice(2, 0, createLineDataset({
            label: 'Profit Before Ads (reconciled)',
            data: series.reconciled_profit_before_ads_usd,
            borderColor: '#2e7d32',
            formatType: 'currency',
            tooltipLinesByIndex: series.profit_before_ads_reconciled_tooltip_lines,
          }, mode));
        }
        createMultiLineChart(
          'reconciledProfitTimelineChart',
          series.labels,
          datasets,
          buildSingleAxis('currency'),
          mode,
        );
      }

      function renderPoasChart(canvasId, series, poasLabel, poasColor, tpoasLabel, tpoasColor, mode) {
        const includeSecondaryLine = Boolean(tpoasLabel) && !series.is_ads_only_campaign_series;
        const ratioSeries = includeSecondaryLine ? [...series.poas, ...series.tpoas] : [...series.poas];
        const suggestedMax = Math.max(1.1, ...ratioSeries, 1.0);
        const datasets = [
          createLineDataset({
            label: poasLabel,
            data: series.poas,
            borderColor: poasColor,
            formatType: 'ratio',
          }, mode),
        ];
        if (includeSecondaryLine) {
          datasets.push(createLineDataset({
            label: tpoasLabel,
            data: series.tpoas,
            borderColor: tpoasColor,
            formatType: 'ratio',
            tooltipLinesByIndex: series.profit_before_ads_reconciled_tooltip_lines,
          }, mode));
        }
        datasets.push(createThresholdDataset(series.labels, mode));
        createMultiLineChart(
          canvasId,
          series.labels,
          datasets,
          buildSingleAxis('ratio', suggestedMax),
          mode,
        );
      }

      function renderCpcAndConversionRateChart(series, mode) {
        createMultiLineChart(
          'cpcAndConversionRateChart',
          series.labels,
          [
            createLineDataset({
              label: 'CPC',
              data: series.cpc,
              borderColor: '#d81b60',
              yAxisID: 'y',
              formatType: 'currency',
            }, mode),
            createLineDataset({
              label: 'Conversion Rate',
              data: series.conversion_rate,
              borderColor: '#00838f',
              yAxisID: 'y1',
              formatType: 'percent',
            }, mode),
          ],
          buildDualAxis('currency', 'percent'),
          mode,
        );
      }

      function renderCtrChart(series, mode) {
        createMultiLineChart(
          'ctrChart',
          series.labels,
          [
            createLineDataset({
              label: 'CTR',
              data: series.ctr,
              borderColor: '#ef6c00',
              formatType: 'percent',
            }, mode),
          ],
          buildSingleAxis('percent'),
          mode,
        );
      }

      function renderImpressionsAndClicksChart(series, mode) {
        createMultiLineChart(
          'impressionsAndClicksChart',
          series.labels,
          [
            createLineDataset({
              label: 'Impressions',
              data: series.impressions,
              borderColor: '#2e7d32',
              yAxisID: 'y',
              formatType: 'number',
            }, mode),
            createLineDataset({
              label: 'Clicks',
              data: series.clicks,
              borderColor: '#1565c0',
              yAxisID: 'y1',
              formatType: 'number',
            }, mode),
          ],
          buildDualAxis('number', 'number'),
          mode,
        );
      }

      function renderAdsProfitBreakdownChart(series, mode) {
        const datasets = [
          createLineDataset({
            label: 'Profit Before Ads (ads)',
            data: series.ads_profit_before_ads_usd,
            borderColor: COLOR_ADS,
            formatType: 'currency',
            tooltipLinesByIndex: series.ads_profit_tooltip_lines,
          }, mode),
          createLineDataset({
            label: 'Matched Ads Profit',
            data: series.matched_ads_profit_before_ads_usd,
            borderColor: COLOR_MATCHED,
            formatType: 'currency',
            tooltipLinesByIndex: series.matched_ads_profit_tooltip_lines,
          }, mode),
          createLineDataset({
            label: 'Unmatched Ad Profit',
            data: series.unmatched_pre_ad_profit_usd,
            borderColor: COLOR_UNMATCHED,
            formatType: 'currency',
          }, mode),
          createLineDataset({
            label: 'Reconciled Profit',
            data: series.reconciled_matched_profit_before_ads_usd,
            borderColor: COLOR_RECONCILED,
            formatType: 'currency',
            tooltipLinesByIndex: series.reconciled_matched_profit_tooltip_lines,
          }, mode),
        ];

        createMultiLineChart(
          'adsProfitBreakdownChart',
          series.labels,
          datasets,
          buildSingleAxis('currency'),
          mode,
        );
      }

      function toSeriesValues(labels, valuesByIndex) {
        const sourceValues = arrayOrEmpty(valuesByIndex);
        return labels.map((_, index) => toNumber(sourceValues[index]));
      }

      function toSeriesTooltipLines(labels, tooltipLinesByIndex) {
        const sourceLines = arrayOrEmpty(tooltipLinesByIndex);
        return labels.map((_, index) => arrayOrEmpty(sourceLines[index]));
      }

      function renderCountBreakdownChart(canvasId, labels, lineConfigs, mode, scales) {
        const datasets = lineConfigs.map((lineConfig) => {
          const datasetConfig = {
            label: lineConfig.label,
            data: lineConfig.data,
            borderColor: lineConfig.borderColor,
            yAxisID: lineConfig.yAxisID,
            formatType: 'number',
            tooltipLinesByIndex: lineConfig.tooltipLinesByIndex,
          };
          if (lineConfig.order != null) {
            datasetConfig.order = lineConfig.order;
          }
          return createLineDataset(datasetConfig, mode);
        });
        createMultiLineChart(
          canvasId,
          labels,
          datasets,
          scales || buildSingleAxis('number'),
          mode,
        );
      }

      function renderSalesBreakdownChart(stats, reconciledStats, mode) {
        const labels = Array.isArray(stats.labels) ? stats.labels : [];
        renderCountBreakdownChart(
          'salesBreakdownChart',
          labels,
          [
            {
              label: 'Ads Sales (ads)',
              data: toSeriesValues(labels, stats.units_sold),
              borderColor: COLOR_ADS,
              tooltipLinesByIndex: toSeriesTooltipLines(
                labels,
                reconciledStats.ads_sales_tooltip_lines,
              ),
            },
            {
              label: 'Matched Ads Sales',
              data: toSeriesValues(labels, reconciledStats.matched_ads_sales_count),
              borderColor: COLOR_MATCHED,
              tooltipLinesByIndex: toSeriesTooltipLines(
                labels,
                reconciledStats.matched_ads_sales_tooltip_lines,
              ),
            },
            {
              label: 'Unmatched Ads Sales',
              data: toSeriesValues(labels, reconciledStats.unmatched_ads_sales_count),
              borderColor: COLOR_UNMATCHED,
              order: -10,
              tooltipLinesByIndex: toSeriesTooltipLines(
                labels,
                reconciledStats.unmatched_ads_sales_tooltip_lines,
              ),
            },
            {
              label: 'Reconciled Sales',
              data: toSeriesValues(labels, reconciledStats.reconciled_sales_count),
              borderColor: COLOR_RECONCILED,
              tooltipLinesByIndex: toSeriesTooltipLines(
                labels,
                reconciledStats.reconciled_sales_tooltip_lines,
              ),
            },
            {
              label: 'Free Downloads',
              data: toSeriesValues(labels, stats.free_units_downloaded),
              borderColor: COLOR_FREE_DOWNLOADS,
              yAxisID: 'y1',
            },
          ],
          mode,
          buildDualAxis('number', 'number'),
        );
      }

      function renderKenpBreakdownChart(stats, reconciledStats, mode) {
        const labels = Array.isArray(stats.labels) ? stats.labels : [];
        renderCountBreakdownChart(
          'kenpBreakdownChart',
          labels,
          [
            {
              label: 'Ads KENP Pages (ads)',
              data: toSeriesValues(labels, reconciledStats.ads_kenp_pages_count),
              borderColor: COLOR_ADS,
              tooltipLinesByIndex: toSeriesTooltipLines(
                labels,
                reconciledStats.ads_kenp_pages_tooltip_lines,
              ),
            },
            {
              label: 'Matched KENP Pages',
              data: toSeriesValues(labels, reconciledStats.matched_ads_kenp_pages_count),
              borderColor: COLOR_MATCHED,
              tooltipLinesByIndex: toSeriesTooltipLines(
                labels,
                reconciledStats.matched_ads_kenp_pages_tooltip_lines,
              ),
            },
            {
              label: 'Unmatched KENP Pages',
              data: toSeriesValues(labels, reconciledStats.unmatched_ads_kenp_pages_count),
              borderColor: COLOR_UNMATCHED,
              order: -10,
              tooltipLinesByIndex: toSeriesTooltipLines(
                labels,
                reconciledStats.unmatched_ads_kenp_pages_tooltip_lines,
              ),
            },
            {
              label: 'Reconciled KENP Pages',
              data: toSeriesValues(labels, reconciledStats.reconciled_kenp_pages_count),
              borderColor: COLOR_RECONCILED,
              tooltipLinesByIndex: toSeriesTooltipLines(
                labels,
                reconciledStats.reconciled_kenp_pages_tooltip_lines,
              ),
            },
          ],
          mode,
        );
      }

      function calculateAndRender(
        campaignName, campaignStatuses, mode, availableStatuses,
      ) {
        const stats = buildChartStats(
          adsStatsData,
          campaignName,
          campaignStatuses,
          mode,
          availableStatuses,
        );
        const reconciledStats = buildReconciledChartStats(
          adsStatsData,
          campaignName,
          campaignStatuses,
          mode,
          reconciledClickDateChartData,
          availableStatuses,
        );

        renderReconciledProfitChart(reconciledStats, mode);
        renderPoasChart(
          'reconciledPoasTimelineChart',
          reconciledStats,
          'POAS',
          '#ef6c00',
          'TPOAS',
          '#2e7d32',
          mode,
        );
        renderCpcAndConversionRateChart(stats, mode);
        renderCtrChart(stats, mode);
        renderImpressionsAndClicksChart(stats, mode);
        renderAdsProfitBreakdownChart(reconciledStats, mode);
        renderSalesBreakdownChart(stats, reconciledStats, mode);
        renderKenpBreakdownChart(stats, reconciledStats, mode);

        const statImpressions = document.getElementById('stat-impressions');
        const statClicks = document.getElementById('stat-clicks');
        const statCost = document.getElementById('stat-cost');
        const statProfitBeforeAdsAds = document.getElementById('stat-profit-before-ads-ads');
        const statProfitBeforeAdsReconciled = document.getElementById(
          'stat-profit-before-ads-reconciled',
        );
        const statGrossProfit = document.getElementById('stat-gross-profit');
        const statCtr = document.getElementById('stat-ctr');
        const statCpc = document.getElementById('stat-cpc');
        const statConversionRate = document.getElementById('stat-conversion-rate');

        if (statImpressions) {
          statImpressions.textContent = formatNumber(stats.totals.impressions);
        }
        if (statClicks) {
          statClicks.textContent = formatNumber(stats.totals.clicks);
        }
        if (statCost) {
          statCost.textContent = formatCurrency(stats.totals.cost);
        }
        if (statProfitBeforeAdsAds) {
          statProfitBeforeAdsAds.textContent = formatCurrency(
            toNumber(reconciledStats.totals && reconciledStats.totals.ads_profit_before_ads_usd),
          );
        }
        if (statProfitBeforeAdsReconciled) {
          statProfitBeforeAdsReconciled.textContent = formatCurrency(
            toNumber(reconciledStats.totals
              && reconciledStats.totals.reconciled_profit_before_ads_usd),
          );
        }
        if (statGrossProfit) {
          statGrossProfit.textContent = formatCurrency(
            toNumber(reconciledStats.totals && reconciledStats.totals.gross_profit_usd),
          );
        }

        const totalCtr = stats.totals.impressions > 0
          ? (stats.totals.clicks / stats.totals.impressions) * 100
          : 0;
        const totalCpc = stats.totals.clicks > 0 ? stats.totals.cost / stats.totals.clicks : 0;
        const totalCr = stats.totals.clicks > 0
          ? (stats.totals.units_sold / stats.totals.clicks) * 100
          : 0;
        if (statCtr) {
          statCtr.textContent = formatPercentage(totalCtr);
        }
        if (statCpc) {
          statCpc.textContent = formatCurrency(totalCpc);
        }
        if (statConversionRate) {
          statConversionRate.textContent = formatPercentage(totalCr);
        }
      }

      function appendUniqueOptions(selectEl, values) {
        const uniqueValues = Array.from(new Set((values || []).filter(Boolean))).sort();
        uniqueValues.forEach((value) => {
          const option = document.createElement('option');
          option.value = value;
          option.textContent = value;
          selectEl.appendChild(option);
        });
      }

      function initGroupedInsights(config) {
        const textFilterEl = document.getElementById(config.textFilterId);
        const dimensionChipsEl = document.getElementById(config.dimensionChipsId);
        const tableHeadEl = document.getElementById(config.tableHeadId);
        const tableBodyEl = document.getElementById(config.tableBodyId);
        const emptyStateEl = document.getElementById(config.emptyStateId);
        const trendCanvasEl = document.getElementById(config.trendCanvasId);
        const filterSelects = config.filterSelects.map((filterConfig) => ({
          ...filterConfig,
          element: document.getElementById(filterConfig.elementId),
        }));
        const summaryElements = {
          rows: document.getElementById(config.summaryElementIds.rows),
          clicks: document.getElementById(config.summaryElementIds.clicks),
          cost: document.getElementById(config.summaryElementIds.cost),
          sales: document.getElementById(config.summaryElementIds.sales),
          acos: document.getElementById(config.summaryElementIds.acos),
          roas: document.getElementById(config.summaryElementIds.roas),
        };
        if (!textFilterEl || !dimensionChipsEl || !tableHeadEl || !tableBodyEl || !trendCanvasEl
          || filterSelects.some((filterConfig) => !filterConfig.element)) {
          return;
        }

        const normalizedRows = (Array.isArray(config.data.rows) ? config.data.rows : [])
          .map((rawRow) => config.normalizeRow(rawRow))
          .filter(Boolean);
        const trendLabels = Array.isArray(config.data.labels)
          ? config.data.labels
          : Array.from(new Set(normalizedRows.map((item) => item.date))).sort();
        const chipButtons = Array.from(
          dimensionChipsEl.querySelectorAll('[data-dimension-key]'),
        );
        const activeDimensionKeys = new Set(
          chipButtons.filter((chip) => chip.getAttribute('aria-pressed') === 'true')
            .map((chip) => String(chip.dataset.dimensionKey || ''))
            .filter(Boolean),
        );
        if (activeDimensionKeys.size === 0) {
          config.defaultDimensions.forEach((key) => activeDimensionKeys.add(key));
        }

        let selectedAggregateKey = '';
        let sortField = config.defaultSortField || 'sales14d_usd';
        let sortDirection = config.defaultSortDirection || 'desc';

        function syncChipStates() {
          chipButtons.forEach((chip) => {
            const dimensionKey = String(chip.dataset.dimensionKey || '');
            chip.setAttribute(
              'aria-pressed',
              activeDimensionKeys.has(dimensionKey) ? 'true' : 'false',
            );
          });
        }

        filterSelects.forEach((filterConfig) => {
          if (filterConfig.populateOptions !== false) {
            appendUniqueOptions(
              filterConfig.element,
              normalizedRows.map((row) => filterConfig.rowValue(row)),
            );
          }
        });

        function currentFilters() {
          const filters = { text: textFilterEl.value || '' };
          filterSelects.forEach((filterConfig) => {
            filters[filterConfig.filterKey] = filterConfig.element.value || 'All';
          });
          if (typeof config.getExternalFilters === 'function') {
            Object.assign(filters, config.getExternalFilters());
          }
          return filters;
        }

        function sortAggregates(rows) {
          const nextRows = [...rows];
          const multiplier = sortDirection === 'asc' ? 1 : -1;
          nextRows.sort((left, right) => {
            const leftValue = left[sortField];
            const rightValue = right[sortField];
            const leftNumber = Number(leftValue);
            const rightNumber = Number(rightValue);
            if (Number.isFinite(leftNumber) && Number.isFinite(rightNumber)) {
              return (leftNumber - rightNumber) * multiplier;
            }
            return String(leftValue || '').localeCompare(String(rightValue || '')) * multiplier;
          });
          return nextRows;
        }

        function getVisibleColumns() {
          const dimensionColumns = config.dimensionColumns.filter(
            (column) => activeDimensionKeys.has(column.key),
          );
          return [
            ...dimensionColumns,
            ...config.metricColumns,
            ...config.extraColumnsBuilder(activeDimensionKeys),
          ];
        }

        function renderTableHead(columns) {
          tableHeadEl.innerHTML = `<tr>${
            columns.map((column) => {
              const isSortable = column.sortable !== false;
              const sortIndicator = isSortable && sortField === column.key
                ? (sortDirection === 'asc' ? ' ?' : ' ?')
                : '';
              const sortFieldAttr = isSortable
                ? ` ${config.sortFieldAttribute}="${escapeHtml(column.key)}"`
                : '';
              return (
                `<th><button class="${config.sortButtonClassName}" type="button"${sortFieldAttr}>`
                + `${escapeHtml(column.label)}${sortIndicator}</button></th>`
              );
            }).join('')
          }</tr>`;
        }

        function formatDimensionValue(value) {
          const normalized = String(value || '').trim();
          return normalized || '-';
        }

        function formatColumnValue(column, row) {
          const value = row[column.key];
          if (column.format === 'currency') {
            return formatCurrency(value);
          }
          if (column.format === 'percent') {
            return value == null ? '-' : formatPercentage(value);
          }
          if (column.format === 'ratio') {
            return formatRatio(value);
          }
          if (column.format === 'number') {
            return formatNumber(value);
          }
          return formatDimensionValue(value);
        }

        function formatColumnHtml(column, row) {
          const formattedValue = formatColumnValue(column, row);
          const amazonLinkColumnKeys = Array.isArray(config.amazonLinkColumnKeys)
            ? config.amazonLinkColumnKeys
            : [];
          const rawValue = row[column.key];
          if (column.format || !amazonLinkColumnKeys.includes(column.key)
            || !isAmazonAsinGuessTerm(rawValue)) {
            return escapeHtml(formattedValue);
          }
          return (
            `<a href="${escapeHtml(buildAmazonDpUrl(rawValue))}" `
            + 'target="_blank" rel="noopener noreferrer">'
            + `${escapeHtml(formattedValue)}</a>`
          );
        }

        function updateSummary(rows) {
          const totals = rows.reduce((acc, row) => {
            acc.rows += 1;
            acc.clicks += toNumber(row.clicks);
            acc.cost += toNumber(row.cost_usd);
            acc.sales += toNumber(row.sales14d_usd);
            return acc;
          }, {
            rows: 0,
            clicks: 0,
            cost: 0,
            sales: 0,
          });
          const acos = totals.sales > 0 ? (totals.cost / totals.sales) * 100 : 0;
          const roas = totals.cost > 0 ? totals.sales / totals.cost : 0;
          if (summaryElements.rows) {
            summaryElements.rows.textContent = formatNumber(totals.rows);
          }
          if (summaryElements.clicks) {
            summaryElements.clicks.textContent = formatNumber(totals.clicks);
          }
          if (summaryElements.cost) {
            summaryElements.cost.textContent = formatCurrency(totals.cost);
          }
          if (summaryElements.sales) {
            summaryElements.sales.textContent = formatCurrency(totals.sales);
          }
          if (summaryElements.acos) {
            summaryElements.acos.textContent = formatPercentage(acos);
          }
          if (summaryElements.roas) {
            summaryElements.roas.textContent = formatRatio(roas);
          }
        }

        function trendSeriesForAggregate(aggregate) {
          return trendLabels.map((label) => {
            const day = aggregate && aggregate.daily ? aggregate.daily[label] : null;
            return {
              cost_usd: day ? toNumber(day.cost_usd) : 0,
              sales14d_usd: day ? toNumber(day.sales14d_usd) : 0,
              clicks: day ? toNumber(day.clicks) : 0,
            };
          });
        }

        function renderTrendForSelectedAggregate(visibleRows) {
          const selected = visibleRows.find((row) => row.aggregate_key === selectedAggregateKey)
            || visibleRows[0];
          if (!selected) {
            if (charts[config.chartStateKey]) {
              charts[config.chartStateKey].destroy();
              delete charts[config.chartStateKey];
            }
            return;
          }
          selectedAggregateKey = selected.aggregate_key;
          const series = trendSeriesForAggregate(selected);
          const ctx = trendCanvasEl.getContext('2d');
          if (!ctx) {
            return;
          }
          if (charts[config.chartStateKey]) {
            charts[config.chartStateKey].destroy();
          }
          charts[config.chartStateKey] = new chartCtor(ctx, {
            type: 'line',
            data: {
              labels: trendLabels,
              datasets: [
                {
                  label: 'Cost',
                  data: series.map((item) => item.cost_usd),
                  borderColor: '#c62828',
                  backgroundColor: '#c6282822',
                  yAxisID: 'y',
                  tension: 0.2,
                  formatType: 'currency',
                },
                {
                  label: 'Sales',
                  data: series.map((item) => item.sales14d_usd),
                  borderColor: '#2e7d32',
                  backgroundColor: '#2e7d3222',
                  yAxisID: 'y',
                  tension: 0.2,
                  formatType: 'currency',
                },
                {
                  label: 'Clicks',
                  data: series.map((item) => item.clicks),
                  borderColor: '#1565c0',
                  backgroundColor: '#1565c022',
                  yAxisID: 'y1',
                  tension: 0.2,
                  formatType: 'number',
                },
              ],
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              scales: buildDualAxis('currency', 'number'),
              plugins: {
                tooltip: {
                  callbacks: buildDefaultTooltipCallbacks(),
                },
                adsEventsOverlay: buildAdsEventsOverlayOptions(TIMELINE_MODE, trendLabels),
              },
            },
            plugins: [adsEventsOverlayPlugin],
          });
        }

        function renderTable() {
          const filteredRows = config.filterRows(normalizedRows, currentFilters());
          const aggregates = config.buildAggregates(
            filteredRows,
            Array.from(activeDimensionKeys),
          );
          const visibleColumns = getVisibleColumns();
          if (!visibleColumns.some((column) => column.key === sortField)) {
            sortField = config.defaultSortField || 'sales14d_usd';
            sortDirection = config.defaultSortDirection || 'desc';
          }
          const sortedRows = sortAggregates(aggregates);
          updateSummary(sortedRows);
          renderTableHead(visibleColumns);

          tableBodyEl.innerHTML = '';
          if (emptyStateEl) {
            emptyStateEl.hidden = sortedRows.length > 0;
          }

          if (selectedAggregateKey
            && !sortedRows.some((row) => row.aggregate_key === selectedAggregateKey)) {
            selectedAggregateKey = '';
          }

          sortedRows.slice(0, 200).forEach((row) => {
            const tr = document.createElement('tr');
            tr.className = row.aggregate_key === selectedAggregateKey
              ? `${config.rowClassName} ${config.selectedRowClassName}`
              : config.rowClassName;
            tr.tabIndex = 0;
            tr.dataset.aggregateKey = row.aggregate_key;
            tr.innerHTML = visibleColumns.map((column) => {
              return `<td>${formatColumnHtml(column, row)}</td>`;
            }).join('');
            tableBodyEl.appendChild(tr);
          });

          renderTrendForSelectedAggregate(sortedRows);
        }

        tableBodyEl.addEventListener('click', (event) => {
          const target = event.target instanceof Element ? event.target : null;
          const row = target
            ? target.closest(`.${config.rowClassName}[data-aggregate-key]`)
            : null;
          if (!row) {
            return;
          }
          if (typeof window !== 'undefined' && window.getSelection) {
            const selection = window.getSelection();
            if (selection && String(selection.toString() || '').trim()) {
              return;
            }
          }
          selectedAggregateKey = row.dataset.aggregateKey || '';
          renderTable();
        });

        tableBodyEl.addEventListener('keydown', (event) => {
          const target = event.target instanceof Element ? event.target : null;
          const row = target
            ? target.closest(`.${config.rowClassName}[data-aggregate-key]`)
            : null;
          if (!row) {
            return;
          }
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            selectedAggregateKey = row.dataset.aggregateKey || '';
            renderTable();
          }
        });

        filterSelects.forEach((filterConfig) => {
          filterConfig.element.addEventListener('change', renderTable);
        });
        textFilterEl.addEventListener('input', renderTable);
        if (typeof config.getExternalFilters === 'function') {
          document.addEventListener('adsstats:campaign-status-change', renderTable);
        }

        chipButtons.forEach((chipButton) => {
          chipButton.addEventListener('click', () => {
            const dimensionKey = String(chipButton.dataset.dimensionKey || '');
            if (!dimensionKey) {
              return;
            }
            if (activeDimensionKeys.has(dimensionKey)) {
              if (activeDimensionKeys.size === 1) {
                return;
              }
              activeDimensionKeys.delete(dimensionKey);
            } else {
              activeDimensionKeys.add(dimensionKey);
            }
            syncChipStates();
            selectedAggregateKey = '';
            renderTable();
          });
        });

        tableHeadEl.addEventListener('click', (event) => {
          const target = event.target instanceof Element ? event.target : null;
          const button = target ? target.closest(`[${config.sortFieldAttribute}]`) : null;
          if (!button) {
            return;
          }
          const requestedField = String(button.getAttribute(config.sortFieldAttribute) || '');
          if (!requestedField) {
            return;
          }
          if (sortField === requestedField) {
            sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
          } else {
            sortField = requestedField;
            sortDirection = config.dimensionColumns.some(
              (column) => column.key === requestedField,
            ) ? 'asc' : 'desc';
          }
          renderTable();
        });

        syncChipStates();
        renderTable();
      }

      function initSearchTermInsights() {
        initGroupedInsights({
          data: searchTermData,
          normalizeRow: normalizeSearchTermRow,
          filterRows: filterSearchTermRows,
          buildAggregates: buildSearchTermAggregates,
          dimensionColumns: SEARCH_TERM_DIMENSION_COLUMNS,
          defaultDimensions: SEARCH_TERM_DIMENSION_DEFAULTS,
          metricColumns: SEARCH_TERM_METRIC_COLUMNS,
          filterSelects: [
            {
              elementId: 'searchTermCampaignSelector',
              filterKey: 'campaign',
              rowValue: (row) => row.campaign_name,
            },
            {
              elementId: 'searchTermKeywordTypeSelector',
              filterKey: 'keywordType',
              rowValue: (row) => row.keyword_type,
            },
            {
              elementId: 'searchTermMatchTypeSelector',
              filterKey: 'matchType',
              rowValue: (row) => row.match_type,
            },
          ],
          textFilterId: 'searchTermTextFilter',
          dimensionChipsId: 'searchTermDimensionChips',
          tableHeadId: 'searchTermInsightsTableHead',
          tableBodyId: 'searchTermInsightsTableBody',
          emptyStateId: 'searchTermInsightsEmptyState',
          trendCanvasId: 'searchTermTrendChart',
          chartStateKey: 'searchTermTrendChart',
          rowClassName: 'search-term-row',
          selectedRowClassName: 'search-term-row--selected',
          sortButtonClassName: 'search-term-sort-button',
          sortFieldAttribute: 'data-search-term-sort-field',
          summaryElementIds: {
            rows: 'searchTermSummaryRows',
            clicks: 'searchTermSummaryClicks',
            cost: 'searchTermSummaryCost',
            sales: 'searchTermSummarySales',
            acos: 'searchTermSummaryAcos',
            roas: 'searchTermSummaryRoas',
          },
          amazonLinkColumnKeys: ['search_term', 'keyword', 'targeting'],
          extraColumnsBuilder: () => [],
          defaultSortField: 'sales14d_usd',
          defaultSortDirection: 'desc',
          getExternalFilters: () => ({
            campaignStatuses: getActiveCampaignStatusFilters(),
            availableCampaignStatuses: availableCampaignStatuses,
          }),
        });
      }

      function initPlacementInsights() {
        initGroupedInsights({
          data: placementData,
          normalizeRow: normalizePlacementRow,
          filterRows: filterPlacementRows,
          buildAggregates: buildPlacementAggregates,
          dimensionColumns: PLACEMENT_DIMENSION_COLUMNS,
          defaultDimensions: PLACEMENT_DIMENSION_DEFAULTS,
          metricColumns: PLACEMENT_METRIC_COLUMNS,
          filterSelects: [
            {
              elementId: 'placementCampaignSelector',
              filterKey: 'campaign',
              rowValue: (row) => row.campaign_name,
            },
            {
              elementId: 'placementPlacementSelector',
              filterKey: 'placement',
              rowValue: (row) => row.placement_classification,
            },
          ],
          textFilterId: 'placementTextFilter',
          dimensionChipsId: 'placementDimensionChips',
          tableHeadId: 'placementInsightsTableHead',
          tableBodyId: 'placementInsightsTableBody',
          emptyStateId: 'placementInsightsEmptyState',
          trendCanvasId: 'placementTrendChart',
          chartStateKey: 'placementTrendChart',
          rowClassName: 'placement-row',
          selectedRowClassName: 'placement-row--selected',
          sortButtonClassName: 'placement-sort-button',
          sortFieldAttribute: 'data-placement-sort-field',
          summaryElementIds: {
            rows: 'placementSummaryRows',
            clicks: 'placementSummaryClicks',
            cost: 'placementSummaryCost',
            sales: 'placementSummarySales',
            acos: 'placementSummaryAcos',
            roas: 'placementSummaryRoas',
          },
          extraColumnsBuilder: (activeDimensionKeys) => (
            activeDimensionKeys.has('campaign_name')
              ? [{
                key: 'top_of_search_impression_share',
                label: 'Top of Search IS',
                format: 'percent',
                sortable: false,
              }]
              : []
          ),
          defaultSortField: 'sales14d_usd',
          defaultSortDirection: 'desc',
          getExternalFilters: () => ({
            campaignStatuses: getActiveCampaignStatusFilters(),
            availableCampaignStatuses: availableCampaignStatuses,
          }),
        });
      }
      const campaignNames = new Set();
      const campaignStatuses = new Set();
      Object.values(adsStatsData.daily_campaigns || {}).forEach((campaignList) => {
        if (!Array.isArray(campaignList)) {
          return;
        }
        campaignList.forEach((campaign) => {
          if (campaign && campaign.campaign_name) {
            campaignNames.add(campaign.campaign_name);
          }
          if (campaign) {
            campaignStatuses.add(normalizeCampaignStatus(campaign.campaign_status));
          }
        });
      });
      (Array.isArray(searchTermData.rows) ? searchTermData.rows : []).forEach((row) => {
        if (row) {
          campaignStatuses.add(normalizeCampaignStatus(row.campaign_status));
        }
      });
      (Array.isArray(placementData.rows) ? placementData.rows : []).forEach((row) => {
        if (row) {
          campaignStatuses.add(normalizeCampaignStatus(row.campaign_status));
        }
      });

      Array.from(campaignNames).sort().forEach((name) => {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = name;
        campaignSelector.appendChild(option);
      });
      availableCampaignStatuses = Array.from(campaignStatuses)
        .filter((status) => status && status !== 'All')
        .sort();
      const storedCampaignStatuses = loadStoredCampaignStatuses();
      selectedCampaignStatuses = storedCampaignStatuses === null
        ? [...availableCampaignStatuses]
        : availableCampaignStatuses.filter((status) => storedCampaignStatuses.includes(status));
      renderCampaignStatusButtons();

      renderSelectedView = () => {
        calculateAndRender(
          campaignSelector.value,
          getActiveCampaignStatusFilters(),
          modeSelector.value,
          availableCampaignStatuses,
        );
      };

      campaignSelector.addEventListener('change', renderSelectedView);
      modeSelector.addEventListener('change', renderSelectedView);
      renderSelectedView();
      initPlacementInsights();
      initSearchTermInsights();

      document.addEventListener('click', async (event) => {
        const target = event.target instanceof Element ? event.target : null;
        const btn = target && target.closest ? target.closest('.chart-data-button') : null;
        if (!btn) {
          return;
        }

        let popup = null;
        let csv = '';
        const popupId = btn.getAttribute('data-popup-id');
        if (popupId) {
          popup = document.getElementById(popupId);
          csv = reconciliationDebugCsv;
        } else {
          const canvasId = btn.getAttribute('data-canvas-id');
          popup = canvasId ? document.getElementById(`${canvasId}-data-popup`) : null;
          if (canvasId) {
            const canvas = document.getElementById(canvasId);
            const chart = canvas && typeof chartCtor.getChart === 'function'
              ? chartCtor.getChart(canvas)
              : charts[canvasId];
            csv = chartDataToCsv(chart);
          }
        }

        if (!popup) {
          return;
        }

        try {
          const copied = await copyTextToClipboard(csv);
          showCopyFeedback(popup, {
            message: copied ? 'Copied to clipboard!' : 'Copy failed',
          });
        } catch (_error) {
          showCopyFeedback(popup, { message: 'Copy failed' });
        }
      });
    }

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', setup, { once: true });
      return {
        upsertAdsEvent: upsertAdsEvent,
      };
    }
    setup();
    return {
      upsertAdsEvent: upsertAdsEvent,
    };
  }

  if (typeof window !== 'undefined') {
    window.initAdsStatsPage = initAdsStatsPage;
    if (window.document && window.document.getElementById(ADS_STATS_PAGE_DATA_ELEMENT_ID)) {
      window.adsStatsPage = initAdsStatsPage();
    }
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      ADS_STATS_PAGE_DATA_ELEMENT_ID: ADS_STATS_PAGE_DATA_ELEMENT_ID,
      DAYS_OF_WEEK_MODE: DAYS_OF_WEEK_MODE,
      TIMELINE_MODE: TIMELINE_MODE,
      DAYS_OF_WEEK_LABELS: DAYS_OF_WEEK_LABELS,
      isIsoDateString: isIsoDateString,
      normalizeAdsEvent: normalizeAdsEvent,
      groupAdsEventsByDate: groupAdsEventsByDate,
      getAdsEventLinesForLabel: getAdsEventLinesForLabel,
      normalizeSearchTermRow: normalizeSearchTermRow,
      buildSearchTermAggregates: buildSearchTermAggregates,
      filterSearchTermAggregates: filterSearchTermAggregates,
      normalizePlacementRow: normalizePlacementRow,
      buildPlacementAggregates: buildPlacementAggregates,
      chartDataToCsv: chartDataToCsv,
      copyTextToClipboard: copyTextToClipboard,
      readAdsStatsPageOptionsFromDocument: readAdsStatsPageOptionsFromDocument,
      showCopyFeedback: showCopyFeedback,
      toNumber: toNumber,
      isAmazonAsinGuessTerm: isAmazonAsinGuessTerm,
      buildAmazonDpUrl: buildAmazonDpUrl,
      dayOfWeekIndexForDate: dayOfWeekIndexForDate,
      average: average,
      reserveScaleWidth: reserveScaleWidth,
      getDailyStatsForCampaign: getDailyStatsForCampaign,
      calculateTotals: calculateTotals,
      buildTimelineSeries: buildTimelineSeries,
      buildDaysOfWeekSeries: buildDaysOfWeekSeries,
      buildReconciledChartStats: buildReconciledChartStats,
      buildChartStats: buildChartStats,
      formatUnmatchedAdsTooltipLine: formatUnmatchedAdsTooltipLine,
      initAdsStatsPage: initAdsStatsPage,
    };
  }
})();


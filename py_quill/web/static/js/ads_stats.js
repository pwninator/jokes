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
  const RESERVED_RIGHT_GUTTER_PX = 56;

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

  function getAdsEventTooltipLines(eventGroup) {
    if (!eventGroup || !isIsoDateString(eventGroup.date)) {
      return [];
    }
    const titles = Array.isArray(eventGroup.titles)
      ? eventGroup.titles.map((title) => String(title || '').trim()).filter(Boolean)
      : [];
    return [eventGroup.date, ...titles];
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

  function toNumber(value) {
    const parsedValue = Number(value);
    return Number.isFinite(parsedValue) ? parsedValue : 0;
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

  function getDailyStatsForCampaign(adsStatsData, campaignName) {
    const data = adsStatsData || {};
    const labels = Array.isArray(data.labels) ? data.labels : [];
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
            dayImpressions += toNumber(camp.impressions);
            dayClicks += toNumber(camp.clicks);
            dayCost += toNumber(camp.spend);
            daySales += toNumber(camp.total_attributed_sales_usd);
            dayUnitsSold += toNumber(camp.total_units_sold);
            dayGpPreAd += toNumber(camp.gross_profit_before_ads_usd);
            dayGp += toNumber(camp.gross_profit_usd);
          });
        } else {
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
          if (camp.campaign_name === campaignName) {
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
    const grossProfitBeforeAds = rows.map((day) => toNumber(day.gross_profit_before_ads_usd));
    const grossProfit = rows.map((day) => toNumber(day.gross_profit_usd));

    return {
      labels: labels,
      impressions: impressions,
      clicks: clicks,
      cost: cost,
      sales_usd: sales,
      units_sold: unitsSold,
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
      bucket.gross_profit_before_ads_usd += toNumber(day.gross_profit_before_ads_usd);
      bucket.gross_profit_usd += toNumber(day.gross_profit_usd);
    });

    const impressions = weekdayBuckets.map((bucket) => average(bucket.impressions, bucket.count));
    const clicks = weekdayBuckets.map((bucket) => average(bucket.clicks, bucket.count));
    const cost = weekdayBuckets.map((bucket) => average(bucket.cost, bucket.count));
    const sales = weekdayBuckets.map((bucket) => average(bucket.sales_usd, bucket.count));
    const unitsSold = weekdayBuckets.map((bucket) => average(bucket.units_sold, bucket.count));
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
      gross_profit_before_ads_usd: series.gross_profit_before_ads_usd,
      gross_profit_usd: series.gross_profit_usd,
      poas: series.poas,
      cpc: series.cpc,
      ctr: series.ctr,
      conversion_rate: series.conversion_rate,
      totals: totals,
    };
  }

  function buildChartStats(adsStatsData, campaignName, mode) {
    const dailyStats = getDailyStatsForCampaign(adsStatsData, campaignName);
    return buildStatsFromDaily(adsStatsData, dailyStats, mode);
  }

  function getReconciledDailyStats(baseDailyStats, reconciledChartData) {
    const data = reconciledChartData || {};
    const labels = Array.isArray(data.labels) ? data.labels : [];
    const gpPreAd = Array.isArray(data.gross_profit_before_ads_usd)
      ? data.gross_profit_before_ads_usd
      : [];
    const organicProfit = Array.isArray(data.organic_profit_usd)
      ? data.organic_profit_usd
      : [];
    const rowsByDate = {};

    labels.forEach((dateKey, index) => {
      rowsByDate[dateKey] = {
        gross_profit_before_ads_usd: toNumber(gpPreAd[index]),
        organic_profit_usd: toNumber(organicProfit[index]),
      };
    });

    return (baseDailyStats || []).map((day) => {
      const reconciledDay = rowsByDate[day.dateKey] || {};
      const dayCost = toNumber(day.cost);
      const dayMatchedAdsProfitBeforeAds = toNumber(reconciledDay.gross_profit_before_ads_usd);
      const dayOrganicProfit = toNumber(reconciledDay.organic_profit_usd);
      const dayAdsProfitBeforeAds = toNumber(day.gross_profit_before_ads_usd);
      const dayUnmatchedAdsProfitBeforeAds = (
        dayAdsProfitBeforeAds - dayMatchedAdsProfitBeforeAds
      );
      const dayReconciledProfitBeforeAds = (
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
        reconciled_profit_before_ads_usd: dayReconciledProfitBeforeAds,
        organic_profit_usd: dayOrganicProfit,
        unmatched_pre_ad_profit_usd: dayUnmatchedAdsProfitBeforeAds,
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
      reconciled_profit_before_ads_usd: 0,
      organic_profit_usd: 0,
      unmatched_pre_ad_profit_usd: 0,
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
      bucket.reconciled_profit_before_ads_usd += toNumber(day.reconciled_profit_before_ads_usd);
      bucket.organic_profit_usd += toNumber(day.organic_profit_usd);
      bucket.unmatched_pre_ad_profit_usd += toNumber(day.unmatched_pre_ad_profit_usd);
      bucket.gross_profit_usd += toNumber(day.gross_profit_usd);
    });

    const cost = weekdayBuckets.map((bucket) => average(bucket.cost, bucket.count));
    const adsProfitBeforeAds = weekdayBuckets.map((bucket) =>
      average(bucket.ads_profit_before_ads_usd, bucket.count));
    const matchedAdsProfitBeforeAds = weekdayBuckets.map((bucket) =>
      average(bucket.matched_ads_profit_before_ads_usd, bucket.count));
    const grossProfitBeforeAds = weekdayBuckets.map((bucket) =>
      average(bucket.gross_profit_before_ads_usd, bucket.count));
    const reconciledProfitBeforeAds = weekdayBuckets.map((bucket) =>
      average(bucket.reconciled_profit_before_ads_usd, bucket.count));
    const organicProfit = weekdayBuckets.map((bucket) =>
      average(bucket.organic_profit_usd, bucket.count));
    const unmatchedPreAdProfit = weekdayBuckets.map((bucket) =>
      average(bucket.unmatched_pre_ad_profit_usd, bucket.count));
    const grossProfit = weekdayBuckets.map((bucket) =>
      average(bucket.gross_profit_usd, bucket.count));

    return {
      labels: DAYS_OF_WEEK_LABELS.slice(),
      cost: cost,
      ads_profit_before_ads_usd: adsProfitBeforeAds,
      matched_ads_profit_before_ads_usd: matchedAdsProfitBeforeAds,
      gross_profit_before_ads_usd: grossProfitBeforeAds,
      reconciled_profit_before_ads_usd: reconciledProfitBeforeAds,
      organic_profit_usd: organicProfit,
      unmatched_pre_ad_profit_usd: unmatchedPreAdProfit,
      gross_profit_usd: grossProfit,
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

  function buildReconciledChartStats(adsStatsData, campaignName, mode, reconciledChartData) {
    if (campaignName !== 'All') {
      return {
        labels: [],
        cost: [],
        ads_profit_before_ads_usd: [],
        matched_ads_profit_before_ads_usd: [],
        gross_profit_before_ads_usd: [],
        reconciled_profit_before_ads_usd: [],
        gross_profit_usd: [],
        organic_profit_usd: [],
        unmatched_pre_ad_profit_usd: [],
        poas: [],
        tpoas: [],
        totals: {
          cost: 0,
          ads_profit_before_ads_usd: 0,
          matched_ads_profit_before_ads_usd: 0,
          gross_profit_before_ads_usd: 0,
          reconciled_profit_before_ads_usd: 0,
          organic_profit_usd: 0,
          unmatched_pre_ad_profit_usd: 0,
          gross_profit_usd: 0,
        },
      };
    }

    const baseDailyStats = getDailyStatsForCampaign(adsStatsData, 'All');
    const reconciledDailyStats = getReconciledDailyStats(baseDailyStats, reconciledChartData).map(
      (day, index) => ({
        dateKey: day.dateKey,
        impressions: toNumber(baseDailyStats[index] && baseDailyStats[index].impressions),
        cost: day.cost,
        raw_gross_profit_before_ads_usd: day.raw_gross_profit_before_ads_usd,
        ads_profit_before_ads_usd: day.ads_profit_before_ads_usd,
        matched_ads_profit_before_ads_usd: day.matched_ads_profit_before_ads_usd,
        gross_profit_before_ads_usd: day.gross_profit_before_ads_usd,
        reconciled_profit_before_ads_usd: day.reconciled_profit_before_ads_usd,
        organic_profit_usd: day.organic_profit_usd,
        unmatched_pre_ad_profit_usd: day.unmatched_pre_ad_profit_usd,
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
      reconciled_profit_before_ads_usd: reconciledDailyStats.map(
        (day) => day.reconciled_profit_before_ads_usd),
      gross_profit_usd: reconciledDailyStats.map((day) => day.gross_profit_usd),
      organic_profit_usd: reconciledDailyStats.map((day) => day.organic_profit_usd),
      unmatched_pre_ad_profit_usd: reconciledDailyStats.map(
        (day) => day.unmatched_pre_ad_profit_usd),
      poas: reconciledDailyStats.map((day) => {
        return calculatePoas(day.raw_gross_profit_before_ads_usd, day.cost);
      }),
      tpoas: reconciledDailyStats.map((day) => {
        return calculateTpoas(day.raw_gross_profit_before_ads_usd, day.organic_profit_usd, day.cost);
      }),
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

  function initAdsStatsPage(options) {
    const config = options || {};
    const adsStatsData = config.chartData || {};
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

    function setup() {
      if (typeof window === 'undefined' || !window.document) {
        return;
      }
      const chartCtor = window.Chart;
      if (typeof chartCtor !== 'function') {
        return;
      }

      const campaignSelector = document.getElementById('campaignSelector');
      const modeSelector = document.getElementById('modeSelector');
      if (!campaignSelector || !modeSelector) {
        return;
      }

      const charts = {};
      const adsEventsOverlayPlugin = {
        id: 'adsEventsOverlay',
        afterEvent: function (chart, args) {
          const pluginOptions = chart.options && chart.options.plugins
            ? chart.options.plugins.adsEventsOverlay
            : null;
          if (!pluginOptions || !pluginOptions.enabled) {
            hideAdsEventTooltip(chart);
            if (chart.$adsEventsHoveredDate) {
              chart.$adsEventsHoveredDate = '';
              chart.draw();
            }
            return;
          }

          const chartEvent = args && args.event ? args.event : null;
          if (!chartEvent || chartEvent.type === 'mouseout' || chartEvent.type === 'mouseleave') {
            hideAdsEventTooltip(chart);
            if (chart.$adsEventsHoveredDate) {
              chart.$adsEventsHoveredDate = '';
              chart.draw();
            }
            return;
          }

          const chartArea = chart.chartArea;
          const xScale = chart.scales ? chart.scales.x : null;
          if (!chartArea || !xScale || !Number.isFinite(chartEvent.x) || !Number.isFinite(chartEvent.y)) {
            return;
          }

          const events = Array.isArray(pluginOptions.events) ? pluginOptions.events : [];
          let nearestGroup = null;
          let nearestPixelX = null;
          let nearestDistance = Number.POSITIVE_INFINITY;
          events.forEach((eventGroup) => {
            const pixelX = xScale.getPixelForValue(eventGroup.date);
            if (!Number.isFinite(pixelX) || pixelX < chartArea.left || pixelX > chartArea.right) {
              return;
            }
            const distance = Math.abs(chartEvent.x - pixelX);
            if (distance <= 8 && distance < nearestDistance) {
              nearestDistance = distance;
              nearestPixelX = pixelX;
              nearestGroup = eventGroup;
            }
          });

          const nextHoveredDate = nearestGroup ? nearestGroup.date : '';
          if (chart.$adsEventsHoveredDate !== nextHoveredDate) {
            chart.$adsEventsHoveredDate = nextHoveredDate;
            chart.draw();
          }

          if (!nearestGroup
            || chartEvent.y < chartArea.top
            || chartEvent.y > chartArea.bottom) {
            hideAdsEventTooltip(chart);
            return;
          }

          showAdsEventTooltip(
            chart,
            nearestGroup,
            Number.isFinite(nearestPixelX) ? nearestPixelX : chartEvent.x,
            chartEvent.y,
          );
        },
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
            const isHovered = chart.$adsEventsHoveredDate === eventGroup.date;
            ctx.beginPath();
            ctx.moveTo(pixelX, chartArea.top);
            ctx.lineTo(pixelX, chartArea.bottom);
            ctx.lineWidth = isHovered ? 2 : 1;
            ctx.strokeStyle = isHovered ? '#1f2937' : '#8d99ae';
            ctx.stroke();
          });
          ctx.restore();
        },
      };

      function getAdsEventTooltipElement(chart) {
        if (chart.$adsEventsTooltipEl) {
          return chart.$adsEventsTooltipEl;
        }
        const container = chart.canvas && chart.canvas.parentElement;
        if (!container) {
          return null;
        }
        const tooltipEl = document.createElement('div');
        tooltipEl.style.position = 'absolute';
        tooltipEl.style.display = 'none';
        tooltipEl.style.padding = '8px 10px';
        tooltipEl.style.borderRadius = '6px';
        tooltipEl.style.border = '1px solid #cfd8dc';
        tooltipEl.style.background = '#ffffff';
        tooltipEl.style.color = '#1f2937';
        tooltipEl.style.fontSize = '12px';
        tooltipEl.style.lineHeight = '1.4';
        tooltipEl.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.16)';
        tooltipEl.style.pointerEvents = 'none';
        tooltipEl.style.zIndex = '20';
        container.appendChild(tooltipEl);
        chart.$adsEventsTooltipEl = tooltipEl;
        return tooltipEl;
      }

      function hideAdsEventTooltip(chart) {
        const tooltipEl = chart.$adsEventsTooltipEl;
        if (tooltipEl) {
          tooltipEl.style.display = 'none';
        }
      }

      function showAdsEventTooltip(chart, eventGroup, xPos, yPos) {
        const lines = getAdsEventTooltipLines(eventGroup);
        if (lines.length === 0) {
          hideAdsEventTooltip(chart);
          return;
        }

        const tooltipEl = getAdsEventTooltipElement(chart);
        const container = chart.canvas && chart.canvas.parentElement;
        if (!tooltipEl || !container) {
          return;
        }

        tooltipEl.innerHTML = lines.map((line, index) => {
          const fontWeight = index === 0 ? '700' : '400';
          return `<div style="font-weight: ${fontWeight};">${escapeHtml(line)}</div>`;
        }).join('');
        tooltipEl.style.display = 'block';

        const maxLeft = Math.max(8, container.clientWidth - tooltipEl.offsetWidth - 8);
        const maxTop = Math.max(8, container.clientHeight - tooltipEl.offsetHeight - 8);
        const left = Math.max(8, Math.min(maxLeft, xPos + 12));
        const top = Math.max(8, Math.min(maxTop, yPos + 12));
        tooltipEl.style.left = `${left}px`;
        tooltipEl.style.top = `${top}px`;
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
                callbacks: {
                  label: function (context) {
                    const formatType = context.dataset.formatType || 'number';
                    return `${context.dataset.label}: ${formatValueByType(
                      formatType,
                      context.parsed.y,
                    )}`;
                  },
                },
              },
              adsEventsOverlay: {
                enabled: mode === TIMELINE_MODE,
                events: adsEventGroups,
              },
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
          }, mode),
          createLineDataset({
            label: 'Profit Before Ads (reconciled)',
            data: series.reconciled_profit_before_ads_usd,
            borderColor: '#2e7d32',
            formatType: 'currency',
          }, mode),
          createLineDataset({
            label: 'Gross Profit',
            data: series.gross_profit_usd,
            borderColor: '#6a1b9a',
            fill: 'origin',
            formatType: 'currency',
          }, mode),
        ];
        createMultiLineChart(
          'reconciledProfitTimelineChart',
          series.labels,
          datasets,
          buildSingleAxis('currency'),
          mode,
        );
      }

      function renderPoasChart(canvasId, series, poasLabel, poasColor, tpoasLabel, tpoasColor, mode) {
        const ratioSeries = tpoasLabel ? [...series.poas, ...series.tpoas] : [...series.poas];
        const suggestedMax = Math.max(1.1, ...ratioSeries, 1.0);
        const datasets = [
          createLineDataset({
            label: poasLabel,
            data: series.poas,
            borderColor: poasColor,
            formatType: 'ratio',
          }, mode),
        ];
        if (tpoasLabel) {
          datasets.push(createLineDataset({
            label: tpoasLabel,
            data: series.tpoas,
            borderColor: tpoasColor,
            formatType: 'ratio',
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
        createMultiLineChart(
          'adsProfitBreakdownChart',
          series.labels,
          [
            createLineDataset({
              label: 'Profit Before Ads (ads)',
              data: series.ads_profit_before_ads_usd,
              borderColor: '#ef6c00',
              formatType: 'currency',
            }, mode),
            createLineDataset({
              label: 'Matched Ads Profit',
              data: series.matched_ads_profit_before_ads_usd,
              borderColor: '#2e7d32',
              formatType: 'currency',
            }, mode),
            createLineDataset({
              label: 'Unmatched Ad Profit',
              data: series.unmatched_pre_ad_profit_usd,
              borderColor: '#c62828',
              formatType: 'currency',
            }, mode),
          ],
          buildSingleAxis('currency'),
          mode,
        );
      }

      function calculateAndRender(campaignName, mode) {
        const stats = buildChartStats(adsStatsData, campaignName, mode);
        const reconciledStats = buildReconciledChartStats(
          adsStatsData,
          campaignName,
          mode,
          reconciledClickDateChartData,
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

      const campaignNames = new Set();
      Object.values(adsStatsData.daily_campaigns || {}).forEach((campaignList) => {
        if (!Array.isArray(campaignList)) {
          return;
        }
        campaignList.forEach((campaign) => {
          if (campaign && campaign.campaign_name) {
            campaignNames.add(campaign.campaign_name);
          }
        });
      });

      Array.from(campaignNames).sort().forEach((name) => {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = name;
        campaignSelector.appendChild(option);
      });

      renderSelectedView = () => {
        calculateAndRender(campaignSelector.value, modeSelector.value);
      };

      campaignSelector.addEventListener('change', renderSelectedView);
      modeSelector.addEventListener('change', renderSelectedView);
      renderSelectedView();

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
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      DAYS_OF_WEEK_MODE: DAYS_OF_WEEK_MODE,
      TIMELINE_MODE: TIMELINE_MODE,
      DAYS_OF_WEEK_LABELS: DAYS_OF_WEEK_LABELS,
      isIsoDateString: isIsoDateString,
      normalizeAdsEvent: normalizeAdsEvent,
      groupAdsEventsByDate: groupAdsEventsByDate,
      getAdsEventTooltipLines: getAdsEventTooltipLines,
      chartDataToCsv: chartDataToCsv,
      copyTextToClipboard: copyTextToClipboard,
      showCopyFeedback: showCopyFeedback,
      toNumber: toNumber,
      dayOfWeekIndexForDate: dayOfWeekIndexForDate,
      average: average,
      reserveScaleWidth: reserveScaleWidth,
      getDailyStatsForCampaign: getDailyStatsForCampaign,
      calculateTotals: calculateTotals,
      buildTimelineSeries: buildTimelineSeries,
      buildDaysOfWeekSeries: buildDaysOfWeekSeries,
      buildReconciledChartStats: buildReconciledChartStats,
      buildChartStats: buildChartStats,
      initAdsStatsPage: initAdsStatsPage,
    };
  }
})();

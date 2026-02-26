(function () {
  'use strict';

  const DAYS_OF_WEEK_MODE = 'Days of Week';
  const DAYS_OF_WEEK_LABELS = Object.freeze([
    'Sun',
    'Mon',
    'Tue',
    'Wed',
    'Thu',
    'Fri',
    'Sat',
  ]);

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
        const dayCost = toNumber(day.cost);
        return dayCost > 0 ? toNumber(day.gross_profit_before_ads_usd) / dayCost : 0;
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
      return avgCost > 0 ? avgGrossProfitBeforeAds / avgCost : 0;
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

  function buildChartStats(adsStatsData, campaignName, mode) {
    const dailyStats = getDailyStatsForCampaign(adsStatsData, campaignName);
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

  function initAdsStatsPage(options) {
    const config = options || {};
    const adsStatsData = config.chartData || {};

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

      function createMultiLineChart(canvasId, labels, datasets, scales) {
        const canvas = document.getElementById(canvasId);
        if (!canvas || typeof canvas.getContext !== 'function') {
          return;
        }
        const ctx = canvas.getContext('2d');

        if (charts[canvasId]) {
          charts[canvasId].destroy();
        }

        charts[canvasId] = new chartCtor(ctx, {
          type: 'line',
          data: {
            labels: labels,
            datasets: datasets,
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
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
            },
          },
        });
      }

      function calculateAndRender(campaignName, mode) {
        const stats = buildChartStats(adsStatsData, campaignName, mode);

        createMultiLineChart(
          'profitChart',
          stats.labels,
          [
            {
              label: 'Cost',
              data: stats.cost,
              borderColor: '#c62828',
              backgroundColor: '#c6282822',
              fill: false,
              tension: 0.2,
              pointRadius: 3,
              yAxisID: 'y',
              formatType: 'currency',
            },
            {
              label: 'Gross Profit Before Ads',
              data: stats.gross_profit_before_ads_usd,
              borderColor: '#2e7d32',
              backgroundColor: '#2e7d3222',
              fill: false,
              tension: 0.2,
              pointRadius: 3,
              yAxisID: 'y',
              formatType: 'currency',
            },
            {
              label: 'Gross Profit',
              data: stats.gross_profit_usd,
              borderColor: '#6a1b9a',
              backgroundColor: '#6a1b9a22',
              fill: 'origin',
              tension: 0.2,
              pointRadius: 3,
              yAxisID: 'y',
              formatType: 'currency',
            },
          ],
          {
            y: {
              beginAtZero: true,
              ticks: {
                callback: function (value) {
                  return formatTickByType('currency', value);
                },
              },
            },
          },
        );

        const poasSuggestedMax = Math.max(1.1, ...stats.poas, 1.0);
        createMultiLineChart(
          'poasChart',
          stats.labels,
          [
            {
              label: 'POAS',
              data: stats.poas,
              borderColor: '#1565c0',
              backgroundColor: '#1565c022',
              fill: false,
              tension: 0.2,
              pointRadius: 3,
              yAxisID: 'y',
              formatType: 'ratio',
            },
            {
              label: 'POAS Threshold (1.0)',
              data: stats.labels.map(() => 1.0),
              borderColor: '#c62828',
              backgroundColor: '#c6282822',
              fill: false,
              tension: 0,
              pointRadius: 0,
              borderWidth: 1,
              yAxisID: 'y',
              formatType: 'ratio',
            },
          ],
          {
            y: {
              beginAtZero: true,
              suggestedMax: poasSuggestedMax,
              ticks: {
                callback: function (value) {
                  return formatTickByType('ratio', value);
                },
              },
            },
          },
        );

        createMultiLineChart(
          'cpcAndConversionRateChart',
          stats.labels,
          [
            {
              label: 'CPC',
              data: stats.cpc,
              borderColor: '#d81b60',
              backgroundColor: '#d81b6022',
              fill: false,
              tension: 0.2,
              pointRadius: 3,
              yAxisID: 'y',
              formatType: 'currency',
            },
            {
              label: 'Conversion Rate',
              data: stats.conversion_rate,
              borderColor: '#00838f',
              backgroundColor: '#00838f22',
              fill: false,
              tension: 0.2,
              pointRadius: 3,
              yAxisID: 'y1',
              formatType: 'percent',
            },
          ],
          {
            y: {
              beginAtZero: true,
              position: 'left',
              ticks: {
                callback: function (value) {
                  return formatTickByType('currency', value);
                },
              },
            },
            y1: {
              beginAtZero: true,
              position: 'right',
              grid: {
                drawOnChartArea: false,
              },
              ticks: {
                callback: function (value) {
                  return formatTickByType('percent', value);
                },
              },
            },
          },
        );

        createMultiLineChart(
          'ctrChart',
          stats.labels,
          [
            {
              label: 'CTR',
              data: stats.ctr,
              borderColor: '#ef6c00',
              backgroundColor: '#ef6c0022',
              fill: false,
              tension: 0.2,
              pointRadius: 3,
              yAxisID: 'y',
              formatType: 'percent',
            },
          ],
          {
            y: {
              beginAtZero: true,
              position: 'left',
              ticks: {
                callback: function (value) {
                  return formatTickByType('percent', value);
                },
              },
            },
          },
        );

        createMultiLineChart(
          'impressionsAndClicksChart',
          stats.labels,
          [
            {
              label: 'Impressions',
              data: stats.impressions,
              borderColor: '#2e7d32',
              backgroundColor: '#2e7d3222',
              fill: false,
              tension: 0.2,
              pointRadius: 3,
              yAxisID: 'y',
              formatType: 'number',
            },
            {
              label: 'Clicks',
              data: stats.clicks,
              borderColor: '#1565c0',
              backgroundColor: '#1565c022',
              fill: false,
              tension: 0.2,
              pointRadius: 3,
              yAxisID: 'y1',
              formatType: 'number',
            },
          ],
          {
            y: {
              beginAtZero: true,
              position: 'left',
              ticks: {
                callback: function (value) {
                  return formatTickByType('number', value);
                },
              },
            },
            y1: {
              beginAtZero: true,
              position: 'right',
              grid: {
                drawOnChartArea: false,
              },
              ticks: {
                callback: function (value) {
                  return formatTickByType('number', value);
                },
              },
            },
          },
        );

        const statImpressions = document.getElementById('stat-impressions');
        const statClicks = document.getElementById('stat-clicks');
        const statCost = document.getElementById('stat-cost');
        const statGpPreAd = document.getElementById('stat-gp-pre-ad');
        const statGp = document.getElementById('stat-gp');
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
        if (statGpPreAd) {
          statGpPreAd.textContent = formatCurrency(stats.totals.gross_profit_before_ads_usd);
        }
        if (statGp) {
          statGp.textContent = formatCurrency(stats.totals.gross_profit_usd);
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

      const renderSelectedView = () => {
        calculateAndRender(campaignSelector.value, modeSelector.value);
      };

      campaignSelector.addEventListener('change', renderSelectedView);
      modeSelector.addEventListener('change', renderSelectedView);
      renderSelectedView();
    }

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', setup, { once: true });
      return;
    }
    setup();
  }

  if (typeof window !== 'undefined') {
    window.initAdsStatsPage = initAdsStatsPage;
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      DAYS_OF_WEEK_MODE: DAYS_OF_WEEK_MODE,
      DAYS_OF_WEEK_LABELS: DAYS_OF_WEEK_LABELS,
      toNumber: toNumber,
      dayOfWeekIndexForDate: dayOfWeekIndexForDate,
      average: average,
      getDailyStatsForCampaign: getDailyStatsForCampaign,
      calculateTotals: calculateTotals,
      buildTimelineSeries: buildTimelineSeries,
      buildDaysOfWeekSeries: buildDaysOfWeekSeries,
      buildChartStats: buildChartStats,
      initAdsStatsPage: initAdsStatsPage,
    };
  }
})();

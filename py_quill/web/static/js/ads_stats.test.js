const assert = require('node:assert/strict');
const test = require('node:test');

const {
  DAYS_OF_WEEK_MODE,
  DAYS_OF_WEEK_LABELS,
  buildDaysOfWeekSeries,
  buildChartStats,
  getDailyStatsForCampaign,
} = require('./ads_stats.js');

function assertClose(actual, expected, tolerance = 1e-9) {
  assert.ok(
    Math.abs(Number(actual) - Number(expected)) <= tolerance,
    `Expected ${actual} to be within ${tolerance} of ${expected}`,
  );
}

test('buildDaysOfWeekSeries averages weekdays and skips zero-impression days', () => {
  const dailyStats = [
    {
      dateKey: '2026-02-22', // Sun
      impressions: 100,
      clicks: 10,
      cost: 20,
      sales: 50,
      units_sold: 2,
      gross_profit_before_ads: 40,
      gross_profit: 20,
    },
    {
      dateKey: '2026-03-01', // Sun
      impressions: 300,
      clicks: 30,
      cost: 60,
      sales: 120,
      units_sold: 6,
      gross_profit_before_ads: 150,
      gross_profit: 90,
    },
    {
      dateKey: '2026-02-23', // Mon (should be excluded from weekday averages)
      impressions: 0,
      clicks: 999,
      cost: 999,
      sales: 999,
      units_sold: 999,
      gross_profit_before_ads: 999,
      gross_profit: 999,
    },
    {
      dateKey: '2026-02-24', // Tue
      impressions: 10,
      clicks: 4,
      cost: 0,
      sales: 8,
      units_sold: 1,
      gross_profit_before_ads: 8,
      gross_profit: 8,
    },
    {
      dateKey: '2026-02-25', // Wed
      impressions: 10,
      clicks: 0,
      cost: 5,
      sales: 7,
      units_sold: 0,
      gross_profit_before_ads: 9,
      gross_profit: 4,
    },
  ];

  const series = buildDaysOfWeekSeries(dailyStats);
  assert.deepEqual(series.labels, DAYS_OF_WEEK_LABELS);

  // Sunday averages from two valid Sundays.
  assertClose(series.impressions[0], 200);
  assertClose(series.clicks[0], 20);
  assertClose(series.cost[0], 40);
  assertClose(series.gross_profit_before_ads[0], 95);
  assertClose(series.poas[0], 2.375);
  assertClose(series.cpc[0], 2);
  assertClose(series.ctr[0], 10);
  assertClose(series.conversion_rate[0], 20);

  // Monday excluded entirely because impressions were zero.
  assertClose(series.impressions[1], 0);
  assertClose(series.cost[1], 0);

  // Tuesday denominator handling: avg cost is zero -> POAS/CPC are zero.
  assertClose(series.poas[2], 0);
  assertClose(series.cpc[2], 0);
  assertClose(series.ctr[2], 40);

  // Wednesday denominator handling: avg clicks is zero -> CPC/CR are zero.
  assertClose(series.cpc[3], 0);
  assertClose(series.ctr[3], 0);
  assertClose(series.conversion_rate[3], 0);
});

test('getDailyStatsForCampaign prefers campaign sums for All when campaign rows exist', () => {
  const chartData = {
    labels: ['2026-02-22', '2026-02-23'],
    impressions: [999, 77],
    clicks: [999, 7],
    cost: [999, 8],
    sales: [999, 9],
    units_sold: [999, 3],
    gross_profit_before_ads: [999, 20],
    gross_profit: [999, 11],
    daily_campaigns: {
      '2026-02-22': [
        {
          campaign_name: 'Campaign A',
          impressions: 40,
          clicks: 4,
          spend: 8,
          total_attributed_sales: 12,
          total_units_sold: 2,
          gross_profit_before_ads: 16,
          gross_profit: 8,
        },
        {
          campaign_name: 'Campaign B',
          impressions: 60,
          clicks: 6,
          spend: 12,
          total_attributed_sales: 18,
          total_units_sold: 3,
          gross_profit_before_ads: 24,
          gross_profit: 12,
        },
      ],
      '2026-02-23': [],
    },
  };

  const all = getDailyStatsForCampaign(chartData, 'All');
  assert.equal(all[0].impressions, 100);
  assert.equal(all[0].cost, 20);
  // Falls back to aggregate arrays when no campaign rows exist.
  assert.equal(all[1].impressions, 77);
  assert.equal(all[1].cost, 8);

  const campaignA = getDailyStatsForCampaign(chartData, 'Campaign A');
  assert.equal(campaignA[0].impressions, 40);
  assert.equal(campaignA[0].cost, 8);
  assert.equal(campaignA[1].impressions, 0);
});

test('buildChartStats keeps totals stable while Days of Week series skips zero-impression days', () => {
  const chartData = {
    labels: ['2026-02-22', '2026-02-23'],
    impressions: [10, 0],
    clicks: [2, 100],
    cost: [4, 50],
    sales: [8, 60],
    units_sold: [1, 20],
    gross_profit_before_ads: [6, 70],
    gross_profit: [2, 20],
    daily_campaigns: {
      '2026-02-22': [],
      '2026-02-23': [],
    },
  };

  const timeline = buildChartStats(chartData, 'All', 'Timeline');
  const daysOfWeek = buildChartStats(chartData, 'All', DAYS_OF_WEEK_MODE);

  // Stat-card totals remain unchanged across modes.
  assert.equal(daysOfWeek.totals.impressions, timeline.totals.impressions);
  assert.equal(daysOfWeek.totals.clicks, timeline.totals.clicks);
  assert.equal(daysOfWeek.totals.cost, timeline.totals.cost);
  assert.equal(daysOfWeek.totals.gross_profit_before_ads, timeline.totals.gross_profit_before_ads);

  // Monday bucket should be zeroed because that day has zero impressions.
  assertClose(daysOfWeek.impressions[1], 0);
  assertClose(daysOfWeek.cost[1], 0);
  assertClose(daysOfWeek.cpc[1], 0);
  assertClose(daysOfWeek.ctr[1], 0);
  assertClose(daysOfWeek.poas[1], 0);
});

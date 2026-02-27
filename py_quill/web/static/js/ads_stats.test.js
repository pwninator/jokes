const assert = require('node:assert/strict');
const test = require('node:test');

const {
  DAYS_OF_WEEK_MODE,
  DAYS_OF_WEEK_LABELS,
  buildDaysOfWeekSeries,
  buildReconciledChartStats,
  buildChartStats,
  chartDataToCsv,
  isIsoDateString,
  normalizeAdsEvent,
  groupAdsEventsByDate,
  getAdsEventTooltipLines,
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
      sales_usd: 50,
      units_sold: 2,
      gross_profit_before_ads_usd: 40,
      gross_profit_usd: 20,
    },
    {
      dateKey: '2026-03-01', // Sun
      impressions: 300,
      clicks: 30,
      cost: 60,
      sales_usd: 120,
      units_sold: 6,
      gross_profit_before_ads_usd: 150,
      gross_profit_usd: 90,
    },
    {
      dateKey: '2026-02-23', // Mon (should be excluded from weekday averages)
      impressions: 0,
      clicks: 999,
      cost: 999,
      sales_usd: 999,
      units_sold: 999,
      gross_profit_before_ads_usd: 999,
      gross_profit_usd: 999,
    },
    {
      dateKey: '2026-02-24', // Tue
      impressions: 10,
      clicks: 4,
      cost: 0,
      sales_usd: 8,
      units_sold: 1,
      gross_profit_before_ads_usd: 8,
      gross_profit_usd: 8,
    },
    {
      dateKey: '2026-02-25', // Wed
      impressions: 10,
      clicks: 0,
      cost: 5,
      sales_usd: 7,
      units_sold: 0,
      gross_profit_before_ads_usd: 9,
      gross_profit_usd: 4,
    },
  ];

  const series = buildDaysOfWeekSeries(dailyStats);
  assert.deepEqual(series.labels, DAYS_OF_WEEK_LABELS);

  // Sunday averages from two valid Sundays.
  assertClose(series.impressions[0], 200);
  assertClose(series.clicks[0], 20);
  assertClose(series.cost[0], 40);
  assertClose(series.gross_profit_before_ads_usd[0], 95);
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
    sales_usd: [999, 9],
    units_sold: [999, 3],
    gross_profit_before_ads_usd: [999, 20],
    gross_profit_usd: [999, 11],
    daily_campaigns: {
      '2026-02-22': [
        {
          campaign_name: 'Campaign A',
          impressions: 40,
          clicks: 4,
          spend: 8,
          total_attributed_sales_usd: 12,
          total_units_sold: 2,
          gross_profit_before_ads_usd: 16,
          gross_profit_usd: 8,
        },
        {
          campaign_name: 'Campaign B',
          impressions: 60,
          clicks: 6,
          spend: 12,
          total_attributed_sales_usd: 18,
          total_units_sold: 3,
          gross_profit_before_ads_usd: 24,
          gross_profit_usd: 12,
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
    sales_usd: [8, 60],
    units_sold: [1, 20],
    gross_profit_before_ads_usd: [6, 70],
    gross_profit_usd: [2, 20],
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
  assert.equal(daysOfWeek.totals.gross_profit_before_ads_usd, timeline.totals.gross_profit_before_ads_usd);

  // Monday bucket should be zeroed because that day has zero impressions.
  assertClose(daysOfWeek.impressions[1], 0);
  assertClose(daysOfWeek.cost[1], 0);
  assertClose(daysOfWeek.cpc[1], 0);
  assertClose(daysOfWeek.ctr[1], 0);
  assertClose(daysOfWeek.poas[1], 0);
});

test('buildReconciledChartStats matches main chart cost and poas for campaign All', () => {
  const chartData = {
    labels: ['2026-02-22', '2026-02-23'],
    impressions: [10, 20],
    clicks: [2, 4],
    cost: [4, 10],
    sales_usd: [8, 12],
    units_sold: [1, 2],
    gross_profit_before_ads_usd: [6, 15],
    gross_profit_usd: [2, 5],
    daily_campaigns: {
      '2026-02-22': [],
      '2026-02-23': [],
    },
  };
  const reconciledChartData = {
    labels: ['2026-02-22', '2026-02-23'],
    gross_profit_before_ads_usd: [5, 11],
    organic_profit_usd: [1, 3],
  };

  const timeline = buildReconciledChartStats(
    chartData,
    'All',
    'Timeline',
    reconciledChartData,
  );
  const daysOfWeek = buildReconciledChartStats(
    chartData,
    'All',
    DAYS_OF_WEEK_MODE,
    reconciledChartData,
  );

  assert.deepEqual(timeline.labels, ['2026-02-22', '2026-02-23']);
  assert.deepEqual(timeline.cost, [4, 10]);
  assertClose(timeline.poas[0], 6 / 4);
  assertClose(timeline.poas[1], 15 / 10);
  assertClose(timeline.tpoas[0], (6 + 1) / 4);
  assertClose(timeline.tpoas[1], (15 + 3) / 10);
  assert.deepEqual(timeline.gross_profit_before_ads_usd, [5, 11]);
  assert.deepEqual(timeline.organic_profit_usd, [1, 3]);
  assert.deepEqual(timeline.unmatched_pre_ad_profit_usd, [1, 4]);
  assert.deepEqual(timeline.gross_profit_usd, [2, 4]);
  assertClose(timeline.totals.unmatched_pre_ad_profit_usd, 5);

  assert.deepEqual(daysOfWeek.labels, DAYS_OF_WEEK_LABELS);
  assertClose(daysOfWeek.cost[0], 4); // Sunday
  assertClose(daysOfWeek.cost[1], 10); // Monday
  assertClose(daysOfWeek.poas[0], 6 / 4);
  assertClose(daysOfWeek.poas[1], 15 / 10);
  assertClose(daysOfWeek.tpoas[0], (6 + 1) / 4);
  assertClose(daysOfWeek.tpoas[1], (15 + 3) / 10);
  assertClose(daysOfWeek.unmatched_pre_ad_profit_usd[0], 1);
  assertClose(daysOfWeek.unmatched_pre_ad_profit_usd[1], 4);
});

test('buildReconciledChartStats returns empty series for specific campaigns', () => {
  const chartData = {
    labels: ['2026-02-22'],
    daily_campaigns: {
      '2026-02-22': [
        {
          campaign_name: 'Campaign A',
          impressions: 10,
          clicks: 2,
          spend: 4,
          total_attributed_sales_usd: 8,
          total_units_sold: 1,
          gross_profit_before_ads_usd: 6,
          gross_profit_usd: 2,
        },
      ],
    },
  };

  const reconciled = buildReconciledChartStats(
    chartData,
    'Campaign A',
    'Timeline',
    { labels: ['2026-02-22'] },
  );

  assert.deepEqual(reconciled.labels, []);
  assert.deepEqual(reconciled.cost, []);
  assert.deepEqual(reconciled.unmatched_pre_ad_profit_usd, []);
  assert.deepEqual(reconciled.poas, []);
  assert.deepEqual(reconciled.tpoas, []);
});

test('normalizeAdsEvent validates required fields and date format', () => {
  assert.equal(normalizeAdsEvent(null), null);
  assert.equal(normalizeAdsEvent({}), null);
  assert.equal(normalizeAdsEvent({ date: '2026-02-2', title: 'Launch' }), null);
  assert.equal(normalizeAdsEvent({ date: '2026-02-22', title: '' }), null);

  const normalized = normalizeAdsEvent({
    key: 'k1',
    date: '2026-02-22',
    title: 'Launch Day',
  });
  assert.deepEqual(normalized, {
    key: 'k1',
    date: '2026-02-22',
    title: 'Launch Day',
  });
  assert.equal(isIsoDateString('2026-02-22'), true);
  assert.equal(isIsoDateString('2026-2-22'), false);
});

test('groupAdsEventsByDate groups and sorts events by date', () => {
  const grouped = groupAdsEventsByDate([
    { date: '2026-02-23', title: 'Promo start' },
    { date: '2026-02-22', title: 'Launch' },
    { date: '2026-02-22', title: 'Budget increase' },
    { date: 'bad-date', title: 'Ignore me' },
  ]);

  assert.deepEqual(grouped, [
    {
      date: '2026-02-22',
      titles: ['Launch', 'Budget increase'],
    },
    {
      date: '2026-02-23',
      titles: ['Promo start'],
    },
  ]);
});

test('getAdsEventTooltipLines returns date followed by one title per line', () => {
  assert.deepEqual(getAdsEventTooltipLines(null), []);
  assert.deepEqual(getAdsEventTooltipLines({ date: 'bad', titles: ['x'] }), []);
  assert.deepEqual(
    getAdsEventTooltipLines({
      date: '2026-02-22',
      titles: ['Launch', 'Budget increase'],
    }),
    ['2026-02-22', 'Launch', 'Budget increase'],
  );
});

test('chartDataToCsv returns empty string for null or missing data', () => {
  assert.equal(chartDataToCsv(null), '');
  assert.equal(chartDataToCsv(undefined), '');
  assert.equal(chartDataToCsv({}), '');
  assert.equal(chartDataToCsv({ data: {} }), '');
  assert.equal(chartDataToCsv({ data: { labels: [], datasets: [] } }), '');
});

test('chartDataToCsv produces CSV with Date column and one column per dataset', () => {
  const chart = {
    data: {
      labels: ['2026-02-22', '2026-02-23'],
      datasets: [
        { label: 'Cost', data: [12.5, 15.0] },
        { label: 'Gross Profit', data: [45.0, 52.0] },
      ],
    },
  };
  const csv = chartDataToCsv(chart);
  assert.ok(csv.includes('Date,Cost,Gross Profit'));
  assert.ok(csv.includes('2026-02-22,12.5,45'));
  assert.ok(csv.includes('2026-02-23,15,52'));
});

test('chartDataToCsv escapes commas and quotes in values', () => {
  const chart = {
    data: {
      labels: ['2026-02-22'],
      datasets: [
        { label: 'A,B', data: ['"quoted"'] },
      ],
    },
  };
  const csv = chartDataToCsv(chart);
  assert.ok(csv.includes('"A,B"'));
  assert.ok(csv.includes('"""quoted"""'));
});

test('chartDataToCsv handles missing data points with empty string', () => {
  const chart = {
    data: {
      labels: ['2026-02-22', '2026-02-23'],
      datasets: [
        { label: 'A', data: [1] },
        { label: 'B', data: [10, 20] },
      ],
    },
  };
  const csv = chartDataToCsv(chart);
  const lines = csv.split('\n');
  assert.equal(lines.length, 3);
  assert.ok(lines[2].endsWith(',20'));
});

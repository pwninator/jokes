const assert = require('node:assert/strict');
const test = require('node:test');

const {
  FakeDocument,
  FakeElement,
  append,
  createFakeClock,
} = require('./test_utils.js');
const {
  DAYS_OF_WEEK_MODE,
  DAYS_OF_WEEK_LABELS,
  TIMELINE_MODE,
  buildDaysOfWeekSeries,
  buildReconciledChartStats,
  buildChartStats,
  chartDataToCsv,
  copyTextToClipboard,
  formatUnmatchedAdsTooltipLine,
  isIsoDateString,
  normalizeAdsEvent,
  groupAdsEventsByDate,
  getAdsEventTooltipLines,
  getDailyStatsForCampaign,
  initAdsStatsPage,
  reserveScaleWidth,
  showCopyFeedback,
} = require('./ads_stats.js');

function assertClose(actual, expected, tolerance = 1e-9) {
  assert.ok(
    Math.abs(Number(actual) - Number(expected)) <= tolerance,
    `Expected ${actual} to be within ${tolerance} of ${expected}`,
  );
}

function createFakePopup() {
  return new FakeElement();
}

function createFakeCanvas(id) {
  const canvas = new FakeElement({ id, tagName: 'canvas' });
  const ctx = { canvas };
  canvas.getContext = () => ctx;
  return canvas;
}

function createFakeAdsStatsDom(initialMode) {
  const body = new FakeElement({ tagName: 'body' });
  const elements = {
    campaignSelector: new FakeElement({ id: 'campaignSelector' }),
    modeSelector: new FakeElement({ id: 'modeSelector' }),
    'stat-impressions': new FakeElement({ id: 'stat-impressions' }),
    'stat-clicks': new FakeElement({ id: 'stat-clicks' }),
    'stat-cost': new FakeElement({ id: 'stat-cost' }),
    'stat-profit-before-ads-ads': new FakeElement({ id: 'stat-profit-before-ads-ads' }),
    'stat-profit-before-ads-reconciled': new FakeElement({
      id: 'stat-profit-before-ads-reconciled',
    }),
    'stat-gross-profit': new FakeElement({ id: 'stat-gross-profit' }),
    'stat-ctr': new FakeElement({ id: 'stat-ctr' }),
    'stat-cpc': new FakeElement({ id: 'stat-cpc' }),
    'stat-conversion-rate': new FakeElement({ id: 'stat-conversion-rate' }),
    reconciledProfitTimelineChart: createFakeCanvas('reconciledProfitTimelineChart'),
    reconciledPoasTimelineChart: createFakeCanvas('reconciledPoasTimelineChart'),
    cpcAndConversionRateChart: createFakeCanvas('cpcAndConversionRateChart'),
    ctrChart: createFakeCanvas('ctrChart'),
    impressionsAndClicksChart: createFakeCanvas('impressionsAndClicksChart'),
    adsProfitBreakdownChart: createFakeCanvas('adsProfitBreakdownChart'),
    salesBreakdownChart: createFakeCanvas('salesBreakdownChart'),
    kenpBreakdownChart: createFakeCanvas('kenpBreakdownChart'),
  };
  elements.campaignSelector.value = 'All';
  elements.modeSelector.value = initialMode;

  Object.values(elements).forEach((element) => append(body, element));

  const document = new FakeDocument(body);
  return { document, elements };
}

function createFakeChartData() {
  return {
    labels: ['2026-02-22', '2026-02-23'],
    impressions: [100, 120],
    clicks: [10, 12],
    cost: [20, 24],
    sales_usd: [50, 60],
    units_sold: [2, 3],
    gross_profit_before_ads_usd: [40, 48],
    gross_profit_usd: [20, 24],
    daily_campaigns: {
      '2026-02-22': [],
      '2026-02-23': [],
    },
  };
}

function createFakeReconciledChartData() {
  return {
    labels: ['2026-02-22', '2026-02-23'],
    gross_profit_before_ads_usd: [35, 45],
    reconciled_matched_profit_before_ads_usd: [40, 52],
    organic_profit_usd: [5, 7],
    matched_ads_sales_count: [2, 3],
    organic_sales_count: [1, 2],
    reconciled_sales_count: [3, 5],
    unmatched_ads_sales_count: [0, 3],
    ads_sales_details: [
      [
        {
          country_code: 'US',
          asin: 'B0G9765J19',
          book_key: 'animal-jokes',
          book_format: 'Ebook',
          count: 2,
        },
        {
          country_code: 'US',
          asin: 'B0G9765J19',
          book_key: 'animal-jokes',
          book_format: 'Ebook',
          count: 300,
          is_kenp: true,
        },
      ],
      [
        {
          country_code: 'US',
          asin: 'B0G9765J19',
          book_key: 'animal-jokes',
          book_format: 'Ebook',
          count: 2,
        },
        {
          country_code: 'GB',
          asin: 'B0GNMFVYC5',
          book_key: 'valentine-jokes',
          book_format: 'Ebook',
          count: 4,
        },
        {
          country_code: 'GB',
          asin: 'B0GNMFVYC5',
          book_key: 'valentine-jokes',
          book_format: 'Ebook',
          count: 450,
          is_kenp: true,
        },
      ],
    ],
    matched_ads_sales_details: [
      [
        {
          country_code: 'US',
          asin: 'B0G9765J19',
          book_key: 'animal-jokes',
          book_format: 'Ebook',
          count: 2,
        },
        {
          country_code: 'US',
          asin: 'B0G9765J19',
          book_key: 'animal-jokes',
          book_format: 'Ebook',
          count: 200,
          is_kenp: true,
        },
      ],
      [
        {
          country_code: 'US',
          asin: 'B0G9765J19',
          book_key: 'animal-jokes',
          book_format: 'Ebook',
          count: 2,
        },
        {
          country_code: 'GB',
          asin: 'B0GNMFVYC5',
          book_key: 'valentine-jokes',
          book_format: 'Ebook',
          count: 1,
        },
        {
          country_code: 'GB',
          asin: 'B0GNMFVYC5',
          book_key: 'valentine-jokes',
          book_format: 'Ebook',
          count: 250,
          is_kenp: true,
        },
      ],
    ],
    reconciled_sales_details: [
      [
        {
          country_code: 'US',
          asin: 'B0G9765J19',
          book_key: 'animal-jokes',
          book_format: 'Ebook',
          count: 3,
        },
        {
          country_code: 'US',
          asin: 'B0G9765J19',
          book_key: 'animal-jokes',
          book_format: 'Ebook',
          count: 220,
          is_kenp: true,
        },
      ],
      [
        {
          country_code: 'US',
          asin: 'B0G9765J19',
          book_key: 'animal-jokes',
          book_format: 'Ebook',
          count: 3,
        },
        {
          country_code: 'GB',
          asin: 'B0GNMFVYC5',
          book_key: 'valentine-jokes',
          book_format: 'Ebook',
          count: 2,
        },
        {
          country_code: 'GB',
          asin: 'B0GNMFVYC5',
          book_key: 'valentine-jokes',
          book_format: 'Ebook',
          count: 300,
          is_kenp: true,
        },
      ],
    ],
    unmatched_ads_sales_details: [
      [],
      [
        {
          country_code: 'US',
          asin: 'B0G9765J19',
          book_key: 'animal-jokes',
          book_format: 'Ebook',
          count: 2,
        },
        {
          country_code: 'GB',
          asin: 'B0GNMFVYC5',
          book_key: 'valentine-jokes',
          book_format: 'Ebook',
          count: 1,
        },
        {
          country_code: 'GB',
          asin: 'B0GNMFVYC5',
          book_key: 'valentine-jokes',
          book_format: 'Ebook',
          count: 120,
          is_kenp: true,
        },
      ],
    ],
    ads_profit_details: [
      [
        {
          country_code: 'US',
          asin: 'B0G9765J19',
          book_key: 'animal-jokes',
          book_format: 'Ebook',
          amount_usd: 40.0,
        },
        {
          country_code: 'US',
          asin: 'B0G9765J19',
          book_key: 'animal-jokes',
          book_format: 'Ebook',
          amount_usd: 5.0,
          is_kenp: true,
          kenp_pages_count: 300,
        },
      ],
      [
        {
          country_code: 'US',
          asin: 'B0G9765J19',
          book_key: 'animal-jokes',
          book_format: 'Ebook',
          amount_usd: 18.0,
        },
        {
          country_code: 'GB',
          asin: 'B0GNMFVYC5',
          book_key: 'valentine-jokes',
          book_format: 'Ebook',
          amount_usd: 30.0,
        },
        {
          country_code: 'GB',
          asin: 'B0GNMFVYC5',
          book_key: 'valentine-jokes',
          book_format: 'Ebook',
          amount_usd: 8.0,
          is_kenp: true,
          kenp_pages_count: 450,
        },
      ],
    ],
    matched_ads_profit_details: [
      [
        {
          country_code: 'US',
          asin: 'B0G9765J19',
          book_key: 'animal-jokes',
          book_format: 'Ebook',
          amount_usd: 35.0,
        },
        {
          country_code: 'US',
          asin: 'B0G9765J19',
          book_key: 'animal-jokes',
          book_format: 'Ebook',
          amount_usd: 5.0,
          is_kenp: true,
          kenp_pages_count: 200,
        },
      ],
      [
        {
          country_code: 'US',
          asin: 'B0G9765J19',
          book_key: 'animal-jokes',
          book_format: 'Ebook',
          amount_usd: 12.0,
        },
        {
          country_code: 'GB',
          asin: 'B0GNMFVYC5',
          book_key: 'valentine-jokes',
          book_format: 'Ebook',
          amount_usd: 20.0,
        },
        {
          country_code: 'GB',
          asin: 'B0GNMFVYC5',
          book_key: 'valentine-jokes',
          book_format: 'Ebook',
          amount_usd: 6.0,
          is_kenp: true,
          kenp_pages_count: 250,
        },
      ],
    ],
    reconciled_matched_profit_details: [
      [
        {
          country_code: 'US',
          asin: 'B0G9765J19',
          book_key: 'animal-jokes',
          book_format: 'Ebook',
          amount_usd: 40.0,
        },
        {
          country_code: 'US',
          asin: 'B0G9765J19',
          book_key: 'animal-jokes',
          book_format: 'Ebook',
          amount_usd: 5.0,
          is_kenp: true,
          kenp_pages_count: 220,
        },
      ],
      [
        {
          country_code: 'US',
          asin: 'B0G9765J19',
          book_key: 'animal-jokes',
          book_format: 'Ebook',
          amount_usd: 18.0,
        },
        {
          country_code: 'GB',
          asin: 'B0GNMFVYC5',
          book_key: 'valentine-jokes',
          book_format: 'Ebook',
          amount_usd: 27.0,
        },
        {
          country_code: 'GB',
          asin: 'B0GNMFVYC5',
          book_key: 'valentine-jokes',
          book_format: 'Ebook',
          amount_usd: 6.0,
          is_kenp: true,
          kenp_pages_count: 300,
        },
      ],
    ],
    profit_before_ads_reconciled_details: [
      [
        {
          country_code: 'US',
          asin: 'B0G9765J19',
          book_key: 'animal-jokes',
          book_format: 'Ebook',
          amount_usd: 40.0,
        },
        {
          country_code: 'US',
          asin: 'B0G9765J19',
          book_key: 'animal-jokes',
          book_format: 'Ebook',
          amount_usd: 5.0,
          is_kenp: true,
          kenp_pages_count: 300,
        },
      ],
      [
        {
          country_code: 'US',
          asin: 'B0G9765J19',
          book_key: 'animal-jokes',
          book_format: 'Ebook',
          amount_usd: 24.0,
        },
        {
          country_code: 'GB',
          asin: 'B0GNMFVYC5',
          book_key: 'valentine-jokes',
          book_format: 'Ebook',
          amount_usd: 30.0,
        },
        {
          country_code: 'GB',
          asin: 'B0GNMFVYC5',
          book_key: 'valentine-jokes',
          book_format: 'Ebook',
          amount_usd: 8.0,
          is_kenp: true,
          kenp_pages_count: 450,
        },
      ],
    ],
    unmatched_ads_profit_details: [
      [
        {
          country_code: 'US',
          asin: 'B0G9765J19',
          book_key: 'animal-jokes',
          book_format: 'Ebook',
          amount_usd: 5.0,
        },
      ],
      [
        {
          country_code: 'US',
          asin: 'B0G9765J19',
          book_key: 'animal-jokes',
          book_format: 'Ebook',
          amount_usd: 6.0,
        },
        {
          country_code: 'GB',
          asin: 'B0GNMFVYC5',
          book_key: 'valentine-jokes',
          book_format: 'Ebook',
          amount_usd: 10.0,
        },
        {
          country_code: 'GB',
          asin: 'B0GNMFVYC5',
          book_key: 'valentine-jokes',
          book_format: 'Ebook',
          amount_usd: 2.0,
          is_kenp: true,
          kenp_pages_count: 120,
        },
      ],
    ],
  };
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

test('formatUnmatchedAdsTooltipLine formats asin, book key, format, and count', () => {
  assert.equal(
    formatUnmatchedAdsTooltipLine({
      country_code: 'US',
      asin: 'B0G9765J19',
      book_key: 'animal-jokes',
      book_format: 'Ebook',
      count: 2,
    }),
    'US B0G9765J19 - animal-jokes (Ebook): 2',
  );
});

test('reserveScaleWidth preserves larger widths and raises smaller widths', () => {
  const narrowScale = { width: 18 };
  reserveScaleWidth(narrowScale, 56);
  assert.equal(narrowScale.width, 56);

  const wideScale = { width: 72 };
  reserveScaleWidth(wideScale, 56);
  assert.equal(wideScale.width, 72);
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

test('buildReconciledChartStats exposes ads and reconciled profit series for campaign All', () => {
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
    reconciled_matched_profit_before_ads_usd: [6, 14],
    organic_profit_usd: [1, 3],
    matched_ads_sales_count: [1, 2],
    organic_sales_count: [1, 1],
    reconciled_sales_count: [2, 3],
    unmatched_ads_sales_count: [1, 3],
    ads_sales_details: [
      [
        {
          country_code: 'US',
          asin: 'B0A',
          book_key: 'a',
          book_format: 'Ebook',
          count: 2,
        },
      ],
      [
        {
          country_code: 'US',
          asin: 'B0B',
          book_key: 'b',
          book_format: 'Paperback',
          count: 5,
        },
      ],
    ],
    matched_ads_sales_details: [
      [
        {
          country_code: 'US',
          asin: 'B0A',
          book_key: 'a',
          book_format: 'Ebook',
          count: 1,
        },
      ],
      [
        {
          country_code: 'US',
          asin: 'B0B',
          book_key: 'b',
          book_format: 'Paperback',
          count: 2,
        },
      ],
    ],
    unmatched_ads_sales_details: [
      [
        {
          country_code: 'US',
          asin: 'B0A',
          book_key: 'a',
          book_format: 'Ebook',
          count: 1,
        },
      ],
      [
        {
          country_code: 'US',
          asin: 'B0B',
          book_key: 'b',
          book_format: 'Paperback',
          count: 3,
        },
      ],
    ],
    ads_profit_details: [
      [
        {
          country_code: 'US',
          asin: 'B0A',
          book_key: 'a',
          book_format: 'Ebook',
          amount_usd: 6.0,
        },
      ],
      [
        {
          country_code: 'US',
          asin: 'B0B',
          book_key: 'b',
          book_format: 'Paperback',
          amount_usd: 15.0,
        },
      ],
    ],
    matched_ads_profit_details: [
      [
        {
          country_code: 'US',
          asin: 'B0A',
          book_key: 'a',
          book_format: 'Ebook',
          amount_usd: 5.0,
        },
      ],
      [
        {
          country_code: 'US',
          asin: 'B0B',
          book_key: 'b',
          book_format: 'Paperback',
          amount_usd: 11.0,
        },
      ],
    ],
    unmatched_ads_profit_details: [
      [
        {
          country_code: 'US',
          asin: 'B0A',
          book_key: 'a',
          book_format: 'Ebook',
          amount_usd: 1.0,
        },
      ],
      [
        {
          country_code: 'US',
          asin: 'B0B',
          book_key: 'b',
          book_format: 'Paperback',
          amount_usd: 4.0,
        },
      ],
    ],
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
  assert.deepEqual(timeline.ads_profit_before_ads_usd, [6, 15]);
  assert.deepEqual(timeline.matched_ads_profit_before_ads_usd, [5, 11]);
  assert.deepEqual(timeline.gross_profit_before_ads_usd, [5, 11]);
  assert.deepEqual(timeline.reconciled_matched_profit_before_ads_usd, [6, 14]);
  assert.deepEqual(timeline.reconciled_profit_before_ads_usd, [7, 18]);
  assertClose(timeline.poas[0], 6 / 4);
  assertClose(timeline.poas[1], 15 / 10);
  assertClose(timeline.tpoas[0], (6 + 1) / 4);
  assertClose(timeline.tpoas[1], (15 + 3) / 10);
  assert.deepEqual(timeline.organic_profit_usd, [1, 3]);
  assert.deepEqual(timeline.unmatched_pre_ad_profit_usd, [1, 4]);
  assert.deepEqual(timeline.matched_ads_sales_count, [1, 2]);
  assert.deepEqual(timeline.organic_sales_count, [1, 1]);
  assert.deepEqual(timeline.reconciled_sales_count, [2, 3]);
  assert.deepEqual(timeline.unmatched_ads_sales_count, [1, 3]);
  assert.deepEqual(timeline.gross_profit_usd, [3, 8]);
  assertClose(timeline.totals.ads_profit_before_ads_usd, 21);
  assertClose(timeline.totals.matched_ads_profit_before_ads_usd, 16);
  assertClose(timeline.totals.reconciled_profit_before_ads_usd, 25);
  assertClose(timeline.totals.unmatched_pre_ad_profit_usd, 5);
  assertClose(timeline.totals.gross_profit_usd, 11);

  assert.deepEqual(daysOfWeek.labels, DAYS_OF_WEEK_LABELS);
  assertClose(daysOfWeek.cost[0], 4); // Sunday
  assertClose(daysOfWeek.cost[1], 10); // Monday
  assertClose(daysOfWeek.ads_profit_before_ads_usd[0], 6);
  assertClose(daysOfWeek.ads_profit_before_ads_usd[1], 15);
  assertClose(daysOfWeek.reconciled_profit_before_ads_usd[0], 7);
  assertClose(daysOfWeek.reconciled_profit_before_ads_usd[1], 18);
  assertClose(daysOfWeek.poas[0], 6 / 4);
  assertClose(daysOfWeek.poas[1], 15 / 10);
  assertClose(daysOfWeek.tpoas[0], (6 + 1) / 4);
  assertClose(daysOfWeek.tpoas[1], (15 + 3) / 10);
  assertClose(daysOfWeek.unmatched_pre_ad_profit_usd[0], 1);
  assertClose(daysOfWeek.unmatched_pre_ad_profit_usd[1], 4);
  assertClose(daysOfWeek.gross_profit_usd[0], 3);
  assertClose(daysOfWeek.gross_profit_usd[1], 8);
});

test('buildReconciledChartStats prefers profit detail totals for dollar series when present', () => {
  const chartData = {
    labels: ['2026-02-22'],
    impressions: [10],
    clicks: [2],
    cost: [4],
    sales_usd: [8],
    units_sold: [1],
    gross_profit_before_ads_usd: [999], // Intentionally different from detail sum.
    gross_profit_usd: [2],
    daily_campaigns: {
      '2026-02-22': [],
    },
  };
  const reconciledChartData = {
    labels: ['2026-02-22'],
    gross_profit_before_ads_usd: [111],
    reconciled_matched_profit_before_ads_usd: [222],
    organic_profit_usd: [3],
    matched_ads_sales_count: [1],
    organic_sales_count: [1],
    reconciled_sales_count: [2],
    unmatched_ads_sales_count: [0],
    ads_profit_details: [[
      {
        country_code: 'US',
        asin: 'B0A',
        book_key: 'a',
        book_format: 'Ebook',
        amount_usd: 6.0,
      },
      {
        country_code: 'US',
        asin: 'B0A',
        book_key: 'a',
        book_format: 'Ebook',
        amount_usd: 2.0,
        is_kenp: true,
        kenp_pages_count: 100,
      },
    ]],
    matched_ads_profit_details: [[
      {
        country_code: 'US',
        asin: 'B0A',
        book_key: 'a',
        book_format: 'Ebook',
        amount_usd: 5.0,
      },
      {
        country_code: 'US',
        asin: 'B0A',
        book_key: 'a',
        book_format: 'Ebook',
        amount_usd: 1.0,
        is_kenp: true,
        kenp_pages_count: 80,
      },
    ]],
    reconciled_matched_profit_details: [[
      {
        country_code: 'US',
        asin: 'B0A',
        book_key: 'a',
        book_format: 'Ebook',
        amount_usd: 7.5,
      },
    ]],
    profit_before_ads_reconciled_details: [[
      {
        country_code: 'US',
        asin: 'B0A',
        book_key: 'a',
        book_format: 'Ebook',
        amount_usd: 9.5,
      },
    ]],
  };

  const timeline = buildReconciledChartStats(
    chartData,
    'All',
    'Timeline',
    reconciledChartData,
  );

  assert.deepEqual(timeline.ads_profit_before_ads_usd, [8]);
  assert.deepEqual(timeline.matched_ads_profit_before_ads_usd, [6]);
  assert.deepEqual(timeline.reconciled_matched_profit_before_ads_usd, [7.5]);
  assert.deepEqual(timeline.reconciled_profit_before_ads_usd, [9.5]);
  assert.deepEqual(timeline.unmatched_pre_ad_profit_usd, [2]);
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
  assert.deepEqual(reconciled.ads_profit_before_ads_usd, []);
  assert.deepEqual(reconciled.reconciled_profit_before_ads_usd, []);
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

test('copyTextToClipboard uses navigator clipboard when available', async () => {
  const originalNavigator = global.navigator;
  const writes = [];
  global.navigator = {
    clipboard: {
      writeText: async (value) => {
        writes.push(value);
      },
    },
  };

  try {
    const copied = await copyTextToClipboard('alpha,beta');
    assert.equal(copied, true);
    assert.deepEqual(writes, ['alpha,beta']);
  } finally {
    global.navigator = originalNavigator;
  }
});

test('showCopyFeedback keeps confirmation visible, then fades and hides it', () => {
  const originalSetTimeout = global.setTimeout;
  const originalClearTimeout = global.clearTimeout;
  const clock = createFakeClock();
  const popup = createFakePopup();

  global.setTimeout = clock.setTimeout;
  global.clearTimeout = clock.clearTimeout;

  try {
    showCopyFeedback(popup, {
      visibleDurationMs: 40,
      fadeDurationMs: 30,
    });

    assert.equal(popup.textContent, 'Copied to clipboard!');
    assert.equal(popup.getAttribute('aria-hidden'), 'false');
    assert.equal(popup.classList.contains('is-visible'), true);
    assert.equal(popup.classList.contains('is-fading'), false);

    clock.tick(50);
    assert.equal(popup.classList.contains('is-visible'), true);
    assert.equal(popup.classList.contains('is-fading'), true);

    clock.tick(40);
    assert.equal(popup.classList.contains('is-visible'), false);
    assert.equal(popup.classList.contains('is-fading'), false);
    assert.equal(popup.getAttribute('aria-hidden'), 'true');
  } finally {
    global.setTimeout = originalSetTimeout;
    global.clearTimeout = originalClearTimeout;
  }
});

test('initAdsStatsPage switches chart configs from line to bar in Days of Week mode', () => {
  const originalWindow = global.window;
  const originalDocument = global.document;
  const chartCalls = [];
  const { document, elements } = createFakeAdsStatsDom(TIMELINE_MODE);

  function FakeChart(ctx, config) {
    chartCalls.push({
      canvasId: ctx.canvas.id,
      config,
    });
    return {
      destroy: () => {},
      canvas: ctx.canvas,
      data: config.data,
      options: config.options,
    };
  }

  global.document = document;
  global.window = {
    document,
    Chart: FakeChart,
  };

  try {
    initAdsStatsPage({
      chartData: createFakeChartData(),
      reconciledClickDateChartData: createFakeReconciledChartData(),
      adsEvents: [],
    });

    assert.equal(chartCalls.length, 8);
    assert.deepEqual(
      chartCalls.map((call) => call.config.type),
      Array(8).fill('line'),
    );

    elements.modeSelector.value = DAYS_OF_WEEK_MODE;
    elements.modeSelector.dispatch('change');

    assert.equal(chartCalls.length, 16);
    assert.deepEqual(
      chartCalls.slice(-8).map((call) => call.config.type),
      Array(8).fill('bar'),
    );
  } finally {
    global.window = originalWindow;
    global.document = originalDocument;
  }
});

test('initAdsStatsPage renders Sales and Profit breakdown datasets with detailed tooltip lines', () => {
  const originalWindow = global.window;
  const originalDocument = global.document;
  const chartCalls = [];
  const { document } = createFakeAdsStatsDom(TIMELINE_MODE);

  function FakeChart(ctx, config) {
    chartCalls.push({
      canvasId: ctx.canvas.id,
      config,
    });
    return {
      destroy: () => {},
      canvas: ctx.canvas,
      data: config.data,
      options: config.options,
    };
  }

  global.document = document;
  global.window = {
    document,
    Chart: FakeChart,
  };

  try {
    initAdsStatsPage({
      chartData: createFakeChartData(),
      reconciledClickDateChartData: createFakeReconciledChartData(),
      adsEvents: [],
    });

    const adsProfitChartCall = chartCalls.find((call) => call.canvasId === 'adsProfitBreakdownChart');
    assert.ok(adsProfitChartCall);
    const adsProfitDatasetLabels = adsProfitChartCall.config.data.datasets.map(
      (dataset) => dataset.label,
    );
    assert.deepEqual(adsProfitDatasetLabels, [
      'Profit Before Ads (ads)',
      'Matched Ads Profit',
      'Unmatched Ad Profit',
      'Reconciled Profit',
    ]);
    assert.equal(adsProfitChartCall.config.data.datasets[0].borderColor, '#ef6c00');
    assert.equal(adsProfitChartCall.config.data.datasets[1].borderColor, '#1565c0');
    assert.equal(adsProfitChartCall.config.data.datasets[2].borderColor, '#c62828');
    assert.equal(adsProfitChartCall.config.data.datasets[3].borderColor, '#2e7d32');
    assert.deepEqual(
      adsProfitChartCall.config.data.datasets[0].tooltipLinesByIndex[0],
      [
        'US B0G9765J19 - animal-jokes (Ebook): $40.00',
        'US B0G9765J19 - animal-jokes (Ebook KENP): $5.00 (300)',
      ],
    );
    assert.deepEqual(
      adsProfitChartCall.config.data.datasets[1].tooltipLinesByIndex[1],
      [
        'US B0G9765J19 - animal-jokes (Ebook): $12.00',
        'GB B0GNMFVYC5 - valentine-jokes (Ebook): $20.00',
        'GB B0GNMFVYC5 - valentine-jokes (Ebook KENP): $6.00 (250)',
      ],
    );
    assert.deepEqual(
      adsProfitChartCall.config.data.datasets[3].tooltipLinesByIndex[1],
      [
        'US B0G9765J19 - animal-jokes (Ebook): $18.00',
        'GB B0GNMFVYC5 - valentine-jokes (Ebook): $27.00',
        'GB B0GNMFVYC5 - valentine-jokes (Ebook KENP): $6.00 (300)',
      ],
    );
    assert.equal(
      adsProfitChartCall.config.data.datasets[2].tooltipLinesByIndex,
      undefined,
    );

    const salesBreakdownChartCall = chartCalls.find((call) => call.canvasId === 'salesBreakdownChart');
    assert.ok(salesBreakdownChartCall);

    const datasets = salesBreakdownChartCall.config.data.datasets;
    assert.deepEqual(datasets.map((dataset) => dataset.label), [
      'Ads Sales (ads)',
      'Matched Ads Sales',
      'Unmatched Ads Sales',
      'Reconciled Sales',
    ]);
    assert.equal(datasets[2].borderColor, '#c62828');
    assert.equal(datasets[2].order, -10);
    assert.equal(datasets[0].borderColor, '#ef6c00');
    assert.equal(datasets[1].borderColor, '#1565c0');
    assert.equal(datasets[3].borderColor, '#2e7d32');
    assert.deepEqual(datasets[0].data, [2, 3]);
    assert.deepEqual(datasets[1].data, [2, 3]);
    assert.deepEqual(datasets[2].data, [0, 3]);
    assert.deepEqual(datasets[3].data, [3, 5]);
    assert.deepEqual(datasets[0].tooltipLinesByIndex[0], [
      'US B0G9765J19 - animal-jokes (Ebook): 2',
    ]);
    assert.deepEqual(datasets[1].tooltipLinesByIndex[1], [
      'US B0G9765J19 - animal-jokes (Ebook): 2',
      'GB B0GNMFVYC5 - valentine-jokes (Ebook): 1',
    ]);
    assert.deepEqual(datasets[2].tooltipLinesByIndex[0], []);
    assert.deepEqual(
      datasets[2].tooltipLinesByIndex[1],
      [
        'US B0G9765J19 - animal-jokes (Ebook): 2',
        'GB B0GNMFVYC5 - valentine-jokes (Ebook): 1',
      ],
    );
    assert.deepEqual(
      datasets[3].tooltipLinesByIndex[1],
      [
        'US B0G9765J19 - animal-jokes (Ebook): 3',
        'GB B0GNMFVYC5 - valentine-jokes (Ebook): 2',
      ],
    );

    const tooltipCallbacks = salesBreakdownChartCall.config.options.plugins.tooltip.callbacks;
    assert.deepEqual(
      tooltipCallbacks.afterLabel({
        dataset: datasets[2],
        dataIndex: 1,
      }),
      [
        'US B0G9765J19 - animal-jokes (Ebook): 2',
        'GB B0GNMFVYC5 - valentine-jokes (Ebook): 1',
      ],
    );

    const kenpBreakdownChartCall = chartCalls.find((call) => call.canvasId === 'kenpBreakdownChart');
    assert.ok(kenpBreakdownChartCall);
    const kenpDatasets = kenpBreakdownChartCall.config.data.datasets;
    assert.deepEqual(kenpDatasets.map((dataset) => dataset.label), [
      'Ads KENP Pages (ads)',
      'Matched KENP Pages',
      'Unmatched KENP Pages',
      'Reconciled KENP Pages',
    ]);
    assert.equal(kenpDatasets[0].borderColor, '#ef6c00');
    assert.equal(kenpDatasets[1].borderColor, '#1565c0');
    assert.equal(kenpDatasets[2].borderColor, '#c62828');
    assert.equal(kenpDatasets[3].borderColor, '#2e7d32');
    assert.deepEqual(kenpDatasets[0].data, [300, 450]);
    assert.deepEqual(kenpDatasets[1].data, [200, 250]);
    assert.deepEqual(kenpDatasets[2].data, [0, 120]);
    assert.deepEqual(kenpDatasets[3].data, [220, 300]);
    assert.deepEqual(kenpDatasets[0].tooltipLinesByIndex[0], [
      'US B0G9765J19 - animal-jokes (Ebook KENP Pages): 300',
    ]);
    assert.deepEqual(kenpDatasets[2].tooltipLinesByIndex[1], [
      'GB B0GNMFVYC5 - valentine-jokes (Ebook KENP Pages): 120',
    ]);

    const reconciledProfitChartCall = chartCalls.find(
      (call) => call.canvasId === 'reconciledProfitTimelineChart',
    );
    assert.ok(reconciledProfitChartCall);
    const reconciledDatasets = reconciledProfitChartCall.config.data.datasets;
    assert.deepEqual(
      reconciledDatasets[1].tooltipLinesByIndex[0],
      [
        'US B0G9765J19 - animal-jokes (Ebook): $40.00',
        'US B0G9765J19 - animal-jokes (Ebook KENP): $5.00 (300)',
      ],
    );
    assert.deepEqual(
      reconciledDatasets[2].tooltipLinesByIndex[1],
      [
        'US B0G9765J19 - animal-jokes (Ebook): $24.00',
        'GB B0GNMFVYC5 - valentine-jokes (Ebook): $30.00',
        'GB B0GNMFVYC5 - valentine-jokes (Ebook KENP): $8.00 (450)',
      ],
    );
  } finally {
    global.window = originalWindow;
    global.document = originalDocument;
  }
});

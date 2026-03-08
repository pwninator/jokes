const assert = require('node:assert/strict');
const test = require('node:test');

const {
  FakeDocument,
  FakeElement,
  append,
  createFetchMock,
  createFakeClock,
} = require('./test_utils.js');
const {
  ADS_STATS_PAGE_DATA_ELEMENT_ID,
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
  normalizePlacementRow,
  normalizeSearchTermRow,
  groupAdsEventsByDate,
  buildPlacementAggregates,
  buildSearchTermAggregates,
  filterSearchTermAggregates,
  getAdsEventTooltipLines,
  getDailyStatsForCampaign,
  initAdsStatsPage,
  readAdsStatsPageOptionsFromDocument,
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
  body.clientWidth = 960;
  body.clientHeight = 720;
  const elements = {
    adsStatsPageData: new FakeElement({
      id: ADS_STATS_PAGE_DATA_ELEMENT_ID,
      tagName: 'script',
    }),
    campaignSelector: new FakeElement({ id: 'campaignSelector' }),
    modeSelector: new FakeElement({ id: 'modeSelector' }),
    adsStatsModeTimelineButton: new FakeElement({
      id: 'adsStatsModeTimelineButton',
      tagName: 'button',
    }),
    adsStatsModeDaysOfWeekButton: new FakeElement({
      id: 'adsStatsModeDaysOfWeekButton',
      tagName: 'button',
    }),
    adsStatsCreateEventToggleButton: new FakeElement({
      id: 'adsStatsCreateEventToggleButton',
      tagName: 'button',
    }),
    adsStatsCreateEventForm: new FakeElement({
      id: 'adsStatsCreateEventForm',
      tagName: 'form',
    }),
    adsStatsEventDateInput: new FakeElement({
      id: 'adsStatsEventDateInput',
      tagName: 'input',
    }),
    adsStatsEventTitleInput: new FakeElement({
      id: 'adsStatsEventTitleInput',
      tagName: 'input',
    }),
    adsStatsEventCreateButton: new FakeElement({
      id: 'adsStatsEventCreateButton',
      tagName: 'button',
    }),
    adsStatsCreateEventStatus: new FakeElement({
      id: 'adsStatsCreateEventStatus',
      tagName: 'span',
    }),
    kdpUploadForm: new FakeElement({ id: 'kdpUploadForm', tagName: 'form' }),
    kdpFileInput: new FakeElement({ id: 'kdpFileInput', tagName: 'input' }),
    kdpUploadStatus: new FakeElement({ id: 'kdpUploadStatus', tagName: 'span' }),
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
    placementCampaignSelector: new FakeElement({ id: 'placementCampaignSelector', tagName: 'select' }),
    placementPlacementSelector: new FakeElement({ id: 'placementPlacementSelector', tagName: 'select' }),
    placementTextFilter: new FakeElement({ id: 'placementTextFilter', tagName: 'input' }),
    placementDimensionChips: new FakeElement({ id: 'placementDimensionChips' }),
    placementInsightsTableHead: new FakeElement({ id: 'placementInsightsTableHead', tagName: 'thead' }),
    placementInsightsTableBody: new FakeElement({ id: 'placementInsightsTableBody', tagName: 'tbody' }),
    placementInsightsEmptyState: new FakeElement({ id: 'placementInsightsEmptyState', tagName: 'p' }),
    placementTrendChart: createFakeCanvas('placementTrendChart'),
    placementSummaryRows: new FakeElement({ id: 'placementSummaryRows' }),
    placementSummaryClicks: new FakeElement({ id: 'placementSummaryClicks' }),
    placementSummaryCost: new FakeElement({ id: 'placementSummaryCost' }),
    placementSummarySales: new FakeElement({ id: 'placementSummarySales' }),
    placementSummaryAcos: new FakeElement({ id: 'placementSummaryAcos' }),
    placementSummaryRoas: new FakeElement({ id: 'placementSummaryRoas' }),
    searchTermCampaignSelector: new FakeElement({ id: 'searchTermCampaignSelector', tagName: 'select' }),
    searchTermKeywordTypeSelector: new FakeElement({
      id: 'searchTermKeywordTypeSelector',
      tagName: 'select',
    }),
    searchTermMatchTypeSelector: new FakeElement({
      id: 'searchTermMatchTypeSelector',
      tagName: 'select',
    }),
    searchTermTextFilter: new FakeElement({ id: 'searchTermTextFilter', tagName: 'input' }),
    searchTermDimensionChips: new FakeElement({ id: 'searchTermDimensionChips' }),
    searchTermInsightsTableHead: new FakeElement({ id: 'searchTermInsightsTableHead', tagName: 'thead' }),
    searchTermInsightsTableBody: new FakeElement({ id: 'searchTermInsightsTableBody', tagName: 'tbody' }),
    searchTermInsightsEmptyState: new FakeElement({ id: 'searchTermInsightsEmptyState', tagName: 'p' }),
    searchTermTrendChart: createFakeCanvas('searchTermTrendChart'),
    searchTermSummaryRows: new FakeElement({ id: 'searchTermSummaryRows' }),
    searchTermSummaryClicks: new FakeElement({ id: 'searchTermSummaryClicks' }),
    searchTermSummaryCost: new FakeElement({ id: 'searchTermSummaryCost' }),
    searchTermSummarySales: new FakeElement({ id: 'searchTermSummarySales' }),
    searchTermSummaryAcos: new FakeElement({ id: 'searchTermSummaryAcos' }),
    searchTermSummaryRoas: new FakeElement({ id: 'searchTermSummaryRoas' }),
  };
  elements.campaignSelector.value = 'All';
  elements.modeSelector.value = initialMode;
  elements.adsStatsModeTimelineButton.setAttribute('aria-pressed', 'true');
  elements.adsStatsModeDaysOfWeekButton.setAttribute('aria-pressed', 'false');
  elements.adsStatsCreateEventForm.hidden = true;
  elements.placementCampaignSelector.value = 'All';
  elements.placementPlacementSelector.value = 'All';
  elements.searchTermCampaignSelector.value = 'All';
  elements.searchTermKeywordTypeSelector.value = 'All';
  elements.searchTermMatchTypeSelector.value = 'All';
  append(elements.adsStatsCreateEventForm, elements.adsStatsEventDateInput);
  append(elements.adsStatsCreateEventForm, elements.adsStatsEventTitleInput);
  append(elements.adsStatsCreateEventForm, elements.adsStatsEventCreateButton);
  append(elements.adsStatsCreateEventForm, elements.adsStatsCreateEventStatus);

  const placementChipConfigs = [
    { key: 'placement_classification', pressed: true },
    { key: 'campaign_name', pressed: false },
  ];
  placementChipConfigs.forEach((config) => {
    const chip = new FakeElement({
      tagName: 'button',
      className: 'placement-dimension-chip',
    });
    chip.setAttribute('data-dimension-key', config.key);
    chip.setAttribute('aria-pressed', config.pressed ? 'true' : 'false');
    chip.textContent = config.key;
    append(elements.placementDimensionChips, chip);
  });

  const dimensionChipConfigs = [
    { key: 'campaign_name', pressed: false },
    { key: 'search_term', pressed: true },
    { key: 'targeting', pressed: false },
    { key: 'keyword', pressed: false },
    { key: 'keyword_type', pressed: false },
    { key: 'match_type', pressed: false },
  ];
  dimensionChipConfigs.forEach((config) => {
    const chip = new FakeElement({
      tagName: 'button',
      className: 'search-term-dimension-chip',
    });
    chip.setAttribute('data-dimension-key', config.key);
    chip.setAttribute('aria-pressed', config.pressed ? 'true' : 'false');
    chip.textContent = config.key;
    append(elements.searchTermDimensionChips, chip);
  });

  Object.values(elements).forEach((element) => append(body, element));

  const document = new FakeDocument(body);
  return { document, elements };
}

function setEmbeddedAdsStatsPageData(elements, data) {
  elements.adsStatsPageData.textContent = JSON.stringify(data);
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

function createFakeSearchTermData() {
  return {
    labels: ['2026-02-22', '2026-02-23'],
    rows: [
      {
        date: '2026-02-22',
        campaign_name: 'Campaign A',
        search_term: 'alpha',
        keyword_type: 'EXACT',
        match_type: 'EXACT',
        keyword: 'alpha keyword',
        targeting: '',
        impressions: 10,
        clicks: 1,
        cost_usd: 1,
        sales14d_usd: 10,
        purchases14d: 1,
      },
      {
        date: '2026-02-23',
        campaign_name: 'Campaign B',
        search_term: 'alpha',
        keyword_type: 'EXACT',
        match_type: 'EXACT',
        keyword: 'alpha keyword',
        targeting: '',
        impressions: 20,
        clicks: 2,
        cost_usd: 2,
        sales14d_usd: 20,
        purchases14d: 2,
      },
      {
        date: '2026-02-22',
        campaign_name: 'Campaign A',
        search_term: 'beta',
        keyword_type: 'EXACT',
        match_type: 'EXACT',
        keyword: 'beta keyword',
        targeting: '',
        impressions: 30,
        clicks: 3,
        cost_usd: 4,
        sales14d_usd: 40,
        purchases14d: 3,
      },
    ],
  };
}

function createFakePlacementData() {
  return {
    labels: ['2026-02-22', '2026-02-23'],
    rows: [
      {
        date: '2026-02-22',
        campaign_id: 'c-a',
        campaign_name: 'Campaign A',
        placement_classification: 'PLACEMENT_TOP',
        impressions: 100,
        clicks: 10,
        cost_usd: 5,
        sales14d_usd: 30,
        purchases14d: 3,
        top_of_search_impression_share: 0.21,
      },
      {
        date: '2026-02-23',
        campaign_id: 'c-b',
        campaign_name: 'Campaign B',
        placement_classification: 'Top of search',
        impressions: 80,
        clicks: 8,
        cost_usd: 4,
        sales14d_usd: 28,
        purchases14d: 2,
        top_of_search_impression_share: 0.34,
      },
      {
        date: '2026-02-22',
        campaign_id: 'c-a',
        campaign_name: 'Campaign A',
        placement_classification: 'rest of search',
        impressions: 60,
        clicks: 3,
        cost_usd: 2,
        sales14d_usd: 8,
        purchases14d: 1,
        top_of_search_impression_share: 0.21,
      },
    ],
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

test('normalizeSearchTermRow validates required fields and normalizes numbers', () => {
  assert.equal(normalizeSearchTermRow(null), null);
  assert.equal(normalizeSearchTermRow({ date: 'bad' }), null);

  const normalized = normalizeSearchTermRow({
    date: '2026-02-20',
    campaign_name: 'Campaign A',
    search_term: 'dad jokes',
    keyword_type: 'EXACT',
    clicks: '4',
    cost_usd: '5.25',
  });

  assert.equal(normalized.date, '2026-02-20');
  assert.equal(normalized.campaign_name, 'Campaign A');
  assert.equal(normalized.search_term, 'dad jokes');
  assert.equal(normalized.keyword_type, 'EXACT');
  assert.equal(normalized.clicks, 4);
  assert.equal(normalized.cost_usd, 5.25);
});

test('normalizePlacementRow validates required fields and normalizes placement labels', () => {
  assert.equal(normalizePlacementRow(null), null);
  assert.equal(normalizePlacementRow({ date: 'bad' }), null);

  const normalized = normalizePlacementRow({
    date: '2026-02-20',
    campaign_name: 'Campaign A',
    placement_classification: 'PLACEMENT_TOP',
    clicks: '4',
    cost_usd: '5.25',
  });

  assert.equal(normalized.date, '2026-02-20');
  assert.equal(normalized.campaign_name, 'Campaign A');
  assert.equal(normalized.placement_classification, 'Top of Search');
  assert.equal(normalized.clicks, 4);
  assert.equal(normalized.cost_usd, 5.25);
});

test('buildSearchTermAggregates computes totals and derived metrics', () => {
  const aggregates = buildSearchTermAggregates([
    {
      date: '2026-02-20',
      campaign_name: 'Campaign A',
      ad_group_name: 'AG 1',
      search_term: 'dad jokes',
      keyword_type: 'EXACT',
      match_type: 'EXACT',
      keyword: 'dad joke',
      targeting: '',
      impressions: 100,
      clicks: 10,
      cost_usd: 5,
      sales14d_usd: 20,
      purchases14d: 2,
      units_sold_clicks14d: 2,
    },
    {
      date: '2026-02-21',
      campaign_name: 'Campaign A',
      ad_group_name: 'AG 1',
      search_term: 'dad jokes',
      keyword_type: 'EXACT',
      match_type: 'EXACT',
      keyword: 'dad joke',
      targeting: '',
      impressions: 50,
      clicks: 5,
      cost_usd: 3,
      sales14d_usd: 12,
      purchases14d: 1,
      units_sold_clicks14d: 1,
    },
  ]);

  assert.equal(aggregates.length, 1);
  assert.equal(aggregates[0].impressions, 150);
  assert.equal(aggregates[0].clicks, 15);
  assert.equal(aggregates[0].cost_usd, 8);
  assert.equal(aggregates[0].sales14d_usd, 32);
  assertClose(aggregates[0].ctr, 10);
  assertClose(aggregates[0].cpc, 8 / 15);
  assertClose(aggregates[0].cvr, 20);
  assertClose(aggregates[0].acos, 25);
  assertClose(aggregates[0].roas, 4);
});

test('buildPlacementAggregates computes totals and derived metrics', () => {
  const aggregates = buildPlacementAggregates([
    {
      date: '2026-02-20',
      campaign_id: 'c-a',
      campaign_name: 'Campaign A',
      placement_classification: 'Top of Search',
      impressions: 100,
      clicks: 10,
      cost_usd: 5,
      sales14d_usd: 20,
      purchases14d: 2,
      top_of_search_impression_share: 0.25,
    },
    {
      date: '2026-02-21',
      campaign_id: 'c-b',
      campaign_name: 'Campaign B',
      placement_classification: 'Top of Search',
      impressions: 50,
      clicks: 5,
      cost_usd: 3,
      sales14d_usd: 12,
      purchases14d: 1,
      top_of_search_impression_share: 0.35,
    },
  ], ['placement_classification']);

  assert.equal(aggregates.length, 1);
  assert.equal(aggregates[0].placement_classification, 'Top of Search');
  assert.equal(aggregates[0].impressions, 150);
  assert.equal(aggregates[0].clicks, 15);
  assert.equal(aggregates[0].cost_usd, 8);
  assert.equal(aggregates[0].sales14d_usd, 32);
  assertClose(aggregates[0].ctr, 10);
  assertClose(aggregates[0].cpc, 8 / 15);
  assertClose(aggregates[0].cvr, 20);
  assertClose(aggregates[0].acos, 25);
  assertClose(aggregates[0].roas, 4);
  assertClose(aggregates[0].top_of_search_impression_share, 0.3);
});

test('filterSearchTermAggregates applies campaign/type/match/text filters', () => {
  const aggregates = [
    {
      campaign_name: 'Campaign A',
      keyword_type: 'EXACT',
      match_type: 'EXACT',
      search_term: 'dad jokes',
      keyword: 'dad joke',
      targeting: '',
    },
    {
      campaign_name: 'Campaign B',
      keyword_type: 'TARGETING_EXPRESSION',
      match_type: '',
      search_term: 'book',
      keyword: '',
      targeting: 'asin=\"B0G9765J19\"',
    },
  ];

  assert.equal(
    filterSearchTermAggregates(aggregates, {
      campaign: 'Campaign A',
      keywordType: 'EXACT',
      matchType: 'EXACT',
      text: 'dad',
    }).length,
    1,
  );
  assert.equal(
    filterSearchTermAggregates(aggregates, {
      campaign: 'All',
      keywordType: 'TARGETING_EXPRESSION',
      matchType: 'All',
      text: 'asin=',
    }).length,
    1,
  );
});

test('initAdsStatsPage search term timeline follows grouped row selection', async () => {
  const originalWindow = global.window;
  const originalDocument = global.document;
  const originalElement = global.Element;
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
  global.Element = FakeElement;
  global.window = {
    document,
    Chart: FakeChart,
    getSelection: () => ({ toString: () => '' }),
  };

  try {
    initAdsStatsPage({
      chartData: createFakeChartData(),
      reconciledClickDateChartData: createFakeReconciledChartData(),
      searchTermData: createFakeSearchTermData(),
      adsEvents: [],
    });

    const tableBody = elements.searchTermInsightsTableBody;
    const campaignChip = elements.searchTermDimensionChips.children[0];
    const syncAggregateKeyAttributes = () => {
      tableBody.children.forEach((row) => {
        if (row && row.dataset && row.dataset.aggregateKey) {
          row.setAttribute('data-aggregate-key', row.dataset.aggregateKey);
        }
      });
    };

    syncAggregateKeyAttributes();
    assert.ok(campaignChip);
    assert.equal(campaignChip.getAttribute('aria-pressed'), 'false');

    const alphaOnlyRow = tableBody.children.find((row) => row.dataset.aggregateKey === 'alpha');
    assert.ok(alphaOnlyRow);
    await tableBody.dispatch('click', { target: alphaOnlyRow });

    const searchTermChartsAfterAlpha = chartCalls.filter(
      (call) => call.canvasId === 'searchTermTrendChart',
    );
    assert.ok(searchTermChartsAfterAlpha.length >= 1);
    const alphaGroupedChart = searchTermChartsAfterAlpha[searchTermChartsAfterAlpha.length - 1];
    assert.deepEqual(alphaGroupedChart.config.data.datasets[0].data, [1, 2]);
    assert.deepEqual(alphaGroupedChart.config.data.datasets[1].data, [10, 20]);
    assert.deepEqual(alphaGroupedChart.config.data.datasets[2].data, [1, 2]);

    await campaignChip.dispatch('click');
    assert.equal(campaignChip.getAttribute('aria-pressed'), 'true');
    syncAggregateKeyAttributes();

    const alphaCampaignBRow = tableBody.children.find((row) => {
      return row.dataset.aggregateKey === `alpha${String.fromCharCode(31)}Campaign B`;
    });
    assert.ok(alphaCampaignBRow);
    await tableBody.dispatch('click', { target: alphaCampaignBRow });

    const searchTermChartsAfterCampaignGrouping = chartCalls.filter(
      (call) => call.canvasId === 'searchTermTrendChart',
    );
    const alphaCampaignChart = searchTermChartsAfterCampaignGrouping[
      searchTermChartsAfterCampaignGrouping.length - 1
    ];
    assert.deepEqual(alphaCampaignChart.config.data.datasets[0].data, [0, 2]);
    assert.deepEqual(alphaCampaignChart.config.data.datasets[1].data, [0, 20]);
    assert.deepEqual(alphaCampaignChart.config.data.datasets[2].data, [0, 2]);
  } finally {
    global.window = originalWindow;
    global.document = originalDocument;
    global.Element = originalElement;
  }
});

test('initAdsStatsPage placement timeline follows grouped row selection', async () => {
  const originalWindow = global.window;
  const originalDocument = global.document;
  const originalElement = global.Element;
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
  global.Element = FakeElement;
  global.window = {
    document,
    Chart: FakeChart,
    getSelection: () => ({ toString: () => '' }),
  };

  try {
    initAdsStatsPage({
      chartData: createFakeChartData(),
      reconciledClickDateChartData: createFakeReconciledChartData(),
      searchTermData: createFakeSearchTermData(),
      placementData: createFakePlacementData(),
      adsEvents: [],
    });

    const tableBody = elements.placementInsightsTableBody;
    const campaignChip = elements.placementDimensionChips.children[1];
    const syncAggregateKeyAttributes = () => {
      tableBody.children.forEach((row) => {
        if (row && row.dataset && row.dataset.aggregateKey) {
          row.setAttribute('data-aggregate-key', row.dataset.aggregateKey);
        }
      });
    };

    syncAggregateKeyAttributes();
    assert.ok(campaignChip);
    assert.equal(campaignChip.getAttribute('aria-pressed'), 'false');
    assert.match(elements.placementInsightsTableHead.innerHTML, /Placement/i);
    assert.doesNotMatch(elements.placementInsightsTableHead.innerHTML, /Top of Search IS/i);

    const topPlacementRow = tableBody.children.find(
      (row) => row.dataset.aggregateKey === 'Top of Search',
    );
    assert.ok(topPlacementRow);
    await tableBody.dispatch('click', { target: topPlacementRow });

    const placementChartsAfterPlacementOnly = chartCalls.filter(
      (call) => call.canvasId === 'placementTrendChart',
    );
    assert.ok(placementChartsAfterPlacementOnly.length >= 1);
    const placementOnlyChart = placementChartsAfterPlacementOnly[
      placementChartsAfterPlacementOnly.length - 1
    ];
    assert.deepEqual(placementOnlyChart.config.data.datasets[0].data, [5, 4]);
    assert.deepEqual(placementOnlyChart.config.data.datasets[1].data, [30, 28]);
    assert.deepEqual(placementOnlyChart.config.data.datasets[2].data, [10, 8]);

    await campaignChip.dispatch('click');
    assert.equal(campaignChip.getAttribute('aria-pressed'), 'true');
    syncAggregateKeyAttributes();
    assert.match(elements.placementInsightsTableHead.innerHTML, /Top of Search IS/i);

    const topCampaignBRow = tableBody.children.find((row) => {
      return row.dataset.aggregateKey === `Top of Search${String.fromCharCode(31)}Campaign B`;
    });
    assert.ok(topCampaignBRow);
    await tableBody.dispatch('click', { target: topCampaignBRow });

    const placementChartsAfterCampaignGrouping = chartCalls.filter(
      (call) => call.canvasId === 'placementTrendChart',
    );
    const campaignPlacementChart = placementChartsAfterCampaignGrouping[
      placementChartsAfterCampaignGrouping.length - 1
    ];
    assert.deepEqual(campaignPlacementChart.config.data.datasets[0].data, [0, 4]);
    assert.deepEqual(campaignPlacementChart.config.data.datasets[1].data, [0, 28]);
    assert.deepEqual(campaignPlacementChart.config.data.datasets[2].data, [0, 8]);
  } finally {
    global.window = originalWindow;
    global.document = originalDocument;
    global.Element = originalElement;
  }
});

test('initAdsStatsPage shares ads event hover behavior across dashboard and grouped charts', () => {
  const originalWindow = global.window;
  const originalDocument = global.document;
  const chartCalls = [];
  const { document } = createFakeAdsStatsDom(TIMELINE_MODE);

  function FakeChart(ctx, config) {
    const instance = {
      destroy: () => {},
      draw: () => {},
      canvas: ctx.canvas,
      data: config.data,
      options: config.options,
    };
    chartCalls.push({
      canvasId: ctx.canvas.id,
      config,
      instance,
    });
    return instance;
  }

  global.document = document;
  global.window = {
    document,
    Chart: FakeChart,
    getSelection: () => ({ toString: () => '' }),
  };

  try {
    initAdsStatsPage({
      chartData: createFakeChartData(),
      reconciledClickDateChartData: createFakeReconciledChartData(),
      placementData: createFakePlacementData(),
      searchTermData: createFakeSearchTermData(),
      adsEvents: [{
        date: '2026-02-22',
        title: 'Launch Day',
      }],
    });

    const mainChartCall = chartCalls.find(
      (call) => call.canvasId === 'reconciledProfitTimelineChart',
    );
    const placementChartCall = chartCalls.filter(
      (call) => call.canvasId === 'placementTrendChart',
    ).at(-1);
    const searchTermChartCall = chartCalls.filter(
      (call) => call.canvasId === 'searchTermTrendChart',
    ).at(-1);

    assert.ok(mainChartCall);
    assert.ok(placementChartCall);
    assert.ok(searchTermChartCall);
    assert.strictEqual(
      mainChartCall.config.plugins[0],
      placementChartCall.config.plugins[0],
    );
    assert.strictEqual(
      mainChartCall.config.plugins[0],
      searchTermChartCall.config.plugins[0],
    );

    [mainChartCall, placementChartCall, searchTermChartCall].forEach((call) => {
      assert.equal(call.config.options.plugins.adsEventsOverlay.enabled, true);
      call.instance.chartArea = {
        left: 0,
        right: 320,
        top: 0,
        bottom: 200,
      };
      call.instance.scales = {
        x: {
          getPixelForValue(value) {
            return value === '2026-02-22' ? 120 : 220;
          },
        },
      };

      call.config.plugins[0].afterEvent(call.instance, {
        event: {
          type: 'mousemove',
          x: 120,
          y: 48,
        },
      });

      assert.ok(call.instance.$adsEventsTooltipEl);
      assert.equal(call.instance.$adsEventsTooltipEl.style.display, 'block');
      assert.match(call.instance.$adsEventsTooltipEl.innerHTML, /Launch Day/);
    });
  } finally {
    global.window = originalWindow;
    global.document = originalDocument;
  }
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

test('readAdsStatsPageOptionsFromDocument parses embedded JSON payload', () => {
  const { document, elements } = createFakeAdsStatsDom(TIMELINE_MODE);
  const embeddedData = {
    chartData: createFakeChartData(),
    placementData: createFakePlacementData(),
    searchTermData: createFakeSearchTermData(),
    reconciledClickDateChartData: createFakeReconciledChartData(),
    reconciliationDebugCsv: 'alpha,beta',
    adsEvents: [{ date: '2026-02-22', title: 'Launch Day' }],
  };
  setEmbeddedAdsStatsPageData(elements, embeddedData);

  assert.deepEqual(
    readAdsStatsPageOptionsFromDocument(document),
    embeddedData,
  );
});

test('initAdsStatsPage reads embedded page data and mode buttons update charts', async () => {
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

  setEmbeddedAdsStatsPageData(elements, {
    chartData: createFakeChartData(),
    placementData: createFakePlacementData(),
    searchTermData: createFakeSearchTermData(),
    reconciledClickDateChartData: createFakeReconciledChartData(),
    reconciliationDebugCsv: '',
    adsEvents: [],
  });

  global.document = document;
  global.window = {
    document,
    Chart: FakeChart,
    getSelection: () => ({ toString: () => '' }),
  };

  try {
    initAdsStatsPage();
    assert.equal(chartCalls.length, 10);
    assert.equal(elements.modeSelector.value, TIMELINE_MODE);
    assert.equal(elements.adsStatsModeTimelineButton.getAttribute('aria-pressed'), 'true');
    assert.equal(elements.adsStatsModeDaysOfWeekButton.getAttribute('aria-pressed'), 'false');

    await elements.adsStatsModeDaysOfWeekButton.dispatch('click');

    assert.equal(elements.modeSelector.value, DAYS_OF_WEEK_MODE);
    assert.equal(elements.adsStatsModeTimelineButton.getAttribute('aria-pressed'), 'false');
    assert.equal(elements.adsStatsModeDaysOfWeekButton.getAttribute('aria-pressed'), 'true');
    assert.deepEqual(
      chartCalls.slice(-8).map((call) => call.config.type),
      Array(8).fill('bar'),
    );
  } finally {
    global.window = originalWindow;
    global.document = originalDocument;
  }
});

test('initAdsStatsPage create event controls post and update status when moved logic runs from ads_stats.js', async () => {
  const originalWindow = global.window;
  const originalDocument = global.document;
  const originalFetch = global.fetch;
  const chartCalls = [];
  const fetchMock = createFetchMock([{
    ok: true,
    json: {
      event: {
        key: 'launch',
        date: '2026-02-24',
        title: 'Launch Day',
      },
    },
  }]);
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

  setEmbeddedAdsStatsPageData(elements, {
    chartData: createFakeChartData(),
    placementData: createFakePlacementData(),
    searchTermData: createFakeSearchTermData(),
    reconciledClickDateChartData: createFakeReconciledChartData(),
    reconciliationDebugCsv: '',
    adsEvents: [],
  });

  global.fetch = fetchMock;
  global.document = document;
  global.window = {
    document,
    Chart: FakeChart,
    getSelection: () => ({ toString: () => '' }),
  };

  try {
    initAdsStatsPage();

    assert.equal(elements.adsStatsCreateEventForm.hidden, true);
    await elements.adsStatsCreateEventToggleButton.dispatch('click');
    assert.equal(elements.adsStatsCreateEventForm.hidden, false);
    assert.equal(elements.adsStatsCreateEventToggleButton.getAttribute('aria-expanded'), 'true');
    assert.equal(elements.adsStatsEventDateInput.focused, true);

    elements.adsStatsEventDateInput.value = '2026-02-24';
    elements.adsStatsEventTitleInput.value = 'Launch Day';
    await elements.adsStatsCreateEventForm.dispatch('submit');

    assert.equal(fetchMock.calls.length, 1);
    assert.equal(fetchMock.calls[0].url, '/admin/ads-stats/events');
    assert.equal(fetchMock.calls[0].options.method, 'POST');
    assert.deepEqual(
      JSON.parse(fetchMock.calls[0].options.body),
      { date: '2026-02-24', title: 'Launch Day' },
    );
    assert.equal(elements.adsStatsCreateEventStatus.textContent, 'Saved');
    assert.equal(elements.adsStatsEventTitleInput.value, '');
    assert.ok(chartCalls.length > 10);
  } finally {
    global.fetch = originalFetch;
    global.window = originalWindow;
    global.document = originalDocument;
  }
});

test('initAdsStatsPage KDP upload controls post selected file and reload on success', async () => {
  const originalWindow = global.window;
  const originalDocument = global.document;
  const originalFetch = global.fetch;
  const originalFormData = global.FormData;
  const fetchMock = createFetchMock([{
    ok: true,
    json: {
      days_saved: 2,
    },
  }]);
  const formDataEntries = [];
  let reloaded = false;
  const { document, elements } = createFakeAdsStatsDom(TIMELINE_MODE);

  function FakeChart(ctx, config) {
    return {
      destroy: () => {},
      canvas: ctx.canvas,
      data: config.data,
      options: config.options,
    };
  }

  class FakeFormData {
    append(name, value) {
      formDataEntries.push([name, value]);
    }
  }

  setEmbeddedAdsStatsPageData(elements, {
    chartData: createFakeChartData(),
    placementData: createFakePlacementData(),
    searchTermData: createFakeSearchTermData(),
    reconciledClickDateChartData: createFakeReconciledChartData(),
    reconciliationDebugCsv: '',
    adsEvents: [],
  });

  elements.kdpFileInput.files = [{ name: 'report.xlsx' }];
  global.fetch = fetchMock;
  global.FormData = FakeFormData;
  global.document = document;
  global.window = {
    document,
    Chart: FakeChart,
    getSelection: () => ({ toString: () => '' }),
    location: {
      reload() {
        reloaded = true;
      },
    },
  };

  try {
    initAdsStatsPage();
    await elements.kdpFileInput.dispatch('change');

    assert.equal(fetchMock.calls.length, 1);
    assert.equal(fetchMock.calls[0].url, '/admin/ads-stats/upload-kdp');
    assert.equal(fetchMock.calls[0].options.method, 'POST');
    assert.deepEqual(formDataEntries, [['file', elements.kdpFileInput.files[0]]]);
    assert.equal(elements.kdpUploadStatus.textContent, 'Saved 2 days');
    assert.equal(reloaded, true);
  } finally {
    global.fetch = originalFetch;
    global.FormData = originalFormData;
    global.window = originalWindow;
    global.document = originalDocument;
  }
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

test('initAdsStatsPage switches chart configs from line to bar in Days of Week mode', async () => {
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
    await elements.modeSelector.dispatch('change');

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

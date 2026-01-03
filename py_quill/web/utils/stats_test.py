"""Tests for stats bucketing utilities."""

from __future__ import annotations

from web.utils import stats as stats_utils


def test_bucket_jokes_viewed_ranges():
  """Ensure bucket ranges match the defined spec."""
  assert stats_utils.bucket_jokes_viewed(0) == "0"
  assert stats_utils.bucket_jokes_viewed(1) == "1-9"
  assert stats_utils.bucket_jokes_viewed(9) == "1-9"
  assert stats_utils.bucket_jokes_viewed(10) == "10-19"
  assert stats_utils.bucket_jokes_viewed(99) == "90-99"
  assert stats_utils.bucket_jokes_viewed(100) == "100-149"
  assert stats_utils.bucket_jokes_viewed(149) == "100-149"
  assert stats_utils.bucket_jokes_viewed(150) == "150-199"


def test_rebucket_counts_and_matrix():
  """Rebucket merges numeric and string buckets into defined ranges."""
  counts = {"1": 2, "5": 3, "10": 1, "101": 4, "bad": 9}
  rebucketed = stats_utils.rebucket_counts(counts)
  assert rebucketed == {
    "1-9": 5,
    "10-19": 1,
    "100-149": 4,
  }

  matrix = {"2": counts}
  rebucketed_matrix = stats_utils.rebucket_matrix(matrix)
  assert rebucketed_matrix == {"2": rebucketed}



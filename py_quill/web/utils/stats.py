"""Stats bucketing helpers for admin charts."""

from __future__ import annotations


def bucket_jokes_viewed(count: int) -> str:
  """Bucket joke view counts into ranges for charting."""
  safe_count = max(0, count)
  if safe_count == 0:
    return "0"
  if safe_count < 10:
    return "1-9"
  if safe_count < 100:
    lower = (safe_count // 10) * 10
    upper = lower + 9
    return f"{lower}-{upper}"
  lower = max(100, (safe_count // 50) * 50)
  upper = lower + 49
  return f"{lower}-{upper}"


def rebucket_counts(counts: object) -> dict[str, int]:
  """Aggregate arbitrary bucket keys into the defined joke-count buckets."""
  if not isinstance(counts, dict):
    return {}

  aggregated: dict[str, int] = {}
  for raw_bucket, raw_count in counts.items():
    try:
      count_val = int(raw_count)
    except Exception:
      continue

    if isinstance(raw_bucket, str) and "-" in raw_bucket:
      bucket_label = raw_bucket
    else:
      try:
        numeric_bucket = int(raw_bucket)
      except Exception:
        continue
      bucket_label = bucket_jokes_viewed(numeric_bucket)

    aggregated[bucket_label] = aggregated.get(bucket_label, 0) + count_val

  return aggregated


def rebucket_matrix(matrix: object) -> dict[str, dict[str, int]]:
  """Aggregate a nested day->bucket map into the defined bucket ranges."""
  if not isinstance(matrix, dict):
    return {}

  rebucketed: dict[str, dict[str, int]] = {}
  for day, day_data in matrix.items():
    rebucketed[day] = rebucket_counts(day_data)
  return rebucketed


def bucket_label_sort_key(label: str) -> int:
  """Sort bucket labels by their numeric lower bound."""
  if isinstance(label, str) and "-" in label:
    lower = label.split("-", 1)[0]
    try:
      return int(lower)
    except Exception:
      return 0
  try:
    return int(label)
  except Exception:
    return 0


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
  hex_color = hex_color.lstrip('#')
  return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
  r, g, b = rgb
  return f'#{r:02x}{g:02x}{b:02x}'


_ANCHOR_COLORS = [
  '#7e57c2',  # Purple (start)
  '#3f51b5',  # Indigo
  '#2196f3',  # Blue
  '#26a69a',  # Teal
  '#66bb6a',  # Green
  '#ffeb3b',  # Yellow
  '#ff9800',  # Orange
  '#f44336',  # Red (end)
]
_ZERO_BUCKET_COLOR = '#9e9e9e'


def _color_at_position(position: float) -> str:
  """Return a color along the rainbow gradient (purple -> red)."""
  position = max(0.0, min(1.0, position))
  segment_count = len(_ANCHOR_COLORS) - 1
  if segment_count <= 0:
    return _ANCHOR_COLORS[0]

  scaled = position * segment_count
  idx = int(scaled)
  if idx >= segment_count:
    return _ANCHOR_COLORS[-1]

  local_t = scaled - idx
  start_rgb = _hex_to_rgb(_ANCHOR_COLORS[idx])
  end_rgb = _hex_to_rgb(_ANCHOR_COLORS[idx + 1])
  interp = tuple(
    round(start_rgb[c] + (end_rgb[c] - start_rgb[c]) * local_t)
    for c in range(3))
  return _rgb_to_hex(interp)


def build_bucket_color_map(bucket_labels: list[str]) -> dict[str, str]:
  """Assign colors to buckets using a rainbow gradient."""
  color_map: dict[str, str] = {}
  non_zero_labels = [b for b in bucket_labels if b != "0"]
  total = len(non_zero_labels)

  for idx, bucket in enumerate(non_zero_labels):
    position = 0.0 if total <= 1 else idx / (total - 1)
    color_map[bucket] = _color_at_position(position)

  if "0" in bucket_labels:
    color_map["0"] = _ZERO_BUCKET_COLOR

  return color_map


def _bucket_days_used_label(day_value: str | int) -> str | None:
  """Bucket days-used into singles for <=7, weekly ranges for >=8."""
  try:
    day_int = int(day_value)
  except Exception:
    return None

  if day_int <= 0:
    return None
  if day_int <= 7:
    return str(day_int)
  start = ((day_int - 1) // 7) * 7 + 1
  end = start + 6
  return f"{start}-{end}"


def rebucket_days_used(
  matrix: dict[str, dict[str, int]] | object, ) -> dict[str, dict[str, int]]:
  """Aggregate retention matrix by day-used buckets (1..7 individual, then weekly)."""
  if not isinstance(matrix, dict):
    return {}

  rebucketed: dict[str, dict[str, int]] = {}
  for day_label, buckets in (matrix or {}).items():
    target_label = _bucket_days_used_label(day_label)
    if not target_label:
      continue
    if target_label not in rebucketed:
      rebucketed[target_label] = {}
    for bucket_label, count in (buckets or {}).items():
      rebucketed[target_label][bucket_label] = (
        rebucketed[target_label].get(bucket_label, 0) + int(count or 0))
  return rebucketed


def day_bucket_sort_key(label: str) -> int:
  """Sort day buckets by their numeric lower bound."""
  if isinstance(label, str) and "-" in label:
    lower = label.split("-", 1)[0]
    try:
      return int(lower)
    except Exception:
      return 0
  try:
    return int(label)
  except Exception:
    return 0

"""Formatting helpers for joke generation metadata in the web UI."""

from __future__ import annotations

from typing import Any, cast

from common import models

_NO_METADATA_MESSAGE = "No generation metadata available for this joke."
_EXCLUDED_GENERATION_FIELDS = {
  "label",
  "model_name",
  "cost",
  "generation_time_sec",
  "retry_count",
}


def _format_raw_metadata(metadata: dict[str, Any]) -> str:
  """Render unexpected metadata structures in an indented plain-text format."""
  lines: list[str] = []

  def write_key_value(key: str, value: Any, indent: int = 0) -> None:
    indent_str = "  " * indent
    if isinstance(value, dict):
      lines.append(f"{indent_str}{key}:")
      for nested_key, nested_value in cast(dict[str, Any], value).items():
        write_key_value(str(nested_key), nested_value, indent=indent + 1)
      return
    if isinstance(value, list):
      items = cast(list[Any], value)
      lines.append(f"{indent_str}{key}: [{len(items)} items]")
      for index, item in enumerate(items):
        write_key_value(f"[{index}]", item, indent=indent + 1)
      return
    lines.append(f"{indent_str}{key}: {value}")

  for key, value in metadata.items():
    write_key_value(str(key), value)

  return "\n".join(lines).strip()


def _append_generation_field_lines(lines: list[str],
                                   generation: dict[str, Any]) -> None:
  """Append detail lines for non-summary generation fields."""
  for key, value in generation.items():
    if key in _EXCLUDED_GENERATION_FIELDS:
      continue
    if isinstance(value, dict):
      lines.append(f"  {key}:")
      for nested_key, nested_value in cast(dict[str, Any], value).items():
        lines.append(f"    {nested_key}: {nested_value}")
      continue
    lines.append(f"  {key}: {value}")


def _append_generation_detail_lines(lines: list[str], label_text: str,
                                    model_name: str,
                                    generation: dict[str, Any]) -> None:
  """Append one formatted generation detail block."""
  lines.append(label_text)
  lines.append(f"  model_name: {model_name}")

  cost_value = generation.get("cost")
  cost = float(cost_value) if isinstance(cost_value, (int, float)) else 0.0
  lines.append(f"  cost: ${cost:.4f}")

  generation_time = generation.get("generation_time_sec")
  if isinstance(generation_time, (int, float)) and generation_time > 0:
    lines.append(f"  time: {float(generation_time):.2f}s")

  _append_generation_field_lines(lines, generation)


def _coerce_generation_dict(generation: Any) -> dict[str, Any] | None:
  """Normalize a generation entry to a plain dict."""
  if isinstance(generation, models.SingleGenerationMetadata):
    return generation.as_dict
  if isinstance(generation, dict):
    return cast(dict[str, Any], generation)
  return None


def _coerce_generation_metadata(metadata: Any) -> dict[str, Any]:
  """Normalize generation metadata to a dict."""
  if isinstance(metadata, models.GenerationMetadata):
    return metadata.as_dict
  if isinstance(metadata, dict):
    return cast(dict[str, Any], metadata)
  return {}


def format_generation_metadata_tooltip(metadata: Any) -> str:
  """Format generation metadata to match the admin long-press details view."""
  metadata_dict = _coerce_generation_metadata(metadata)
  if not metadata_dict:
    return _NO_METADATA_MESSAGE

  raw_generations = metadata_dict.get("generations")
  if not isinstance(raw_generations, list) or not raw_generations:
    raw_metadata = _format_raw_metadata(metadata_dict)
    return raw_metadata or _NO_METADATA_MESSAGE
  generations = cast(list[Any], raw_generations)

  grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
  total_costs: dict[str, dict[str, float]] = {}
  counts: dict[str, dict[str, int]] = {}

  for raw_generation in generations:
    generation = _coerce_generation_dict(raw_generation)
    if generation is None:
      continue

    label = str(generation.get("label") or "unknown")
    model_name = str(generation.get("model_name") or "unknown")
    cost_value = generation.get("cost")
    cost = float(cost_value) if isinstance(cost_value, (int, float)) else 0.0

    grouped.setdefault(label, {}).setdefault(model_name, []).append(generation)
    _ = total_costs.setdefault(label, {}).setdefault(model_name, 0.0)
    total_costs[label][model_name] += cost
    _ = counts.setdefault(label, {}).setdefault(model_name, 0)
    counts[label][model_name] += 1

  if not grouped:
    raw_metadata = _format_raw_metadata(metadata_dict)
    return raw_metadata or _NO_METADATA_MESSAGE

  grand_total = sum(cost for label_costs in total_costs.values()
                    for cost in label_costs.values())
  lines = [
    "SUMMARY",
    f"Total Cost: ${grand_total:.4f}",
    "",
  ]

  for label, models_by_name in grouped.items():
    lines.append(label)
    for model_name in models_by_name:
      lines.append(
        f"  {model_name}: ${total_costs[label][model_name]:.4f} ({counts[label][model_name]})"
      )
    lines.append("")

  lines.append("DETAILS")

  grouped_items = list(grouped.items())
  for label_index, (label, models_by_name) in enumerate(grouped_items):
    model_items = list(models_by_name.items())
    for model_index, (model_name, generation_list) in enumerate(model_items):
      for generation_index, generation in enumerate(generation_list):
        label_text = label
        if generation_index > 0 and len(generation_list) > 1:
          label_text = f"{label} ({generation_index + 1})"

        _append_generation_detail_lines(lines, label_text, model_name,
                                        generation)

        is_last_generation = generation_index == len(generation_list) - 1
        is_last_model = model_index == len(model_items) - 1
        is_last_label = label_index == len(grouped_items) - 1
        if not (is_last_generation and is_last_model and is_last_label):
          lines.append("")

  return "\n".join(lines).strip()

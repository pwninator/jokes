"""Utility helpers for prompt parsing."""


def parse_llm_response_line_separated(
  keys: list[str],
  llm_response: str,
) -> dict[str, str]:
  """Parse a line-separated LLM response into a dictionary keyed by sections.

  Args:
      keys: List of section headers to extract (case-insensitive).
      llm_response: Full text response from the LLM.

  Returns:
      A dictionary mapping each key to the captured multiline text that
      follows its header. Missing sections return empty strings.
  """
  normalized_keys = {key.upper(): key for key in keys}
  result: dict[str, str] = {key: "" for key in keys}
  current_key: str | None = None
  buffer: list[str] = []

  def _flush_buffer_for_current_key() -> None:
    nonlocal buffer, current_key
    if current_key:
      result[current_key] = "\n".join(buffer).strip()
    buffer = []

  for line in llm_response.splitlines():
    line = line.strip()

    candidate_key = line.upper()
    if candidate_key.endswith(":"):
      # Trailing colon is optional
      candidate_key = candidate_key[:-1].strip()

    if candidate_key in normalized_keys:
      _flush_buffer_for_current_key()
      current_key = normalized_keys[candidate_key]
    elif current_key:
      buffer.append(line)

  _flush_buffer_for_current_key()
  return result

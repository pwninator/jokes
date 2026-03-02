"""Sanity checks for admin joke actions JS.

These are lightweight tests that ensure critical client-side behaviors don't
silently regress (we don't have a JS test runner in this repo).
"""

from __future__ import annotations

from pathlib import Path

def test_joke_admin_actions_updates_card_after_regenerate():
  js_path = Path(__file__).resolve().parent / "js" / "joke_admin_actions.js"
  js = js_path.read_text(encoding="utf-8")

  # The "regenerate images" modal should update the card in-place when the API
  # returns the updated joke payload.
  assert "regenerateForm.addEventListener('submit'" in js
  assert "applyJokeDataToPayload" in js
  assert "updateCardFromPayload(card, refreshedPayload)" in js


def test_joke_admin_actions_modify_flow_uses_image_modify_op_and_updates_card():
  js_path = Path(__file__).resolve().parent / "js" / "joke_admin_actions.js"
  js = js_path.read_text(encoding="utf-8")

  assert "function closestFromEvent(event, selector)" in js
  assert "const modifyButton = closestFromEvent(event, '.joke-modify-button');" in js
  assert "function sendModifyRequest()" in js
  assert "op: 'joke_image_modify'" in js
  assert "joke image modify request failed" in js
  assert "updateCardFromPayload(card, refreshedPayload)" in js

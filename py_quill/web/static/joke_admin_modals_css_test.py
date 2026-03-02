"""Sanity checks for admin joke modal CSS."""

from __future__ import annotations

from pathlib import Path


def test_admin_action_buttons_share_one_footer_rule():
  css_path = Path(__file__).resolve().parent / "css" / "joke_admin_modals.css"
  css = css_path.read_text(encoding="utf-8")

  assert ".joke-admin-footer .joke-regenerate-button," in css
  assert ".joke-admin-footer .joke-edit-button," in css
  assert ".joke-admin-footer .joke-modify-button {" in css
  assert ".joke-admin-footer .joke-edit-button {\n  margin-left: auto;\n}" not in css
  assert ".joke-admin-button.joke-modify-button" not in css
  assert "min-width: 88px;" not in css

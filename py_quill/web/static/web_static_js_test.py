"""Runs the zero-dependency Node.js suite for web static JavaScript tests."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest


def test_web_static_js_node_suite_passes() -> None:
  node_path = shutil.which("node")
  if not node_path:
    pytest.skip("Node.js is required to run the web static JS test suite")

  js_dir = Path(__file__).resolve().parent / "js"
  test_files = sorted(str(path) for path in js_dir.glob("*.test.js"))
  assert test_files, "Expected at least one JS test file"

  completed = subprocess.run(
    [node_path, "--test", *test_files],
    check=False,
    capture_output=True,
    text=True,
  )

  if completed.returncode != 0:
    pytest.fail(
      "Node.js web static test suite failed\n"
      f"stdout:\n{completed.stdout}\n"
      f"stderr:\n{completed.stderr}"
    )

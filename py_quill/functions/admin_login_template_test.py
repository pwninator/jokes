"""Tests for the admin login template JavaScript."""

import subprocess
import sys
from pathlib import Path

import pytest
from flask import Flask, render_template


@pytest.fixture(scope='module')
def flask_app():
  app = Flask(__name__)
  app.template_folder = str(Path('py_quill/web/templates').resolve())
  app.static_folder = str(Path('py_quill/web/static').resolve())
  return app


def _extract_inline_script(html: str) -> str:
  start = html.find('<script type="module">')
  if start == -1:
    raise AssertionError('No module script found in login template')
  end = html.find('</script>', start)
  if end == -1:
    raise AssertionError('Module script not closed')
  start += len('<script type="module">')
  return html[start:end]


def _ensure_node_installed():
  try:
    subprocess.run(['node', '--version'],
                   check=True,
                   stdout=subprocess.PIPE,
                   stderr=subprocess.PIPE)
  except Exception as exc:  # pragma: no cover - defensive
    raise RuntimeError('Node.js must be installed to run JS syntax checks'
                       ) from exc


def _run_node_syntax_check(js_source: str) -> subprocess.CompletedProcess:
  tmp_dir = Path('py_quill/.tmp_js_checks')
  tmp_dir.mkdir(exist_ok=True)
  source_path = tmp_dir / 'inline.mjs'
  source_path.write_text(js_source, encoding='utf-8')

  return subprocess.run(['node', '--check', str(source_path)],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True)


def test_admin_login_inline_script_is_valid_js(flask_app):
  _ensure_node_installed()

  with flask_app.app_context():
    rendered = render_template(
      'admin/login.html',
      firebase_config={
        'apiKey': 'test',
        'authDomain': 'example.firebaseapp.com',
        'projectId': 'example'
      },
      next_url='/admin',
    )

  inline_js = _extract_inline_script(rendered)
  result = _run_node_syntax_check(inline_js)

  if result.returncode != 0:
    pytest.fail(
      f'Admin login inline script has syntax error:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}'
    )


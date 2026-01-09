"""Tests for the login template JavaScript."""

import subprocess
import sys
from pathlib import Path

import pytest
from flask import Blueprint, Flask, render_template, url_for


@pytest.fixture(scope='module')
def flask_app():
  app = Flask(__name__)
  # Resolve path relative to this test file's location
  test_file_dir = Path(__file__).parent.parent
  app.template_folder = str((test_file_dir / 'web' / 'templates').resolve())
  app.static_folder = str((test_file_dir / 'web' / 'static').resolve())
  web_bp = Blueprint('web', __name__)

  @web_bp.route('/')
  def index():
    return ''

  @web_bp.route('/lunchbox')
  def lunchbox():
    return ''

  @web_bp.route('/printables/notes')
  def notes():
    return ''

  @web_bp.route('/jokes')
  def jokes():
    return ''

  @web_bp.route('/about')
  def about():
    return ''

  @web_bp.route('/session-info')
  def session_info():
    return ''

  @web_bp.route('/logout', methods=['POST'])
  def logout():
    return ''

  app.register_blueprint(web_bp)
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
    raise RuntimeError(
      'Node.js must be installed to run JS syntax checks') from exc


def _run_node_syntax_check(js_source: str) -> subprocess.CompletedProcess:
  # Create temp directory relative to the test file location
  test_file_dir = Path(__file__).parent.parent
  tmp_dir = test_file_dir / '.tmp_js_checks'
  tmp_dir.mkdir(parents=True, exist_ok=True)
  source_path = tmp_dir / 'inline.mjs'
  source_path.write_text(js_source, encoding='utf-8')

  return subprocess.run(
    ['node', '--check', str(source_path)],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True)


def test_login_inline_script_is_valid_js(flask_app):
  _ensure_node_installed()

  with flask_app.test_request_context('/'):
    rendered = render_template(
      'login.html',
      firebase_config={
        'apiKey': 'test',
        'authDomain': 'example.firebaseapp.com',
        'projectId': 'example'
      },
      site_name='Snickerdoodle',
      login_next_url='/admin',
      canonical_url='https://snickerdoodlejokes.com/login',
      prev_url=None,
      next_url=None,
    )

  inline_js = _extract_inline_script(rendered)
  result = _run_node_syntax_check(inline_js)

  if result.returncode != 0:
    pytest.fail(
      f'Admin login inline script has syntax error:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}'
    )

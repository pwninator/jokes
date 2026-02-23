import pytest
from flask import Flask
from unittest.mock import patch
from web.routes.admin import rhyming_words
from web.routes import web_bp


@pytest.fixture
def app():
  app = Flask(__name__)
  app.secret_key = 'test'
  return app


def test_admin_rhyming_words_integration(app):
  app.register_blueprint(web_bp)

  with app.test_client() as client:
    with patch('functions.auth_helpers.verify_session') as mock_verify, \
         patch('web.routes.admin.rhyming_words.render_template') as mock_render, \
         patch('services.phonetics.get_phonetic_matches') as mock_phonetics:

      # verify_session returns (uid, claims).
      # The 'require_admin' decorator checks claims.get('role') == 'admin'
      mock_verify.return_value = ('test-uid', {'role': 'admin'})

      mock_phonetics.return_value = (['h1'], ['r1'])

      response = client.post('/admin/rhyming-words', data={'word': 'testword'})

      assert response.status_code == 200
      mock_phonetics.assert_called_with('testword')

      mock_render.assert_called_once()
      call_args = mock_render.call_args
      assert call_args[0][0] == 'admin/rhyming_words.html'
      assert call_args[1]['site_name'] == 'Snickerdoodle'
      assert call_args[1]['word'] == 'testword'
      assert call_args[1]['homophones'] == ['h1']
      assert call_args[1]['rhymes'] == ['r1']


def test_admin_rhyming_words_get_integration(app):
  app.register_blueprint(web_bp)

  with app.test_client() as client:
    with patch('functions.auth_helpers.verify_session') as mock_verify, \
         patch('web.routes.admin.rhyming_words.render_template') as mock_render:

      mock_verify.return_value = ('test-uid', {'role': 'admin'})

      response = client.get('/admin/rhyming-words')

      assert response.status_code == 200
      mock_render.assert_called_once()
      call_args = mock_render.call_args
      assert call_args[0][0] == 'admin/rhyming_words.html'
      assert call_args[1]['site_name'] == 'Snickerdoodle'
      assert call_args[1]['word'] is None
      assert call_args[1]['homophones'] == []

"""Tests for character animator routes."""

import flask
import pytest
from unittest.mock import patch, MagicMock
from web.app import app
from functions import auth_helpers

def _mock_admin_session(monkeypatch):
  """Bypass admin auth for route tests."""
  monkeypatch.setattr(auth_helpers.utils, "is_emulator", lambda: True)

@pytest.fixture
def client():
  app.config['TESTING'] = True
  with app.test_client() as client:
    yield client

@patch('services.firestore.get_posable_character_defs')
@patch('services.firestore.get_posable_character_sequences')
def test_character_animator_page(mock_get_sequences, mock_get_defs, client, monkeypatch):
  _mock_admin_session(monkeypatch)
  mock_get_defs.return_value = []
  mock_get_sequences.return_value = []

  response = client.get('/admin/character-animator')
  assert response.status_code == 200
  assert b'Character Animator' in response.data

@patch('services.firestore.get_posable_character_def')
@patch('services.firestore.get_posable_character_sequence')
def test_character_animator_api(mock_get_seq, mock_get_def, client, monkeypatch):
  _mock_admin_session(monkeypatch)
  mock_def = MagicMock()
  mock_def.to_dict.return_value = {'key': 'def1', 'name': 'Test Def'}
  mock_get_def.return_value = mock_def

  mock_seq = MagicMock()
  mock_seq.to_dict.return_value = {'key': 'seq1'}
  mock_get_seq.return_value = mock_seq

  response = client.post('/admin/api/character-animator/data', json={
    'def_id': 'def1',
    'seq_id': 'seq1'
  })

  assert response.status_code == 200
  data = response.get_json()
  assert data['definition']['key'] == 'def1'
  assert data['sequence']['key'] == 'seq1'

def test_character_animator_api_missing_args(client, monkeypatch):
  _mock_admin_session(monkeypatch)
  response = client.post('/admin/api/character-animator/data', json={})
  assert response.status_code == 400

@patch('services.firestore.get_posable_character_def')
@patch('services.firestore.get_posable_character_sequence')
def test_character_animator_api_not_found(mock_get_seq, mock_get_def, client, monkeypatch):
  _mock_admin_session(monkeypatch)
  mock_get_def.return_value = None
  mock_get_seq.return_value = None

  response = client.post('/admin/api/character-animator/data', json={
    'def_id': 'bad_def',
    'seq_id': 'bad_seq'
  })
  assert response.status_code == 404

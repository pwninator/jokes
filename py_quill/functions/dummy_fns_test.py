import json
import unittest
from unittest.mock import MagicMock, patch

from functions import dummy_fns


class TestDummyEndpoint(unittest.TestCase):

  @patch('functions.dummy_fns.cloud_storage.get_signed_url')
  @patch('functions.dummy_fns.gen_audio.generate_multi_turn_dialog')
  def test_post_request_generates_audio_json(self, mock_generate_dialog,
                                             mock_get_signed_url):
    mock_generate_dialog.return_value = ("gs://gen_audio/fake.wav", MagicMock())
    mock_get_signed_url.return_value = "http://example.com/fake.wav"

    req = MagicMock()
    req.method = 'POST'
    req.path = '/dummy_endpoint'
    req.is_json = True
    req.headers = {}
    req.get_json.return_value = {
      "data": {
        "script": "Alice: Hello\nBob: Hi",
        "speaker1_name": "Alice",
        "speaker1_voice": "GEMINI_KORE",
        "speaker2_name": "Bob",
        "speaker2_voice": "GEMINI_PUCK",
      }
    }
    req.args = {}

    resp = dummy_fns.dummy_endpoint(req)

    self.assertEqual(resp.status_code, 200)
    payload = json.loads(resp.data.decode("utf-8"))
    self.assertIn("data", payload)
    self.assertEqual(payload["data"]["audio_url"], "http://example.com/fake.wav")
    self.assertEqual(payload["data"]["audio_gcs_uri"], "gs://gen_audio/fake.wav")

    mock_generate_dialog.assert_called_once()
    called_kwargs = mock_generate_dialog.call_args.kwargs
    self.assertEqual(called_kwargs["script"], "Alice: Hello\nBob: Hi")
    self.assertEqual(called_kwargs["speakers"], {
      "Alice": dummy_fns.gen_audio.Voice.GEMINI_KORE,
      "Bob": dummy_fns.gen_audio.Voice.GEMINI_PUCK,
    })

  def test_get_request_returns_form(self):
    req = MagicMock()
    req.method = 'GET'
    req.path = '/dummy_endpoint'
    req.headers = {}

    resp = dummy_fns.dummy_endpoint(req)

    self.assertEqual(resp.status_code, 200)
    self.assertIn(b'Generate Multi-Speaker Audio', resp.data)
    self.assertIn(b'<form id="genForm">', resp.data)
    self.assertIn(b'<textarea id="script"', resp.data)
    self.assertIn(b'name="speaker1_name"', resp.data)
    self.assertIn(b'name="speaker1_voice"', resp.data)
    self.assertIn(b'name="speaker2_name"', resp.data)
    self.assertIn(b'name="speaker2_voice"', resp.data)
    self.assertIn(b'fetch(window.location.href', resp.data)

import unittest
from unittest.mock import MagicMock, patch
from functions import dummy_fns
from common import models
from agents import constants

class TestDummyEndpoint(unittest.TestCase):
    @patch('functions.dummy_fns._select_image_client')
    def test_post_request_generates_images(self, mock_select_client):
        mock_client = MagicMock()
        mock_select_client.return_value = mock_client

        mock_setup_image = MagicMock(spec=models.Image)
        mock_setup_image.url = "http://example.com/setup.png"
        mock_setup_image.gcs_uri = "gs://bucket/setup.png"
        mock_setup_image.custom_temp_data = {
            "image_generation_call_id": "call-123"
        }

        mock_punchline_image = MagicMock(spec=models.Image)
        mock_punchline_image.url = "http://example.com/punchline.png"
        mock_punchline_image.custom_temp_data = {}

        mock_client.generate_image.side_effect = [
            mock_setup_image,
            mock_punchline_image,
        ]

        # Create a mock request
        req = MagicMock()
        req.method = 'POST'
        req.path = '/dummy_endpoint'
        req.is_json = False
        req.args = {}
        # Mock form data
        req.form = {
            'setup_image_prompt': 'Setup prompt',
            'punchline_image_prompt': 'Punch prompt',
            'setup_reference_images': [
                constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS[0],
                constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS[1],
            ],
            'punchline_reference_images': [
                constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS[2],
            ],
            'include_setup_image': 'true',
            'image_quality': 'low'
        }

        # Call the function
        resp = dummy_fns.dummy_endpoint(req)

        # Verify response
        self.assertEqual(resp.status_code, 200)
        # Check if response data contains the image URL and input values
        # Response data is bytes in werkzeug/flask
        self.assertIn(b'http://example.com/setup.png', resp.data)
        self.assertIn(b'http://example.com/punchline.png', resp.data)
        self.assertIn(b'Setup prompt', resp.data)
        self.assertIn(b'Punch prompt', resp.data)

        mock_select_client.assert_called_once_with('low')
        self.assertEqual(mock_client.generate_image.call_count, 2)

        first_call = mock_client.generate_image.call_args_list[0]
        self.assertEqual(first_call.args[0], 'Setup prompt')
        self.assertEqual(first_call.args[1], [
            constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS[0],
            constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS[1],
        ])
        self.assertEqual(first_call.kwargs['save_to_firestore'], False)

        second_call = mock_client.generate_image.call_args_list[1]
        self.assertEqual(second_call.args[0], 'Punch prompt')
        self.assertEqual(second_call.args[1], [
            constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS[2],
            'call-123',
        ])
        self.assertEqual(second_call.kwargs['save_to_firestore'], False)

    def test_get_request_returns_form(self):
        req = MagicMock()
        req.method = 'GET'
        req.path = '/dummy_endpoint'

        resp = dummy_fns.dummy_endpoint(req)

        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'<form method="POST">', resp.data)
        self.assertIn(b'Generate Pun Images', resp.data)
        self.assertIn(b'<textarea name="setup_image_prompt"', resp.data)
        self.assertIn(b'<textarea name="punchline_image_prompt"', resp.data)
        self.assertIn(b'name="setup_reference_images"', resp.data)
        self.assertIn(b'name="punchline_reference_images"', resp.data)
        self.assertIn(b'name="include_setup_image"', resp.data)
        self.assertIn(b'A whimsical and silly sketch', resp.data)
        self.assertIn(b'SETUP_IMAGE_DESCRIPTION_HERE', resp.data)
        self.assertIn(b'PUNCHLINE_IMAGE_DESCRIPTION_HERE', resp.data)
        self.assertIn(constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS[0].encode(), resp.data)

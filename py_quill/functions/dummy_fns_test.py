import unittest
from unittest.mock import MagicMock, patch
from functions import dummy_fns
from common import models
from agents import constants

class TestDummyEndpoint(unittest.TestCase):
    @patch('functions.dummy_fns.image_generation.generate_pun_image')
    def test_post_request_generates_image(self, mock_generate_image):
        # Mock the image generation return value
        mock_image = MagicMock(spec=models.Image)
        mock_image.url = "http://example.com/image.png"
        mock_generate_image.return_value = mock_image

        # Create a mock request
        req = MagicMock()
        req.method = 'POST'
        req.path = '/dummy_endpoint'
        req.is_json = False
        req.args = {}
        # Mock form data
        req.form = {
            'image_description': 'A funny cat',
            'pun_text': 'Meow',
            'image_quality': 'low'
        }

        # Call the function
        resp = dummy_fns.dummy_endpoint(req)

        # Verify response
        self.assertEqual(resp.status_code, 200)
        # Check if response data contains the image URL and input values
        # Response data is bytes in werkzeug/flask
        self.assertIn(b'http://example.com/image.png', resp.data)
        self.assertIn(b'A funny cat', resp.data)
        self.assertIn(b'Meow', resp.data)

        # Verify generate_pun_image was called correctly
        mock_generate_image.assert_called_once()
        _, kwargs = mock_generate_image.call_args
        self.assertEqual(kwargs['pun_text'], 'Meow')
        self.assertEqual(kwargs['image_description'], 'A funny cat')
        self.assertEqual(kwargs['image_quality'], 'low')
        # Check that style reference images were passed
        self.assertEqual(kwargs['style_reference_images'], constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS)

    def test_get_request_returns_form(self):
        req = MagicMock()
        req.method = 'GET'
        req.path = '/dummy_endpoint'

        resp = dummy_fns.dummy_endpoint(req)

        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'<form method="POST">', resp.data)
        self.assertIn(b'Generate Pun Image', resp.data)
        self.assertIn(b'<textarea name="image_description"', resp.data)

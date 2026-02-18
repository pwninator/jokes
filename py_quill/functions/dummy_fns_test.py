import json
import unittest
from unittest.mock import MagicMock, patch

from functions import dummy_fns
from services import amazon


class TestDummyEndpoint(unittest.TestCase):

  def test_get_request_returns_usage_message(self):
    req = MagicMock()
    req.method = "GET"
    req.path = "/dummy_endpoint"
    req.headers = {}

    resp = dummy_fns.dummy_endpoint(req)

    self.assertEqual(resp.status_code, 200)
    html = resp.data.decode("utf-8")
    self.assertEqual(resp.mimetype, "text/html")
    self.assertIn("Fetch Amazon Ads Profiles", html)
    self.assertIn("form method=\"post\"", html)
    self.assertIn("<option value=\"all\" selected>all</option>", html)

  @patch("functions.dummy_fns.amazon.get_profiles")
  def test_post_request_lists_profiles(self, mock_get_profiles):
    mock_get_profiles.return_value = [
      amazon.AmazonAdsProfile(
        profile_id="42",
        region="na",
        api_base="https://advertising-api.amazon.com",
        country_code="US",
      ),
      amazon.AmazonAdsProfile(
        profile_id="99",
        region="eu",
        api_base="https://advertising-api-eu.amazon.com",
        country_code="GB",
      ),
    ]

    req = MagicMock()
    req.method = "POST"
    req.path = "/dummy_endpoint"
    req.is_json = True
    req.headers = {}
    req.get_json.return_value = {"data": {"region": "all"}}
    req.args = {}

    resp = dummy_fns.dummy_endpoint(req)

    self.assertEqual(resp.status_code, 200)
    html = resp.data.decode("utf-8")
    self.assertIn("Amazon Ads Profiles", html)
    self.assertIn("<strong>Requested Region:</strong> all", html)
    self.assertIn("<strong>Profile Count:</strong> 2", html)
    self.assertIn("42", html)
    self.assertIn("99", html)
    self.assertIn("US", html)
    self.assertIn("GB", html)
    mock_get_profiles.assert_called_once_with(region="all")

  @patch("functions.dummy_fns.amazon.get_profiles")
  def test_post_request_invalid_region_returns_400(self, mock_get_profiles):
    mock_get_profiles.side_effect = ValueError(
      "Invalid region 'unknown'. Allowed values: eu, fe, na")

    req = MagicMock()
    req.method = "POST"
    req.path = "/dummy_endpoint"
    req.is_json = True
    req.headers = {}
    req.get_json.return_value = {"data": {"region": "unknown"}}
    req.args = {}

    resp = dummy_fns.dummy_endpoint(req)

    self.assertEqual(resp.status_code, 400)
    payload = json.loads(resp.data.decode("utf-8"))
    self.assertIn("Invalid region", payload["data"]["error"])

  @patch("functions.dummy_fns.amazon.get_profiles")
  def test_post_request_amazon_error_returns_502(self, mock_get_profiles):
    mock_get_profiles.side_effect = amazon.AmazonAdsError("Request failed")

    req = MagicMock()
    req.method = "POST"
    req.path = "/dummy_endpoint"
    req.is_json = True
    req.headers = {}
    req.get_json.return_value = {"data": {"region": "all"}}
    req.args = {}

    resp = dummy_fns.dummy_endpoint(req)

    self.assertEqual(resp.status_code, 502)
    payload = json.loads(resp.data.decode("utf-8"))
    self.assertEqual(payload["data"]["error_type"], "amazon_api_error")
    self.assertIn("Request failed", payload["data"]["error"])

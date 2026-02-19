import json
import unittest
from unittest.mock import MagicMock, patch

from functions import dummy_fns


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
    self.assertIn("joke book", html)
    self.assertIn("joke book for 5 year old", html)
    self.assertIn("easy to read joke book", html)

  def test_post_request_lists_profiles(self):
    req = MagicMock()
    req.method = "POST"
    req.path = "/dummy_endpoint"
    req.headers = {}

    resp = dummy_fns.dummy_endpoint(req)

    self.assertEqual(resp.status_code, 405)
    payload = json.loads(resp.data.decode("utf-8"))
    self.assertIn("Only GET requests are supported", payload["data"]["error"])

  def test_post_request_invalid_region_returns_400(self):
    req = MagicMock()
    req.method = "POST"
    req.path = "/dummy_endpoint"
    req.headers = {}

    resp = dummy_fns.dummy_endpoint(req)

    self.assertEqual(resp.status_code, 405)
    payload = json.loads(resp.data.decode("utf-8"))
    self.assertIn("Only GET requests are supported", payload["data"]["error"])

  def test_post_request_amazon_error_returns_502(self):
    req = MagicMock()
    req.method = "POST"
    req.path = "/dummy_endpoint"
    req.headers = {}

    resp = dummy_fns.dummy_endpoint(req)

    self.assertEqual(resp.status_code, 405)
    payload = json.loads(resp.data.decode("utf-8"))
    self.assertEqual(payload["data"]["error_type"], "invalid_request")
    self.assertIn("Only GET requests are supported", payload["data"]["error"])

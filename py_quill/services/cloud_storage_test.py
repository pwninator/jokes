"""Tests for the cloud_storage module."""

from services import cloud_storage


def test_extract_gcs_uri_from_image_url_gcs_uri_format():
  """Test extracting GCS URI from GCS URI format."""
  input_url = "gs://test-bucket/filename.png"
  expected = "gs://test-bucket/filename.png"
  result = cloud_storage.extract_gcs_uri_from_image_url(input_url)
  assert result == expected


def test_extract_gcs_uri_from_image_url_direct_gcs_url(monkeypatch):
  """Test extracting GCS URI from direct GCS URL format."""
  # Mock the config to return a test bucket name
  monkeypatch.setattr("services.cloud_storage.config.IMAGE_BUCKET_NAME",
                      "test-bucket")

  input_url = "https://storage.googleapis.com/some-bucket/filename.png"
  expected = "gs://test-bucket/filename.png"
  result = cloud_storage.extract_gcs_uri_from_image_url(input_url)
  assert result == expected


def test_extract_gcs_uri_from_image_url_cdn_url(monkeypatch):
  """Test extracting GCS URI from CDN URL format."""
  # Mock the config to return a test bucket name
  monkeypatch.setattr("services.cloud_storage.config.IMAGE_BUCKET_NAME",
                      "test-bucket")

  input_url = "https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/pun_agent_image_20250906_210524_983216.png"
  expected = "gs://test-bucket/pun_agent_image_20250906_210524_983216.png"
  result = cloud_storage.extract_gcs_uri_from_image_url(input_url)
  assert result == expected


def test_extract_gcs_uri_from_image_url_emulator_url(monkeypatch):
  """Test extracting GCS URI from emulator URL format."""
  # Mock the config to return a test bucket name
  monkeypatch.setattr("services.cloud_storage.config.IMAGE_BUCKET_NAME",
                      "test-bucket")

  input_url = "http://10.0.2.2:9199/images.quillsstorybook.com/pun_agent_image_20250907_204036_897106.png"
  expected = "gs://test-bucket/pun_agent_image_20250907_204036_897106.png"
  result = cloud_storage.extract_gcs_uri_from_image_url(input_url)
  assert result == expected


def test_extract_gcs_uri_from_image_url_any_url_format(monkeypatch):
  """Test extracting GCS URI from any URL format."""
  # Mock the config to return a test bucket name
  monkeypatch.setattr("services.cloud_storage.config.IMAGE_BUCKET_NAME",
                      "test-bucket")

  input_url = "https://example.com/some/random/path/image.jpg"
  expected = "gs://test-bucket/image.jpg"
  result = cloud_storage.extract_gcs_uri_from_image_url(input_url)
  assert result == expected

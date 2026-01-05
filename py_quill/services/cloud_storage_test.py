"""Tests for the cloud_storage module."""

from io import BytesIO

from PIL import Image
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


def test_extract_gcs_uri_from_image_url_cdn_nested_path(monkeypatch):
  """Test extracting GCS URI from CDN URL with nested object path."""
  monkeypatch.setattr("services.cloud_storage.config.IMAGE_BUCKET_NAME",
                      "images.quillsstorybook.com")

  input_url = ("https://images.quillsstorybook.com/cdn-cgi/image/"
               "width=4096,format=auto,quality=75/"
               "pun_agent_image_20250831_205102_920445_upscale_4096.png/"
               "1759042812664/sample_0.png")
  expected = ("gs://images.quillsstorybook.com/"
              "pun_agent_image_20250831_205102_920445_upscale_4096.png/"
              "1759042812664/sample_0.png")

  result = cloud_storage.extract_gcs_uri_from_image_url(input_url)
  assert result == expected


def test_get_cdn_url_params_basic():
  """Test extracting params from a CDN URL."""
  cdn_url = "https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/image_file.png"
  result = cloud_storage.get_cdn_url_params(cdn_url)

  assert result == {'width': '1024', 'format': 'auto', 'quality': '75'}


def test_get_cdn_url_params_different_values():
  """Test extracting params with different values."""
  cdn_url = "https://images.quillsstorybook.com/cdn-cgi/image/width=2048,format=png,quality=90/different_image.jpg"
  result = cloud_storage.get_cdn_url_params(cdn_url)

  assert result == {'width': '2048', 'format': 'png', 'quality': '90'}


def test_get_cdn_url_params_invalid_url():
  """Test that invalid CDN URL raises ValueError."""
  invalid_url = "https://example.com/image.png"

  try:
    cloud_storage.get_cdn_url_params(invalid_url)
    assert False, "Should have raised ValueError"
  except ValueError as e:
    assert "Invalid CDN URL format" in str(e)


def test_set_cdn_url_params_change_format(monkeypatch):
  """Test changing format param while keeping others."""
  monkeypatch.setattr("services.cloud_storage.config.IMAGE_BUCKET_NAME",
                      "test-bucket")

  cdn_url = "https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/image.png"
  result = cloud_storage.set_cdn_url_params(cdn_url, image_format='png')

  # Should have png format and original width/quality
  assert 'format=png' in result
  assert 'width=1024' in result
  assert 'quality=75' in result


def test_set_cdn_url_params_change_width(monkeypatch):
  """Test changing width param while keeping others."""
  monkeypatch.setattr("services.cloud_storage.config.IMAGE_BUCKET_NAME",
                      "test-bucket")

  cdn_url = "https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/image.png"
  result = cloud_storage.set_cdn_url_params(cdn_url, width=2048)

  # Should have new width and original format/quality
  assert 'width=2048' in result
  assert 'format=auto' in result
  assert 'quality=75' in result


def test_set_cdn_url_params_multiple_changes(monkeypatch):
  """Test changing multiple params at once."""
  monkeypatch.setattr("services.cloud_storage.config.IMAGE_BUCKET_NAME",
                      "test-bucket")

  cdn_url = "https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/image.png"
  result = cloud_storage.set_cdn_url_params(cdn_url,
                                            width=2048,
                                            image_format='png',
                                            quality=90)

  # Should have all new values
  assert 'width=2048' in result
  assert 'format=png' in result
  assert 'quality=90' in result


def _make_png_bytes(color: str = "red",
                    size: tuple[int, int] = (4, 4)) -> bytes:
  """Helper to construct in-memory PNG bytes for image download tests."""
  buffer = BytesIO()
  Image.new('RGB', size, color=color).save(buffer, format='PNG')
  return buffer.getvalue()


def test_download_image_from_gcs_accepts_gcs_uri(monkeypatch):
  """download_image_from_gcs should handle native gs:// URIs."""
  expected_uri = "gs://test-bucket/sample.png"
  png_bytes = _make_png_bytes(color="green")

  def fake_download_bytes(gcs_uri: str) -> bytes:
    assert gcs_uri == expected_uri
    return png_bytes

  monkeypatch.setattr(cloud_storage, "download_bytes_from_gcs",
                      fake_download_bytes)

  image = cloud_storage.download_image_from_gcs(expected_uri)

  assert image.size == (4, 4)
  assert image.mode == "RGB"


def test_download_image_from_gcs_accepts_http_url(monkeypatch):
  """download_image_from_gcs should resolve URLs to GCS URIs before download."""
  http_url = "https://images.quillsstorybook.com/some/path/image.png"
  resolved_uri = "gs://images.quillsstorybook.com/some/path/image.png"
  png_bytes = _make_png_bytes(color="blue")
  captured_url: dict[str, str] = {}

  def fake_extract(url: str) -> str:
    captured_url["url"] = url
    return resolved_uri

  def fake_download_bytes(gcs_uri: str) -> bytes:
    assert gcs_uri == resolved_uri
    return png_bytes

  monkeypatch.setattr(cloud_storage, "extract_gcs_uri_from_image_url",
                      fake_extract)
  monkeypatch.setattr(cloud_storage, "download_bytes_from_gcs",
                      fake_download_bytes)

  image = cloud_storage.download_image_from_gcs(http_url)

  assert captured_url["url"] == http_url
  assert image.size == (4, 4)
  assert image.mode == "RGB"


def test_get_storage_googleapis_public_url_formats_url():
  gcs_uri = "gs://test-bucket/path/to/file.pdf"
  result = cloud_storage.get_public_cdn_url(gcs_uri)
  assert result == "http://storage.googleapis.com/test-bucket/path/to/file.pdf"


def test_gcs_file_exists_delegates_to_gcs_blob(monkeypatch):

  class FakeBlob:

    def __init__(self, exists_value: bool):
      self._exists_value = exists_value

    def exists(self) -> bool:
      return self._exists_value

  class FakeBucket:

    def __init__(self, exists_value: bool):
      self._exists_value = exists_value

    def blob(self, blob_name: str) -> FakeBlob:
      assert blob_name == "path/to/file.pdf"
      return FakeBlob(self._exists_value)

  class FakeClient:

    def __init__(self, exists_value: bool):
      self._exists_value = exists_value

    def bucket(self, bucket_name: str) -> FakeBucket:
      assert bucket_name == "test-bucket"
      return FakeBucket(self._exists_value)

  monkeypatch.setattr(cloud_storage, "client", lambda: FakeClient(True))
  assert cloud_storage.gcs_file_exists(
    "gs://test-bucket/path/to/file.pdf") is True

  monkeypatch.setattr(cloud_storage, "client", lambda: FakeClient(False))
  assert cloud_storage.gcs_file_exists(
    "gs://test-bucket/path/to/file.pdf") is False

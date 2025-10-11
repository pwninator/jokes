"""Cloud Storage service."""

import datetime

from common import config, utils
from google.cloud import storage as gcs

_client = None  # pylint: disable=invalid-name


def client() -> gcs.Client:
  """Get the Google Cloud Storage client."""
  global _client  # pylint: disable=global-statement
  if _client is None:
    _client = gcs.Client(project=config.PROJECT_ID)
  return _client


def parse_gcs_uri(gcs_uri: str) -> tuple[str, str]:
  """Parse a GCS URI into (bucket_name, blob_name).

  Args:
    gcs_uri: The GCS URI (gs://bucket/path/to/object)

  Returns:
    A tuple of (bucket_name, blob_name)

  Raises:
    ValueError: If the GCS URI format is invalid
  """
  if not gcs_uri.startswith("gs://"):
    raise ValueError(f"Invalid GCS URI format: {gcs_uri}")

  uri_parts = gcs_uri.removeprefix("gs://").split("/", 1)
  if len(uri_parts) != 2:
    raise ValueError(f"Invalid GCS URI format: {gcs_uri}")

  return uri_parts[0], uri_parts[1]


def upload_bytes_to_gcs(
  content_bytes: bytes,
  gcs_uri: str,
  content_type: str,
) -> str:
  """Upload bytes to Google Cloud Storage.
  
  Args:
    content_bytes: The data as bytes
    gcs_uri: The target GCS URI (gs://bucket/path/file.ext)
    content_type: The MIME type of the data
    
  Returns:
    The final GCS URI of the uploaded file
    
  Raises:
    ValueError: If the GCS URI format is invalid
  """
  bucket_name, blob_name = parse_gcs_uri(gcs_uri)

  # Get bucket and blob references
  bucket = client().bucket(bucket_name)
  blob = bucket.blob(blob_name)

  # Upload the bytes with specified content type
  blob.upload_from_string(content_bytes, content_type=content_type)

  return gcs_uri


def upload_file_to_gcs(
  file_path: str,
  gcs_uri: str,
  content_type: str = None,
) -> str:
  """Upload a file to Google Cloud Storage.
  
  Args:
    file_path: The local file path to upload
    gcs_uri: The target GCS URI (gs://bucket/path/file.ext)
    content_type: The MIME type of the file (optional)
    
  Returns:
    The final GCS URI of the uploaded file
    
  Raises:
    ValueError: If the GCS URI format is invalid
  """
  bucket_name, blob_name = parse_gcs_uri(gcs_uri)

  # Get bucket and blob references
  bucket = client().bucket(bucket_name)
  blob = bucket.blob(blob_name)

  # Upload the file
  blob.upload_from_filename(file_path, content_type=content_type)

  return gcs_uri


def download_bytes_from_gcs(gcs_uri: str) -> bytes:
  """Download bytes from Google Cloud Storage.

  Args:
    gcs_uri: The source GCS URI (gs://bucket/path/file.ext)

  Returns:
    The content as bytes

  Raises:
    ValueError: If the GCS URI format is invalid
  """
  bucket_name, blob_name = parse_gcs_uri(gcs_uri)

  # Get bucket and blob references
  bucket = client().bucket(bucket_name)
  blob = bucket.blob(blob_name)

  # Download the bytes
  return blob.download_as_bytes()


def get_audio_gcs_uri(file_name_base: str, extension: str) -> str:
  """Get a GCS URI for an audio file."""
  return get_gcs_uri(config.AUDIO_BUCKET_NAME, file_name_base, extension)


def get_image_gcs_uri(file_name_base: str, extension: str) -> str:
  """Get a GCS URI for an image file."""
  return get_gcs_uri(config.IMAGE_BUCKET_NAME, file_name_base, extension)


def get_gcs_uri(bucket: str, file_name_base: str, extension: str) -> str:
  """Get a GCS URI for a file in the given bucket."""
  timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
  filename = f"{file_name_base}_{timestamp}.{extension}"
  return f"gs://{bucket}/{filename}"


def extract_gcs_uri_from_image_url(image_url: str) -> str:
  """Extract GCS URI from image URL by getting the filename and using IMAGE_BUCKET_NAME.
  
  Args:
    image_url: Any image URL format
    
  Returns:
    The GCS URI (gs://IMAGE_BUCKET_NAME/filename)
  """
  # Handle GCS URI format (already correct)
  if image_url.startswith("gs://"):
    return image_url

  # Extract filename from any URL format
  filename = image_url.split("/")[-1]
  return f"gs://{config.IMAGE_BUCKET_NAME}/{filename}"


def get_signed_url(gcs_uri: str) -> str:
  """Get a signed URL for a GCS URI.

  Args:
    gcs_uri: The source GCS URI (gs://bucket/path/file.ext)

  Returns:
    A time-limited signed HTTPS URL to access the object

  Raises:
    ValueError: If the GCS URI format is invalid
  """
  bucket_name, blob_name = parse_gcs_uri(gcs_uri)

  # Get bucket and blob references
  bucket = client().bucket(bucket_name)
  blob = bucket.blob(blob_name)

  # Generate a V4 signed URL for GET with a 60-minute expiration
  return blob.generate_signed_url(
    version="v4",
    expiration=datetime.timedelta(minutes=60),
    method="GET",
  )


def get_public_url(gcs_uri: str) -> str:
  """Get a public URL for a GCS URI."""
  bucket_name, blob_name = parse_gcs_uri(gcs_uri)
  bucket = client().bucket(bucket_name)
  blob = bucket.blob(blob_name)
  return blob.public_url


def get_emulator_accessible_url(gcs_uri: str) -> str:
  """Get a public URL for a GCS URI that is accessible from the emulator."""
  public_url = get_public_url(gcs_uri)
  # Emulator uses 10.0.2.2 instead of 127.0.0.1
  return public_url.replace("127.0.0.1", "10.0.2.2")


def get_public_image_cdn_url(
  gcs_uri: str,
  width: int = 1024,
  image_format: str = "auto",
  quality: int = 75,
) -> str:
  """Get a public CDN URL for an image."""
  bucket_name, object_path = parse_gcs_uri(gcs_uri)
  del bucket_name
  return f"https://images.quillsstorybook.com/cdn-cgi/image/width={width},format={image_format},quality={quality}/{object_path}"


def get_final_image_url(gcs_uri: str, width: int = 1024) -> str:
  """Get the final image URL for an image."""
  if utils.is_emulator():
    # In emulator mode, the image is not accessible via CDN
    return get_emulator_accessible_url(gcs_uri)
  else:
    return get_public_image_cdn_url(gcs_uri, width=width)



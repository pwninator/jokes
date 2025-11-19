"""Tests for Firestore migrations in util_fns.py."""

from io import BytesIO
from typing import Iterable
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from common import models
from functions import util_fns


def _create_sample_png_bytes(color: tuple[int, int, int] = (255, 0, 0)) -> bytes:
  image = Image.new('RGB', (4, 4), color=color)
  buffer = BytesIO()
  image.save(buffer, format='PNG')
  return buffer.getvalue()


def _create_punny_joke(joke_id: str) -> models.PunnyJoke:
  return models.PunnyJoke(
    key=joke_id,
    setup_text=f"Setup {joke_id}",
    punchline_text=f"Punchline {joke_id}",
    setup_image_url=f"https://cdn.example.com/{joke_id}_setup.png",
    punchline_image_url=f"https://cdn.example.com/{joke_id}_punchline.png",
  )


def _build_snapshot(*, exists: bool, data: dict | None = None):
  snapshot = MagicMock()
  snapshot.exists = exists
  snapshot.to_dict.return_value = data or {}
  return snapshot


def _build_doc(snapshot) -> MagicMock:
  doc = MagicMock()
  doc.get.return_value = snapshot
  return doc


def _side_effect(values: Iterable):
  iterator = iter(values)

  def _inner(*_args, **_kwargs):
    return next(iterator)

  return _inner


@pytest.fixture(name='mock_editor_class')
def mock_editor_class_fixture():
  with patch('functions.util_fns.image_editor.ImageEditor') as mock_class:
    editor_instance = MagicMock()
    editor_instance.enhance_image.side_effect = lambda img: img
    mock_class.return_value = editor_instance
    yield mock_class


@pytest.fixture(name='mock_firestore_get_all')
def mock_firestore_get_all_fixture():
  with patch('functions.util_fns.firestore_service.get_all_punny_jokes') as mock:
    yield mock


@pytest.fixture(name='mock_firestore_upsert')
def mock_firestore_upsert_fixture():
  with patch('functions.util_fns.firestore_service.upsert_punny_joke') as mock:
    yield mock


@pytest.fixture(name='mock_cloud_storage')
def mock_cloud_storage_fixture():
  with patch('functions.util_fns.cloud_storage.extract_gcs_uri_from_image_url'
             ) as mock_extract, \
      patch('functions.util_fns.cloud_storage.download_bytes_from_gcs'
            ) as mock_download, \
      patch('functions.util_fns.cloud_storage.upload_bytes_to_gcs'
            ) as mock_upload, \
      patch('functions.util_fns.cloud_storage.get_gcs_uri'
            ) as mock_get_gcs_uri, \
      patch('functions.util_fns.cloud_storage.get_final_image_url'
            ) as mock_final_url:
    yield {
        'extract': mock_extract,
        'download': mock_download,
        'upload': mock_upload,
        'get_gcs_uri': mock_get_gcs_uri,
        'final_url': mock_final_url,
    }


def test_image_migration_updates_images_and_marks_metadata(
  mock_editor_class: MagicMock,
  mock_firestore_get_all: MagicMock,
  mock_firestore_upsert: MagicMock,
  mock_cloud_storage: dict,
):
  joke = _create_punny_joke("j1")
  mock_firestore_get_all.return_value = [joke]

  snapshot = _build_snapshot(exists=False)
  doc = _build_doc(snapshot)

  with patch('functions.util_fns._get_migrations_doc_ref',
             return_value=doc) as mock_get_doc:
    mock_cloud_storage['extract'].side_effect = [
        'gs://bucket/j1_setup.png', 'gs://bucket/j1_punchline.png'
    ]
    sample_bytes = _create_sample_png_bytes()
    mock_cloud_storage['download'].side_effect = [sample_bytes, sample_bytes]
    mock_cloud_storage['get_gcs_uri'].side_effect = [
        'gs://bucket/enhanced_setup.png', 'gs://bucket/enhanced_punchline.png'
    ]
    mock_cloud_storage['final_url'].side_effect = [
        'https://cdn/enhanced_setup.png', 'https://cdn/enhanced_punchline.png'
    ]

    html_response = util_fns.run_image_enhancement_migration(
      dry_run=False,
      max_jokes=0,
    )

  mock_get_doc.assert_called_once_with('j1')
  assert mock_cloud_storage['upload'].call_count == 2
  mock_firestore_upsert.assert_called_once_with(joke)
  doc.set.assert_called_once_with({'image_enhancement': True}, merge=True)
  assert joke.setup_image_url == 'https://cdn/enhanced_setup.png'
  assert joke.punchline_image_url == 'https://cdn/enhanced_punchline.png'
  assert "Updated Jokes (1)" in html_response


def test_image_migration_skips_when_already_migrated(
  mock_editor_class: MagicMock,
  mock_firestore_get_all: MagicMock,
  mock_firestore_upsert: MagicMock,
  mock_cloud_storage: dict,
):
  del mock_cloud_storage
  joke = _create_punny_joke("j1")
  mock_firestore_get_all.return_value = [joke]

  snapshot = _build_snapshot(exists=True, data={'image_enhancement': True})
  doc = _build_doc(snapshot)

  with patch('functions.util_fns._get_migrations_doc_ref',
             return_value=doc), \
      patch('functions.util_fns.cloud_storage.upload_bytes_to_gcs') as mock_upload:
    html_response = util_fns.run_image_enhancement_migration(
      dry_run=False,
      max_jokes=0,
    )

  mock_firestore_upsert.assert_not_called()
  mock_upload.assert_not_called()
  assert "reason=already_migrated" in html_response


def test_image_migration_dry_run_no_side_effects(
  mock_editor_class: MagicMock,
  mock_firestore_get_all: MagicMock,
  mock_firestore_upsert: MagicMock,
  mock_cloud_storage: dict,
):
  joke = _create_punny_joke("j1")
  mock_firestore_get_all.return_value = [joke]
  snapshot = _build_snapshot(exists=False)
  doc = _build_doc(snapshot)

  with patch('functions.util_fns._get_migrations_doc_ref',
             return_value=doc), \
      patch('functions.util_fns.cloud_storage.upload_bytes_to_gcs') as mock_upload:
    html_response = util_fns.run_image_enhancement_migration(
      dry_run=True,
      max_jokes=0,
    )

  mock_editor_class.return_value.enhance_image.assert_not_called()
  mock_cloud_storage['download'].assert_not_called()
  mock_upload.assert_not_called()
  mock_firestore_upsert.assert_not_called()
  doc.set.assert_not_called()
  assert "Updated Jokes (1)" in html_response
  assert "dry_run=True" in html_response


def test_image_migration_respects_max_jokes(
  mock_editor_class: MagicMock,
  mock_firestore_get_all: MagicMock,
  mock_firestore_upsert: MagicMock,
  mock_cloud_storage: dict,
):
  joke1 = _create_punny_joke("j1")
  joke2 = _create_punny_joke("j2")
  mock_firestore_get_all.return_value = [joke1, joke2]

  snapshot1 = _build_snapshot(exists=False)
  snapshot2 = _build_snapshot(exists=False)
  doc1 = _build_doc(snapshot1)
  doc2 = _build_doc(snapshot2)

  with patch('functions.util_fns._get_migrations_doc_ref',
             side_effect=[doc1, doc2]) as mock_get_doc:
    sample_bytes = _create_sample_png_bytes()
    mock_cloud_storage['extract'].side_effect = _side_effect([
        'gs://bucket/j1_setup.png',
        'gs://bucket/j1_punchline.png',
    ])
    mock_cloud_storage['download'].side_effect = _side_effect(
      [sample_bytes, sample_bytes])
    mock_cloud_storage['get_gcs_uri'].side_effect = _side_effect([
        'gs://bucket/j1_setup_enhanced.png',
        'gs://bucket/j1_punchline_enhanced.png',
    ])
    mock_cloud_storage['final_url'].side_effect = _side_effect([
        'https://cdn/j1_setup_enhanced.png',
        'https://cdn/j1_punchline_enhanced.png',
    ])

    html_response = util_fns.run_image_enhancement_migration(
      dry_run=False,
      max_jokes=1,
    )

  assert mock_get_doc.call_count == 1
  assert mock_cloud_storage['upload'].call_count == 2
  assert mock_firestore_upsert.call_count == 1
  doc1.set.assert_called_once()
  assert "Updated Jokes (1)" in html_response

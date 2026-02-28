"""Tests for JokeCategory model."""

from common import models


def test_joke_category_key_generation_basic():
  cat = models.JokeCategory(display_name="Animal Jokes",
                            joke_description_query="animals")
  assert cat.key == "animal_jokes"


def test_joke_category_key_generation_special_chars():
  cat = models.JokeCategory(display_name="Spooky & Funny!",
                            joke_description_query="spooky")
  # non-alphanumerics become underscores, runs collapse, trimmed
  assert cat.key == "spooky_funny"


def test_joke_category_key_generation_leading_trailing():
  cat = models.JokeCategory(display_name="  $$ Seasonal %%  ",
                            joke_description_query="season")
  assert cat.key == "seasonal"


def test_joke_category_to_dict_contains_computed_key():
  cat = models.JokeCategory(display_name="Animal Jokes",
                            joke_description_query="animals")
  d = cat.to_dict()
  assert 'id' not in d
  assert 'jokes' not in d
  assert d['display_name'] == 'Animal Jokes'
  assert d['joke_description_query'] == 'animals'
  assert d['state'] == 'PROPOSED'


def test_joke_category_to_dict_includes_image_description_when_present():
  cat = models.JokeCategory(display_name="Animal Jokes",
                            joke_description_query="animals",
                            image_description="A cute animal collage")
  d = cat.to_dict()
  assert d['image_description'] == 'A cute animal collage'


def test_joke_category_from_firestore_dict_sets_id_and_defaults():
  cat = models.JokeCategory.from_firestore_dict(
    {
      'display_name': 'Cats',
      'state': 'APPROVED',
      'seasonal_name': 'Christmas',
      'joke_description_query': 'should_be_ignored',
      'search_distance': 0.33,
      'all_image_urls': ['https://a.png', 123, None],
    },
    key='cats',
  )
  assert cat.id == 'cats'
  assert cat.display_name == 'Cats'
  assert cat.state == 'APPROVED'
  assert cat.seasonal_name == 'Christmas'
  # seasonal_name can coexist with search query
  assert cat.joke_description_query == 'should_be_ignored'
  assert cat.search_distance == 0.33
  assert cat.all_image_urls == ['https://a.png']


def test_joke_category_from_firestore_dict_reads_lunchbox_pdf_uris():
  cat = models.JokeCategory.from_firestore_dict(
    {
      'display_name': 'Cats',
      'joke_description_query': 'cats',
      'lunchbox_notes_branded_pdf_gcs_uri': 'gs://bucket/cats_branded.pdf',
      'lunchbox_notes_unbranded_pdf_gcs_uri': 'gs://bucket/cats_unbranded.pdf',
    },
    key='cats',
  )
  assert cat.lunchbox_notes_branded_pdf_gcs_uri == (
    'gs://bucket/cats_branded.pdf')
  assert cat.lunchbox_notes_unbranded_pdf_gcs_uri == (
    'gs://bucket/cats_unbranded.pdf')

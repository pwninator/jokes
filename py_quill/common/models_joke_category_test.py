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
  assert d == {
    'key': 'animal_jokes',
    'display_name': 'Animal Jokes',
    'joke_description_query': 'animals',
  }


def test_joke_category_to_dict_includes_image_description_when_present():
  cat = models.JokeCategory(display_name="Animal Jokes",
                            joke_description_query="animals",
                            image_description="A cute animal collage")
  d = cat.to_dict()
  assert d == {
    'key': 'animal_jokes',
    'display_name': 'Animal Jokes',
    'joke_description_query': 'animals',
    'image_description': 'A cute animal collage',
  }

from pathlib import Path


def test_text_to_weighted_shapes_uses_bundled_nltk_data(monkeypatch):
  nltk_data_dir = Path(__file__).resolve().parents[1] / "nltk_data"
  assert nltk_data_dir.exists()

  monkeypatch.setenv("NLTK_DATA", str(nltk_data_dir))

  import nltk

  nltk.data.path = [p for p in nltk.data.path if p != str(nltk_data_dir)]

  from services import transcript_alignment

  transcript_alignment._g2p = None
  shapes = transcript_alignment.text_to_weighted_shapes("Hello world")

  assert shapes
  assert str(nltk_data_dir) in nltk.data.path

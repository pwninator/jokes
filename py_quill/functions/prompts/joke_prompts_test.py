"""Tests for joke_prompts.py."""


from . import joke_prompts


class TestJokePrompts:
  """Test suite for joke_prompts module."""

  def test_parse_jokes_basic_functionality(self):
    """Test basic functionality of parse_jokes with both is_final=True and is_final=False."""
    text = """- Joke 1: This is the first joke.
- Joke 2: This is the second joke.
- Joke 3: This is the third joke."""

    # Test with is_final=False
    jokes_not_final, remaining_not_final = joke_prompts.parse_jokes(text, is_final=False)

    assert len(jokes_not_final) == 2
    assert jokes_not_final[0] == "Joke 1: This is the first joke."
    assert jokes_not_final[1] == "Joke 2: This is the second joke."
    assert remaining_not_final == "- Joke 3: This is the third joke."

    # Test with is_final=True
    jokes_final, remaining_final = joke_prompts.parse_jokes(text, is_final=True)

    assert len(jokes_final) == 3
    assert jokes_final[0] == "Joke 1: This is the first joke."
    assert jokes_final[1] == "Joke 2: This is the second joke."
    assert jokes_final[2] == "Joke 3: This is the third joke."
    assert remaining_final == ""

  def test_parse_jokes_mixed_content(self):
    """Test parsing jokes with non-joke lines and mixed bullet formats."""
    text = """Here are some jokes about robots and hamsters:
- Why did the robot go to school? To improve its algorithm!
Some more jokes:
* What do you call a hamster with a black belt? Hamster Norris!
- Why did the glitchy robot bring a ladder to the bar? It heard the drinks were on the house!"""

    # Test with is_final=True
    jokes_final, remaining_final = joke_prompts.parse_jokes(text, is_final=True)

    assert len(jokes_final) == 3
    assert "Why did the robot go to school? To improve its algorithm!" in jokes_final
    assert "What do you call a hamster with a black belt? Hamster Norris!" in jokes_final
    assert "Why did the glitchy robot bring a ladder to the bar? It heard the drinks were on the house!" in jokes_final
    assert remaining_final == ""

    # Test with is_final=False
    jokes_not_final, remaining_not_final = joke_prompts.parse_jokes(text, is_final=False)

    assert len(jokes_not_final) == 2
    assert "Why did the robot go to school? To improve its algorithm!" in jokes_not_final
    assert "What do you call a hamster with a black belt? Hamster Norris!" in jokes_not_final
    assert remaining_not_final == "- Why did the glitchy robot bring a ladder to the bar? It heard the drinks were on the house!"

  def test_parse_jokes_with_streaming_chunks(self):
    """Test simulating streaming chunks that split a joke line."""
    # First chunk
    chunk1 = """- Why did the robot go to school? To improve its algorithm!
- What do you call a hamster with a black"""

    jokes1, remaining1 = joke_prompts.parse_jokes(chunk1, is_final=False)

    assert len(jokes1) == 1
    assert jokes1[0] == "Why did the robot go to school? To improve its algorithm!"
    assert remaining1 == "- What do you call a hamster with a black"

    # Second chunk (continuing)
    chunk2 = remaining1 + " belt? Hamster Norris!\n- Why did the glitchy robot"

    jokes2, remaining2 = joke_prompts.parse_jokes(chunk2, is_final=False)

    assert len(jokes2) == 1
    assert jokes2[0] == "What do you call a hamster with a black belt? Hamster Norris!"
    assert remaining2 == "- Why did the glitchy robot"

    # Third chunk (final)
    chunk3 = remaining2 + " bring a ladder to the bar? It heard the drinks were on the house!"

    jokes3, remaining3 = joke_prompts.parse_jokes(chunk3, is_final=True)

    assert len(jokes3) == 1
    assert jokes3[0] == "Why did the glitchy robot bring a ladder to the bar? It heard the drinks were on the house!"
    assert remaining3 == ""

  def test_edge_cases(self):
    """Test various edge cases."""
    # Empty text
    jokes, remaining = joke_prompts.parse_jokes("", is_final=True)
    assert len(jokes) == 0
    assert remaining == ""

    # Only short jokes (less than 5 chars)
    text_short = """- Why?
- No
- Hi"""
    jokes_short, remaining_short = joke_prompts.parse_jokes(text_short, is_final=True)
    assert len(jokes_short) == 0
    assert remaining_short == ""

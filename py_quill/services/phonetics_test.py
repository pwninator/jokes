"""Tests for the phonetics service."""

import pytest
from services import phonetics

def test_find_homophones_single_word():
    # 'read' -> 'red' (past tense) and 'reed' (present tense)
    homophones = phonetics.find_homophones("read")
    assert "red" in homophones
    assert "reed" in homophones
    assert "read" not in homophones

def test_find_homophones_multi_word():
    # 'lettuce' -> 'let us'
    # Now supported via destressed matching
    homophones = phonetics.find_homophones("lettuce")
    assert "let us" in homophones
    assert "lettuce" not in homophones

def test_find_rhymes_strict():
    # 'cat' -> 'bat', 'hat', etc.
    rhymes = phonetics.find_rhymes("cat")
    assert "bat" in rhymes
    assert "hat" in rhymes
    assert "cat" not in rhymes

    # Verify strict rhyme: 'orange' has no perfect rhymes in CMU dict usually
    rhymes_orange = phonetics.find_rhymes("orange")
    assert not rhymes_orange

def test_unknown_word_g2p_fallback():
    # 'bazinga' is likely not in CMU dict.
    matches = phonetics.get_phonetic_matches("bazinga")
    assert isinstance(matches, tuple)
    assert isinstance(matches[0], list)
    assert isinstance(matches[1], list)

def test_phrase_input():
    # 'hello world'
    matches = phonetics.get_phonetic_matches("hello world")
    assert isinstance(matches, tuple)

def test_case_insensitivity():
    h_lower = phonetics.find_homophones("read")
    h_upper = phonetics.find_homophones("READ")
    assert h_lower == h_upper

"""Phonetic service for finding rhymes and homophones (including multi-word)."""

import os
from collections import defaultdict
from pathlib import Path
from typing import Sequence

import nltk
from g2p_en import G2p

# Ensure bundled NLTK data (if present) is discoverable.
# This logic is duplicated from transcript_alignment.py to keep services independent.
_BUNDLED_NLTK_DATA_DIR = Path(__file__).resolve().parents[1] / "nltk_data"
if _BUNDLED_NLTK_DATA_DIR.exists():
    os.environ.setdefault("NLTK_DATA", str(_BUNDLED_NLTK_DATA_DIR))


def _ensure_nltk_data_path() -> None:
    nltk_data_dir = os.environ.get("NLTK_DATA")
    if not nltk_data_dir:
        return
    if nltk_data_dir not in nltk.data.path:
        nltk.data.path.insert(0, nltk_data_dir)


# Singleton instances
_G2P: G2p | None = None
_CMUDICT: dict[str, list[list[str]]] | None = None

# Indices for fast lookup
# Maps tuple of phonemes -> list of words
_PHONEMES_TO_WORDS: dict[tuple[str, ...], list[str]] = defaultdict(list)
# Maps rhyming part (tuple of phonemes) -> list of words
_RHYME_PART_TO_WORDS: dict[tuple[str, ...], list[str]] = defaultdict(list)
# Maps tuple of destressed phonemes -> list of words (for approximate homophones/oronyms)
_DESTRESSED_PHONEMES_TO_WORDS: dict[tuple[str, ...], list[str]] = defaultdict(list)


def _get_g2p() -> G2p:
    """Get or create the G2P converter singleton."""
    global _G2P
    if _G2P is None:
        _ensure_nltk_data_path()
        _G2P = G2p()
    return _G2P


def _strip_stress(phonemes: Sequence[str]) -> tuple[str, ...]:
    """Remove stress digits from phonemes (e.g., 'AH1' -> 'AH')."""
    return tuple("".join(c for c in p if not c.isdigit()) for p in phonemes)


def _load_dictionaries() -> None:
    """Load CMU dictionary and build indices if not already loaded."""
    global _CMUDICT
    if _CMUDICT is not None:
        return

    _ensure_nltk_data_path()
    try:
        _CMUDICT = nltk.corpus.cmudict.dict()
    except LookupError:
        nltk.download("cmudict")
        _CMUDICT = nltk.corpus.cmudict.dict()

    # Build indices
    for word, prons in _CMUDICT.items():
        # Filter out non-alpha keys (like "a.") to reduce noise
        if not word[0].isalpha():
            continue

        for p in prons:
            p_tuple = tuple(p)
            _PHONEMES_TO_WORDS[p_tuple].append(word)

            # Destressed index
            p_destressed = _strip_stress(p)
            _DESTRESSED_PHONEMES_TO_WORDS[p_destressed].append(word)

            rhyme_part = _get_rhyme_part(p)
            if rhyme_part:
                _RHYME_PART_TO_WORDS[rhyme_part].append(word)


def _get_rhyme_part(phonemes: Sequence[str]) -> tuple[str, ...] | None:
    """Extract the rhyming part (from the last stressed vowel)."""
    # Find the last syllable with primary (1) or secondary (2) stress
    for i in range(len(phonemes) - 1, -1, -1):
        phoneme = phonemes[i]
        # Check for stress marker (1 or 2)
        if "1" in phoneme or "2" in phoneme:
            return tuple(phonemes[i:])
    return None


def _get_pronunciations(text: str) -> list[list[str]]:
    """Get pronunciations for a word or phrase.

    Returns a list of phoneme sequences.
    For single words found in CMU dict, returns all known pronunciations.
    For unknown words or phrases, returns a single predicted pronunciation using G2P.
    """
    _load_dictionaries()
    assert _CMUDICT is not None

    text_lower = text.lower()

    # 1. Try direct CMU dict lookup (single word)
    if text_lower in _CMUDICT:
        return _CMUDICT[text_lower]

    # 2. Fallback to G2P (unknown word or phrase)
    g2p = _get_g2p()
    # g2p returns a list of phonemes.
    prediction = g2p(text)
    # Filter out non-phoneme characters (like punctuation or spaces if any)
    cleaned_prediction = [p for p in prediction if p != " " and p.isalnum()]

    if not cleaned_prediction:
        return []

    return [cleaned_prediction]


def _find_segmentations(
    phonemes: tuple[str, ...], memo: dict | None = None
) -> list[list[str]]:
    """Recursively find all ways to segment destressed phonemes into words.

    Returns a list of phrases, where each phrase is a list of words.
    """
    if memo is None:
        memo = {}

    if not phonemes:
        return [[]]

    if phonemes in memo:
        return memo[phonemes]

    valid_segmentations = []

    # Iterate through all possible split points
    for i in range(1, len(phonemes) + 1):
        prefix = phonemes[:i]
        suffix = phonemes[i:]

        # Check if prefix forms a word (using destressed index)
        if prefix in _DESTRESSED_PHONEMES_TO_WORDS:
            words_for_prefix = _DESTRESSED_PHONEMES_TO_WORDS[prefix]

            # Recurse on suffix
            suffix_segmentations = _find_segmentations(suffix, memo)

            # Combine
            for word in words_for_prefix:
                for suffix_seg in suffix_segmentations:
                    valid_segmentations.append([word] + suffix_seg)

    memo[phonemes] = valid_segmentations
    return valid_segmentations


def find_homophones(text: str) -> list[str]:
    """Find words or phrases that sound exactly like the input text.

    Includes multi-word segmentations (e.g., "lettuce" -> "let us").
    Excludes the input text itself.
    Uses destressed phonemes to allow flexibility in stress (e.g. for puns).
    """
    _load_dictionaries()
    prons = _get_pronunciations(text)
    if not prons:
        return []

    homophones = set()
    input_lower = text.lower()

    for p in prons:
        # Use destressed phonemes for homophone matching
        p_destressed = _strip_stress(p)

        # 1. Single word matches (via destressed index)
        candidates = _DESTRESSED_PHONEMES_TO_WORDS.get(p_destressed, [])
        for c in candidates:
            if c != input_lower:
                homophones.add(c)

        # 2. Multi-word segmentation
        if len(p_destressed) < 20:
            segmentations = _find_segmentations(p_destressed)
            for seg in segmentations:
                phrase = " ".join(seg)
                if phrase != input_lower:
                    homophones.add(phrase)

    return sorted(list(homophones))


def find_rhymes(text: str) -> list[str]:
    """Find words that strictly rhyme with the input text.

    Based on the last stressed vowel to the end of the word.
    Excludes the input text itself.
    """
    _load_dictionaries()
    prons = _get_pronunciations(text)
    if not prons:
        return []

    rhymes = set()
    input_lower = text.lower()

    for p in prons:
        rhyme_part = _get_rhyme_part(p)
        if rhyme_part:
            candidates = _RHYME_PART_TO_WORDS.get(rhyme_part, [])
            for c in candidates:
                if c != input_lower:
                    rhymes.add(c)

    return sorted(list(rhymes))


def get_phonetic_matches(text: str) -> tuple[list[str], list[str]]:
    """Get homophones and rhymes for the given text.

    Args:
        text: Input word or phrase.

    Returns:
        A tuple containing:
        - List of homophones (words/phrases that sound the same).
        - List of rhyming words.
    """
    homophones = find_homophones(text)
    rhymes = find_rhymes(text)
    return homophones, rhymes

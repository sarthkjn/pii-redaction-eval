"""Tests for the custom recognizers and the conflict-resolution step."""

from presidio_analyzer import RecognizerResult

from app.recognizers import (
    Mastercard2SeriesRecognizer,
    SpokenEmailRecognizer,
    SpokenNumberRecognizer,
    luhn_valid,
)
from app.redactor import resolve_conflicts

ALL = ["CREDIT_CARD", "PHONE_NUMBER", "US_SSN", "EMAIL_ADDRESS"]


def _types(results):
    return [r.entity_type for r in results]


def test_luhn():
    assert luhn_valid("4111 1111 1111 1111")
    assert luhn_valid("2223003122003222")
    assert not luhn_valid("4111 1111 1111 1112")


def test_mastercard_2_series_is_found_and_checksum_checked():
    rec = Mastercard2SeriesRecognizer()
    assert _types(rec.analyze("card 2223 0031 2200 3222", ALL)) == ["CREDIT_CARD"]
    # Same shape, bad checksum -> rejected
    assert rec.analyze("card 2223 0031 2200 3223", ALL) == []


def test_spoken_numbers_are_labelled_by_length():
    rec = SpokenNumberRecognizer()
    card = "four one one one " * 4
    phone = "nine one seven five five five zero one two three"
    ssn = "five three six two two one eight four seven"
    assert _types(rec.analyze(f"card {card}", ALL)) == ["CREDIT_CARD"]
    assert _types(rec.analyze(f"call {phone} thanks", ALL)) == ["PHONE_NUMBER"]
    assert _types(rec.analyze(f"ssn {ssn}", ALL)) == ["US_SSN"]


def test_spoken_number_allows_fillers_and_commas():
    rec = SpokenNumberRecognizer()
    text = "it's nine one seven, um, four four two, uh, three nine one zero"
    results = rec.analyze(text, ALL)
    assert _types(results) == ["PHONE_NUMBER"]
    assert text[results[0].start:results[0].end].startswith("nine")


def test_short_spoken_numbers_are_ignored():
    assert SpokenNumberRecognizer().analyze("I have two kids and one dog", ALL) == []


def test_spoken_email():
    rec = SpokenEmailRecognizer()
    text = "email priya dot shah at gmail dot com please"
    r = rec.analyze(text, ALL)[0]
    assert text[r.start:r.end] == "priya dot shah at gmail dot com"


def test_conflicts_url_inside_email_is_dropped():
    text = "a@example.com"
    results = [RecognizerResult("EMAIL_ADDRESS", 0, 13, 1.0), RecognizerResult("URL", 2, 13, 0.5)]
    assert _types(resolve_conflicts(text, results)) == ["EMAIL_ADDRESS"]


def test_conflicts_relative_date_is_dropped_but_real_date_kept():
    text = "last year on March 3, 1991"
    results = [RecognizerResult("DATE_TIME", 0, 9, 0.85), RecognizerResult("DATE_TIME", 13, 26, 0.85)]
    kept = resolve_conflicts(text, results)
    assert [text[r.start:r.end] for r in kept] == ["March 3, 1991"]


def test_conflicts_ip_beats_phone_on_same_text():
    text = "142.14.44.201"
    results = [RecognizerResult("IP_ADDRESS", 0, 13, 0.6), RecognizerResult("PHONE_NUMBER", 0, 13, 0.6)]
    assert _types(resolve_conflicts(text, results)) == ["IP_ADDRESS"]

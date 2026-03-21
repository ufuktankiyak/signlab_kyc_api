"""Tests for document parsing functions (no OCR/PaddleOCR dependency)."""

import pytest
from app.services.document_service import (
    parse_turkish_id,
    parse_turkish_id_back,
    parse_passport,
    parse_foreign_id,
    parse_blue_card,
    _is_label,
    _is_name_value,
    _normalize_dates,
    _extract_dates,
    _find_value_after_label,
)


# ─── Shared helpers ──────────────────────────────────────────────────────────

class TestIsLabel:
    def test_known_keywords(self):
        assert _is_label("Surname") is True
        assert _is_label("SOYAD") is True
        assert _is_label("Date of Birth") is True

    def test_short_text(self):
        assert _is_label("A") is True

    def test_non_label(self):
        assert _is_label("YILMAZ") is False


class TestIsNameValue:
    def test_valid_name(self):
        assert _is_name_value("YILMAZ") is True
        assert _is_name_value("MEHMET ALI") is True

    def test_label_is_not_name(self):
        assert _is_name_value("Surname") is False

    def test_digits_not_name(self):
        assert _is_name_value("12345") is False

    def test_single_char(self):
        assert _is_name_value("A") is False


class TestNormalizeDates:
    def test_spaces_around_dots(self):
        assert _normalize_dates("01 . 02 . 2025") == "01.02.2025"

    def test_already_normal(self):
        assert _normalize_dates("01.02.2025") == "01.02.2025"


class TestExtractDates:
    def test_extracts_dates(self):
        text = "Born on 15.03.1985 valid until 20.12.2030"
        dates = _extract_dates(text)
        assert "15.03.1985" in dates
        assert "20.12.2030" in dates

    def test_sorts_by_year(self):
        text = "20.12.2030 and 15.03.1985"
        dates = _extract_dates(text)
        assert dates[0] == "15.03.1985"
        assert dates[1] == "20.12.2030"

    def test_handles_slash_format(self):
        text = "15/03/1985"
        dates = _extract_dates(text)
        assert "15.03.1985" in dates

    def test_no_dates(self):
        assert _extract_dates("no dates here") == []


class TestFindValueAfterLabel:
    def test_finds_value(self):
        texts = ["Surname", "YILMAZ", "Given Name", "MEHMET"]
        value, idx = _find_value_after_label(texts, r"surname", _is_name_value)
        assert value == "YILMAZ"
        assert idx == 1

    def test_no_match(self):
        texts = ["Something", "Else"]
        value, idx = _find_value_after_label(texts, r"surname")
        assert value is None
        assert idx == -1


# ─── Turkish New ID ──────────────────────────────────────────────────────────

class TestParseTurkishId:
    def test_full_extraction(self):
        texts = [
            "T.C.",
            "REPUBLIC OF TURKEY",
            "Soyad / Surname",
            "YILMAZ",
            "Ad(lar) / Name(s)",
            "MEHMET",
            "12345678901",
            "Cinsiyet / Gender",
            "E",
            "01.01.1990",
            "31.12.2030",
            "B21K12345",
        ]
        result = parse_turkish_id(texts)

        assert result["identity_number"] == "12345678901"
        assert result["last_name"] == "YILMAZ"
        assert result["first_name"] == "MEHMET"
        assert result["date_of_birth"] == "01.01.1990"
        assert result["expiry_date"] == "31.12.2030"
        assert result["gender"] == "M"
        assert result["serial_number"] == "B21K12345"

    def test_missing_fields(self):
        texts = ["Some random text"]
        result = parse_turkish_id(texts)
        assert result["identity_number"] is None
        assert result["first_name"] is None
        assert result["last_name"] is None


# ─── Turkish ID Back ─────────────────────────────────────────────────────────

class TestParseTurkishIdBack:
    def test_extracts_parents_and_mrz(self):
        texts = [
            "Anne Adı / Mother",
            "AYSE",
            "Baba Adı / Father",
            "AHMET",
            "Veren Makam / Issued By",
            "ISTANBUL VALILIGI",
            "I<TUR1234567890<<<<<<<<<<<<<<<",
            "8507201M2512319TUR<<<<<<<<<<<6",
            "YILMAZ<<MEHMET<<<<<<<<<<<<<<",
        ]
        result = parse_turkish_id_back(texts)
        assert result["mother_name"] == "AYSE"
        assert result["father_name"] == "AHMET"
        assert result["issued_by"] == "ISTANBUL VALILIGI"
        assert result["mrz_lines"] is not None
        assert len(result["mrz_lines"]) >= 1


# ─── Passport ────────────────────────────────────────────────────────────────

class TestParsePassport:
    def test_full_extraction(self):
        texts = [
            "PASSPORT",
            "Soyad / Surname",
            "OZTURK",
            "Ad(lar) / Name(s)",
            "ALI",
            "U12345678",
            "Uyruk / Nationality",
            "TURK",
            "Cinsiyet / Gender",
            "E",
            "15.06.1988",
            "20.06.2028",
        ]
        result = parse_passport(texts)
        assert result["document_number"] == "U12345678"
        assert result["last_name"] == "OZTURK"
        assert result["first_name"] == "ALI"
        assert result["nationality"] == "TURK"
        assert result["gender"] == "M"


# ─── Foreign ID ──────────────────────────────────────────────────────────────

class TestParseForeignId:
    def test_extracts_foreign_id_number(self):
        texts = [
            "YABANCI KIMLIK",
            "Soyad / Surname",
            "SMITH",
            "Ad(lar) / Name(s)",
            "JOHN",
            "99123456789",
            "Uyruk / Nationality",
            "AMERIKAN",
            "Cinsiyet / Gender",
            "M",
            "01.05.1990",
            "01.05.2025",
            "Ikamet Tipi",
            "KISA DONEM",
        ]
        result = parse_foreign_id(texts)
        assert result["document_number"] == "99123456789"
        assert result["last_name"] == "SMITH"
        assert result["first_name"] == "JOHN"
        assert result["nationality"] == "AMERIKAN"
        assert result["gender"] == "M"
        assert result["permit_type"] == "KISA DONEM"


# ─── Blue Card ───────────────────────────────────────────────────────────────

class TestParseBlueCard:
    def test_extracts_blue_card_info(self):
        texts = [
            "MAVI KART",
            "Soyad / Surname",
            "DEMIR",
            "Ad(lar) / Name(s)",
            "FATMA",
            "12345678901",
            "Uyruk / Nationality",
            "ALMAN",
            "Cinsiyet / Gender",
            "K",
            "10.10.1975",
            "10.10.2035",
            "A22B54321",
        ]
        result = parse_blue_card(texts)
        assert result["document_number"] == "12345678901"
        assert result["last_name"] == "DEMIR"
        assert result["first_name"] == "FATMA"
        assert result["nationality"] == "ALMAN"
        assert result["gender"] == "F"
        assert result["serial_number"] == "A22B54321"

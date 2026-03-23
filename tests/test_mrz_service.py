"""Tests for MRZ (Machine Readable Zone) parser."""

import pytest
from app.core.exceptions import ValidationException
from app.services.mrz_service import parse_mrz, _mrz_date, _decode_name, _sex, _clean


# ─── Helper tests ────────────────────────────────────────────────────────────

class TestClean:
    def test_strips_whitespace(self):
        assert _clean("  hello  ") == "HELLO"

    def test_removes_spaces(self):
        assert _clean("A B C") == "ABC"

    def test_uppercases(self):
        assert _clean("abc") == "ABC"


class TestMrzDate:
    def test_2000s_date(self):
        assert _mrz_date("250315") == "15.03.2025"

    def test_1900s_date(self):
        assert _mrz_date("850720") == "20.07.1985"

    def test_boundary_30(self):
        assert _mrz_date("300101") == "01.01.2030"

    def test_boundary_31(self):
        assert _mrz_date("310101") == "01.01.1931"

    def test_invalid_length(self):
        assert _mrz_date("12345") is None

    def test_non_digit(self):
        assert _mrz_date("ABCDEF") is None

    def test_empty(self):
        assert _mrz_date("") is None


class TestDecodeName:
    def test_surname_and_given(self):
        surname, given = _decode_name("DOE<<JOHN<WILLIAM")
        assert surname == "DOE"
        assert given == "JOHN WILLIAM"

    def test_surname_only(self):
        surname, given = _decode_name("SMITH")
        assert surname == "SMITH"
        assert given == ""

    def test_surname_with_filler(self):
        surname, given = _decode_name("O<BRIEN<<JAMES")
        assert surname == "O BRIEN"
        assert given == "JAMES"


class TestSex:
    def test_male(self):
        assert _sex("M") == "M"

    def test_female(self):
        assert _sex("F") == "F"

    def test_turkish_female(self):
        assert _sex("K") == "F"

    def test_filler(self):
        assert _sex("<") == ""

    def test_unknown(self):
        assert _sex("X") == ""


# ─── TD3 Passport ────────────────────────────────────────────────────────────

class TestParseTD3:
    def test_valid_passport(self):
        line1 = "P<TURDOE<<JOHN<WILLIAM<<<<<<<<<<<<<<<<<<<<<<<"
        line2 = "U123456784TUR8507200M2512315<<<<<<<<<<<<<<06"
        result = parse_mrz(line1, line2)

        assert result["mrz_type"] == "TD3"
        assert result["document_type"] == "P"
        assert result["issuing_country"] == "TUR"
        assert result["last_name"] == "DOE"
        assert result["first_name"] == "JOHN WILLIAM"
        assert result["document_number"] == "U12345678"
        assert result["nationality"] == "TUR"
        assert result["date_of_birth"] == "20.07.1985"
        assert result["sex"] == "M"
        assert result["expiry_date"] == "31.12.2025"

    def test_short_lines_error(self):
        with pytest.raises(ValidationException):
            parse_mrz("SHORT", "LINES")


# ─── TD1 ID Card ─────────────────────────────────────────────────────────────

class TestParseTD1:
    def test_valid_id_card(self):
        # Each TD1 line must be exactly 30 chars
        line1 = "I<TUR1234567890<<<<<<<<<<<<<<<"  # 30 chars
        line2 = "8507201M2512319TUR<<<<<<<<<<<<"  # 30 chars
        line3 = "DOE<<JOHN<<<<<<<<<<<<<<<<<<<<<" # 30 chars

        # Verify lengths
        assert len(line1) == 30
        assert len(line2) == 30
        assert len(line3) == 30

        result = parse_mrz(line1, line2, line3)

        assert result["mrz_type"] == "TD1"
        assert result["document_type"] == "I"
        assert result["issuing_country"] == "TUR"
        assert result["date_of_birth"] == "20.07.1985"
        assert result["sex"] == "M"
        assert result["expiry_date"] == "31.12.2025"
        assert result["nationality"] == "TUR"
        assert result["last_name"] == "DOE"
        assert result["first_name"] == "JOHN"

    def test_short_lines_error(self):
        with pytest.raises(ValidationException):
            parse_mrz("SHORT", "LINES", "TOO")


# ─── Edge cases ──────────────────────────────────────────────────────────────

class TestParseMrzEdgeCases:
    def test_missing_lines(self):
        with pytest.raises(ValidationException) as exc_info:
            parse_mrz(None, None)
        assert "line1 and line2" in exc_info.value.message

    def test_empty_line1(self):
        with pytest.raises(ValidationException):
            parse_mrz("", "something")

    def test_unrecognized_format(self):
        with pytest.raises(ValidationException):
            parse_mrz("ABCDEF", "123456")

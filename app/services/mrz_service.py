"""
MRZ (Machine Readable Zone) parser.

Supports:
  TD3 — Passport         (2 lines × 44 chars)
  TD1 — ID card / Bluecard (3 lines × 30 chars)
  MRV-B — Visa           (2 lines × 36 chars)  [basic]
"""

import re
from typing import Optional

from app.core.exceptions import ValidationException, ErrorCode


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _clean(line: str) -> str:
    return line.strip().upper().replace(" ", "")


def _mrz_date(raw: str) -> Optional[str]:
    """YYMMDD → DD.MM.YYYY (century logic: >30 → 1900s, else 2000s)"""
    if len(raw) != 6 or not raw.isdigit():
        return None
    yy, mm, dd = int(raw[:2]), raw[2:4], raw[4:6]
    year = 1900 + yy if yy > 30 else 2000 + yy
    return f"{dd}.{mm}.{year}"


def _decode_name(raw: str) -> tuple[str, str]:
    """Decode name field: SURNAME<<GIVEN<NAMES → (surname, given_names)"""
    parts = raw.split("<<", 1)
    surname = parts[0].replace("<", " ").strip()
    given = parts[1].replace("<", " ").strip() if len(parts) > 1 else ""
    return surname, given


def _sex(raw: str) -> str:
    mapping = {"M": "M", "F": "F", "K": "F", "<": ""}
    return mapping.get(raw.upper(), "")


# ─── TD3 (Passport) ───────────────────────────────────────────────────────────

def _parse_td3(line1: str, line2: str) -> dict:
    l1, l2 = _clean(line1), _clean(line2)
    if len(l1) < 44 or len(l2) < 44:
        raise ValidationException(
            code=ErrorCode.INVALID_MRZ,
            message="TD3 lines must be 44 chars each",
            details={"line1_len": len(l1), "line2_len": len(l2)},
        )

    doc_type = l1[0:2].replace("<", "").strip()
    issuing_country = l1[2:5].replace("<", "").strip()
    last_name, first_name = _decode_name(l1[5:44])

    document_number = l2[0:9].replace("<", "").strip()
    nationality = l2[10:13].replace("<", "").strip()
    date_of_birth = _mrz_date(l2[13:19])
    sex = _sex(l2[20])
    expiry_date = _mrz_date(l2[21:27])
    personal_number = l2[28:42].replace("<", "").strip()

    return {
        "mrz_type": "TD3",
        "document_type": doc_type,
        "issuing_country": issuing_country,
        "last_name": last_name,
        "first_name": first_name,
        "document_number": document_number,
        "nationality": nationality,
        "date_of_birth": date_of_birth,
        "sex": sex,
        "expiry_date": expiry_date,
        "personal_number": personal_number or None,
    }


# ─── TD1 (ID card / Bluecard) ─────────────────────────────────────────────────

def _parse_td1(line1: str, line2: str, line3: str) -> dict:
    l1, l2, l3 = _clean(line1), _clean(line2), _clean(line3)
    if len(l1) < 30 or len(l2) < 30 or len(l3) < 30:
        raise ValidationException(
            code=ErrorCode.INVALID_MRZ,
            message="TD1 lines must be 30 chars each",
            details={"line1_len": len(l1), "line2_len": len(l2), "line3_len": len(l3)},
        )

    doc_type = l1[0:2].replace("<", "").strip()
    issuing_country = l1[2:5].replace("<", "").strip()
    document_number = l1[5:14].replace("<", "").strip()
    optional1 = l1[15:30].replace("<", "").strip()

    date_of_birth = _mrz_date(l2[0:6])
    sex = _sex(l2[7])
    expiry_date = _mrz_date(l2[8:14])
    nationality = l2[15:18].replace("<", "").strip()
    optional2 = l2[18:29].replace("<", "").strip()

    last_name, first_name = _decode_name(l3)

    return {
        "mrz_type": "TD1",
        "document_type": doc_type,
        "issuing_country": issuing_country,
        "document_number": document_number,
        "date_of_birth": date_of_birth,
        "sex": sex,
        "expiry_date": expiry_date,
        "nationality": nationality,
        "last_name": last_name,
        "first_name": first_name,
        "optional1": optional1 or None,
        "optional2": optional2 or None,
    }


# ─── Public API ───────────────────────────────────────────────────────────────

def parse_mrz(
    line1: Optional[str],
    line2: Optional[str],
    line3: Optional[str] = None,
) -> dict:
    """
    Auto-detect MRZ type from line lengths and parse accordingly.
    Returns a dict with parsed fields or {"error": "..."} on failure.
    """
    if not line1 or not line2:
        raise ValidationException(
            code=ErrorCode.INVALID_MRZ,
            message="At least line1 and line2 are required",
        )

    l1 = _clean(line1)
    l2 = _clean(line2)

    # TD3: 2 lines × 44
    if len(l1) >= 44 and len(l2) >= 44 and not line3:
        return _parse_td3(l1, l2)

    # TD1: 3 lines × 30
    if line3:
        l3 = _clean(line3)
        if len(l1) >= 30 and len(l2) >= 30 and len(l3) >= 30:
            return _parse_td1(l1, l2, l3)

    # Fallback: try TD3 with first 2 lines
    if len(l1) >= 44 and len(l2) >= 44:
        return _parse_td3(l1, l2)

    raise ValidationException(
        code=ErrorCode.INVALID_MRZ,
        message=f"Could not determine MRZ type from line lengths ({len(l1)}, {len(l2)})",
        details={"line1_len": len(l1), "line2_len": len(l2)},
    )

import re
import logging
import cv2
import numpy as np

# PaddleOCR 3.x internal bug fix: 'show_log' is passed to its own base class and gets rejected
import paddleocr._common_args as _paddle_common_args
_original_parse = _paddle_common_args.parse_common_args
_paddle_common_args.parse_common_args = lambda k: _original_parse({x: k[x] for x in k if x != "show_log"})

from paddleocr import PaddleOCR  # noqa: E402

logging.getLogger("ppocr").setLevel(logging.ERROR)

# Singleton — model is loaded only once
_ocr = None


def get_ocr() -> PaddleOCR:
    global _ocr
    if _ocr is None:
        _ocr = PaddleOCR(lang="en")
    return _ocr


def preprocess_image(image_bytes: bytes) -> np.ndarray:
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # Upscale if too small
    h, w = img.shape[:2]
    if w < 800:
        scale = 800 / w
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

    # Noise reduction
    img = cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)

    # Contrast enhancement with CLAHE
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
    img = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    return img


def run_ocr(img: np.ndarray) -> list[str]:
    ocr = get_ocr()
    result = ocr.predict(img)
    texts = []
    for res in result:
        for text, score in zip(res.get("rec_texts", []), res.get("rec_scores", [])):
            if score > 0.5:
                texts.append(text.strip())
    return texts


# ─── Shared helpers ──────────────────────────────────────────────────────────

LABEL_KEYWORDS = {
    "soyad", "surname", "sumame", "given", "name", "birth", "date", "gender",
    "valid", "nationality", "signature", "imza", "cinsiyet", "cinsiy", "kimlik",
    "republic", "turkey", "turkiye", "cumhuriyet", "karti", "card", "identity",
    "tarih", "yeri", "place", "adlar", "adi", "ser no", "seri", "gecer", "until",
    "passport", "pasaport", "expiry", "issued", "authority", "number", "no",
    "foreign", "yabanci", "bluecard", "mavi", "permit", "izin", "ikamet",
}


def _is_label(text: str) -> bool:
    t = text.strip().lower()
    return any(kw in t for kw in LABEL_KEYWORDS) or len(t) <= 1


def _is_name_value(text: str) -> bool:
    t = text.strip()
    return bool(re.match(r"^[A-ZÇĞİÖŞÜa-zçğışöü\-\s]+$", t)) and len(t) > 1 and not _is_label(t)


def _normalize_dates(text: str) -> str:
    return re.sub(r"(\d{2})\s*\.\s*(\d{2})\s*\.\s*(\d{4})", r"\1.\2.\3", text)


def _extract_dates(full_text: str) -> list[str]:
    dates = re.findall(r"\b(\d{2}[./]\d{2}[./]\d{4})\b", full_text)
    dates = [d.replace("/", ".") for d in dates]
    return sorted(set(dates), key=lambda d: int(d.split(".")[2]))


def _find_value_after_label(texts: list[str], label_pattern: str, validator=None) -> tuple[str | None, int]:
    for i, text in enumerate(texts):
        if re.search(label_pattern, text, re.IGNORECASE):
            for j in range(i + 1, min(i + 4, len(texts))):
                candidate = texts[j].strip()
                if validator is None or validator(candidate):
                    return candidate, j
            break
    return None, -1


# ─── Turkish New ID ───────────────────────────────────────────────────────────

def parse_turkish_id(texts: list[str]) -> dict:
    texts = [_normalize_dates(t) for t in texts]
    full_text = " ".join(texts)

    tc_match = re.search(r"\b([1-9]\d{10})\b", full_text)
    identity_number = tc_match.group(1) if tc_match else None

    dates = _extract_dates(full_text)
    date_of_birth = dates[0] if dates else None
    expiry_date = dates[-1] if len(dates) > 1 else None

    last_name, last_name_idx = _find_value_after_label(texts, r"soyad|surname|sumame", _is_name_value)
    first_name = None
    if last_name_idx >= 0:
        for j in range(last_name_idx + 1, min(last_name_idx + 4, len(texts))):
            if _is_name_value(texts[j]):
                first_name = texts[j].strip()
                break

    gender = None
    for i, text in enumerate(texts):
        if re.search(r"cinsiyet|gender|sex", text, re.IGNORECASE):
            for j in range(i + 1, min(i + 4, len(texts))):
                candidate = texts[j].strip().upper()
                if re.match(r"^[EKMF]$", candidate):
                    gender = "M" if candidate in ("E", "M") else "F"
                    break
            if gender:
                break

    place_of_birth, _ = _find_value_after_label(texts, r"doğum yeri|place of birth", _is_name_value)
    serial_match = re.search(r"\b([A-Z]\d{2}[A-Z]\d{5,6})\b", full_text)
    serial_number = serial_match.group(1) if serial_match else None

    return {
        "identity_number": identity_number,
        "first_name": first_name,
        "last_name": last_name,
        "date_of_birth": date_of_birth,
        "place_of_birth": place_of_birth,
        "gender": gender,
        "expiry_date": expiry_date,
        "serial_number": serial_number,
    }


# ─── Passport ─────────────────────────────────────────────────────────────────

def parse_passport(texts: list[str]) -> dict:
    texts = [_normalize_dates(t) for t in texts]
    full_text = " ".join(texts)

    # Passport number: typically 1 letter + 8 digits (Turkish) or 2+7
    passport_match = re.search(r"\b([A-Z]{1,2}\d{7,8})\b", full_text)
    document_number = passport_match.group(1) if passport_match else None

    dates = _extract_dates(full_text)
    date_of_birth = dates[0] if dates else None
    expiry_date = dates[-1] if len(dates) > 1 else None

    last_name, last_name_idx = _find_value_after_label(texts, r"soyad|surname|nom", _is_name_value)
    first_name = None
    if last_name_idx >= 0:
        for j in range(last_name_idx + 1, min(last_name_idx + 4, len(texts))):
            if _is_name_value(texts[j]):
                first_name = texts[j].strip()
                break

    nationality, _ = _find_value_after_label(
        texts,
        r"nationalit|uyruk|vatandas",
        lambda t: 2 <= len(t.strip()) <= 30,
    )

    gender = None
    for i, text in enumerate(texts):
        if re.search(r"cinsiyet|gender|sex", text, re.IGNORECASE):
            for j in range(i + 1, min(i + 4, len(texts))):
                candidate = texts[j].strip().upper()
                if re.match(r"^[EKMF]$", candidate):
                    gender = "M" if candidate in ("E", "M") else "F"
                    break
            if gender:
                break

    place_of_birth, _ = _find_value_after_label(texts, r"doğum yeri|place of birth|birth place", _is_name_value)

    # MRZ lines: 44-char lines of uppercase + '<'
    mrz_lines = [t for t in texts if re.match(r"^[A-Z0-9<]{30,44}$", t.strip())]

    return {
        "document_number": document_number,
        "first_name": first_name,
        "last_name": last_name,
        "date_of_birth": date_of_birth,
        "expiry_date": expiry_date,
        "gender": gender,
        "nationality": nationality,
        "place_of_birth": place_of_birth,
        "mrz_lines": mrz_lines if mrz_lines else None,
    }


# ─── Foreign ID Card ──────────────────────────────────────────────────────────

def parse_foreign_id(texts: list[str]) -> dict:
    texts = [_normalize_dates(t) for t in texts]
    full_text = " ".join(texts)

    # Foreign ID number in Turkey: typically starts with 99 (11 digits)
    id_match = re.search(r"\b(9\d{10})\b", full_text)
    # Fallback to any 11-digit number
    if not id_match:
        id_match = re.search(r"\b(\d{10,11})\b", full_text)
    document_number = id_match.group(1) if id_match else None

    dates = _extract_dates(full_text)
    date_of_birth = dates[0] if dates else None
    expiry_date = dates[-1] if len(dates) > 1 else None

    last_name, last_name_idx = _find_value_after_label(texts, r"soyad|surname|soyadı", _is_name_value)
    first_name = None
    if last_name_idx >= 0:
        for j in range(last_name_idx + 1, min(last_name_idx + 4, len(texts))):
            if _is_name_value(texts[j]):
                first_name = texts[j].strip()
                break

    nationality, _ = _find_value_after_label(
        texts,
        r"nationalit|uyruk|vatandas|country",
        lambda t: 2 <= len(t.strip()) <= 40 and _is_name_value(t),
    )

    gender = None
    for i, text in enumerate(texts):
        if re.search(r"cinsiyet|gender|sex", text, re.IGNORECASE):
            for j in range(i + 1, min(i + 4, len(texts))):
                candidate = texts[j].strip().upper()
                if re.match(r"^[EKMF]$", candidate):
                    gender = "M" if candidate in ("E", "M") else "F"
                    break
            if gender:
                break

    permit_type, _ = _find_value_after_label(
        texts,
        r"ikamet|permit|izin tipi|type",
        lambda t: len(t.strip()) > 2,
    )

    return {
        "document_number": document_number,
        "first_name": first_name,
        "last_name": last_name,
        "date_of_birth": date_of_birth,
        "expiry_date": expiry_date,
        "gender": gender,
        "nationality": nationality,
        "permit_type": permit_type,
    }


# ─── Bluecard ─────────────────────────────────────────────────────────────────

def parse_blue_card(texts: list[str]) -> dict:
    """
    Bluecard: issued to former Turkish citizens and their descendants.
    Layout is similar to the Turkish ID card.
    """
    texts = [_normalize_dates(t) for t in texts]
    full_text = " ".join(texts)

    # Bluecard number format: similar to Turkish ID, 11 digits
    card_match = re.search(r"\b([1-9]\d{10})\b", full_text)
    document_number = card_match.group(1) if card_match else None

    dates = _extract_dates(full_text)
    date_of_birth = dates[0] if dates else None
    expiry_date = dates[-1] if len(dates) > 1 else None

    last_name, last_name_idx = _find_value_after_label(texts, r"soyad|surname", _is_name_value)
    first_name = None
    if last_name_idx >= 0:
        for j in range(last_name_idx + 1, min(last_name_idx + 4, len(texts))):
            if _is_name_value(texts[j]):
                first_name = texts[j].strip()
                break

    nationality, _ = _find_value_after_label(
        texts,
        r"nationalit|uyruk",
        lambda t: 2 <= len(t.strip()) <= 40 and _is_name_value(t),
    )

    gender = None
    for i, text in enumerate(texts):
        if re.search(r"cinsiyet|gender|sex", text, re.IGNORECASE):
            for j in range(i + 1, min(i + 4, len(texts))):
                candidate = texts[j].strip().upper()
                if re.match(r"^[EKMF]$", candidate):
                    gender = "M" if candidate in ("E", "M") else "F"
                    break
            if gender:
                break

    serial_match = re.search(r"\b([A-Z]\d{2}[A-Z]\d{5,6})\b", full_text)
    serial_number = serial_match.group(1) if serial_match else None

    return {
        "document_number": document_number,
        "first_name": first_name,
        "last_name": last_name,
        "date_of_birth": date_of_birth,
        "expiry_date": expiry_date,
        "gender": gender,
        "nationality": nationality,
        "serial_number": serial_number,
    }


# ─── Turkish ID Back ──────────────────────────────────────────────────────────

def parse_turkish_id_back(texts: list[str]) -> dict:
    """
    New Turkish ID card back side:
      - Mother's Name
      - Father's Name
      - Issued By
      - MRZ (3 lines, TD1 format)
    """
    full_text = " ".join(texts)

    mother_name, _ = _find_value_after_label(
        texts, r"anne\s*ad[iı]|mother", _is_name_value
    )
    father_name, _ = _find_value_after_label(
        texts, r"baba\s*ad[iı]|father", _is_name_value
    )
    issued_by, _ = _find_value_after_label(
        texts,
        r"veren\s*makam|issued\s*by",
        lambda t: len(t.strip()) > 3,
    )

    # MRZ: TD1 format — 30 characters, uppercase letters + digits + '<'
    mrz_lines = [t.strip() for t in texts if re.match(r"^[A-Z0-9<]{29,31}$", t.strip())]

    return {
        "mother_name": mother_name,
        "father_name": father_name,
        "issued_by": issued_by,
        "mrz_lines": mrz_lines if mrz_lines else None,
    }


# ─── Dispatcher ───────────────────────────────────────────────────────────────

_FRONT_PARSERS = {
    "new_id": parse_turkish_id,
    "passport": parse_passport,
    "foreign_id": parse_foreign_id,
    "blue_card": parse_blue_card,
}

_BACK_PARSERS = {
    "new_id": parse_turkish_id_back,
    # Passport and others are single-sided — use the front parser
}


def extract_document(image_bytes: bytes, document_type: str, side: str = "front") -> tuple[dict, list]:
    """Full pipeline: preprocess → OCR → parse.  Returns (extracted_data, raw_texts)."""
    img = preprocess_image(image_bytes)
    texts = run_ocr(img)

    if side == "back":
        parser = _BACK_PARSERS.get(document_type)
        if parser is None:
            # For passport/foreign_id/blue_card the back side uses the front parser
            parser = _FRONT_PARSERS.get(document_type, parse_turkish_id)
    else:
        parser = _FRONT_PARSERS.get(document_type, parse_turkish_id)

    return parser(texts), texts

import re
import logging
import cv2
import numpy as np
from app.schemas.document import DocumentType, TurkishIDData

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


LABEL_KEYWORDS = {
    "soyad", "surname", "sumame", "given", "name", "birth", "date", "gender",
    "valid", "nationality", "signature", "imza", "cinsiyet", "cinsiy", "kimlik",
    "republic", "turkey", "turkiye", "cumhuriyet", "karti", "card", "identity",
    "tarih", "yeri", "place", "adlar", "adi", "ser no", "seri", "gecer", "until",
}

def _is_label(text: str) -> bool:
    t = text.strip().lower()
    return any(kw in t for kw in LABEL_KEYWORDS) or len(t) <= 1

def _is_name_value(text: str) -> bool:
    t = text.strip()
    return bool(re.match(r"^[A-ZÇĞİÖŞÜa-zçğışöü\-\s]+$", t)) and len(t) > 1 and not _is_label(t)

def _normalize_dates(text: str) -> str:
    # Fix malformed dates like "15. 08.2030" or "15 .08.2030"
    return re.sub(r"(\d{2})\s*\.\s*(\d{2})\s*\.\s*(\d{4})", r"\1.\2.\3", text)


def parse_turkish_id(texts: list[str]) -> TurkishIDData:
    # Normalize whitespace in dates
    texts = [_normalize_dates(t) for t in texts]
    full_text = " ".join(texts)

    # Turkish ID number: 11 digits, first digit cannot be 0
    tc_match = re.search(r"\b([1-9]\d{10})\b", full_text)
    identity_number = tc_match.group(1) if tc_match else None

    # Dates
    dates = re.findall(r"\b(\d{2}[./]\d{2}[./]\d{4})\b", full_text)
    dates = [d.replace("/", ".") for d in dates]
    dates_sorted = sorted(set(dates), key=lambda d: int(d.split(".")[2]))
    date_of_birth = dates_sorted[0] if dates_sorted else None
    expiry_date = dates_sorted[-1] if len(dates_sorted) > 1 else None

    # Surname: first value after the "Soyadi" / "Surname" label
    last_name = None
    last_name_idx = -1
    for i, text in enumerate(texts):
        if re.search(r"soyad|surname|sumame", text, re.IGNORECASE):
            for j in range(i + 1, min(i + 4, len(texts))):
                if _is_name_value(texts[j]):
                    last_name = texts[j].strip()
                    last_name_idx = j
                    break
            break

    # First name: first value after the surname (positional fallback if no label)
    first_name = None
    if last_name_idx >= 0:
        for j in range(last_name_idx + 1, min(last_name_idx + 4, len(texts))):
            if _is_name_value(texts[j]):
                first_name = texts[j].strip()
                break

    # Gender: E/K/M/F after the "Cinsiyeti"/"Gender" label
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

    # Place of birth: after the label
    place_of_birth = None
    for i, text in enumerate(texts):
        if re.search(r"doğum yeri|place of birth", text, re.IGNORECASE):
            for j in range(i + 1, min(i + 3, len(texts))):
                if _is_name_value(texts[j]):
                    place_of_birth = texts[j].strip()
                    break
            break

    # Serial number
    serial_match = re.search(r"\b([A-Z]\d{2}[A-Z]\d{5,6})\b", full_text)
    serial_number = serial_match.group(1) if serial_match else None

    return TurkishIDData(
        identity_number=identity_number,
        first_name=first_name,
        last_name=last_name,
        date_of_birth=date_of_birth,
        place_of_birth=place_of_birth,
        gender=gender,
        expiry_date=expiry_date,
        serial_number=serial_number,
    )


def extract_document(image_bytes: bytes, content_type: str, document_type: DocumentType) -> TurkishIDData:
    img = preprocess_image(image_bytes)
    texts = run_ocr(img)
    return parse_turkish_id(texts)

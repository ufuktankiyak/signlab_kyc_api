# Signlab KYC API

A production-ready, on-premise KYC (Know Your Customer) API built with FastAPI. Designed to be sold and deployed on-premise by companies that need identity verification capabilities without sending data to third-party cloud services.

## Features

- **Transaction-based flow** — every KYC session is tracked via a unique `tx_id`
- **OCR** — extracts structured data from identity documents using PaddleOCR
- **NFC / MRZ** — parses Machine Readable Zone data from NFC chips or document scans
- **Liveness detection** — analyzes video to detect face presence and liveness score
- **File storage** — all uploaded files are saved to a persistent local storage volume
- **Full audit trail** — every step and all extracted data is persisted to PostgreSQL

## Supported Document Types

| Type | Value |
|------|-------|
| New Turkish ID Card | `new_id` |
| Passport | `passport` |
| Foreign ID Card | `foreign_id` |
| Blue Card (Mavi Kart) | `blue_card` |

## KYC Flow

```
POST /kyc/start
      ↓
POST /kyc/{tx_id}/ocr       (front)
      ↓
POST /kyc/{tx_id}/ocr       (back)
      ↓
POST /kyc/{tx_id}/nfc
      ↓
POST /kyc/{tx_id}/liveness
      ↓
GET  /kyc/{tx_id}/status
```

Each step after `start` requires a valid `tx_id`. Attempting to call any endpoint with an unknown `tx_id` returns `404`.

## API Endpoints

### Start
```
POST /api/v1/kyc/start
```
Starts a new KYC transaction. Returns a `tx_id` to be used in all subsequent steps.

**Request body:**
```json
{
  "document_type": "new_id",
  "client_reference": "optional-your-own-id"
}
```

**Response:**
```json
{
  "tx_id": "a1b2c3d4e5f6...",
  "status": "started",
  "document_type": "new_id",
  "client_reference": null,
  "created_at": "2024-01-15T10:30:00"
}
```

---

### OCR
```
POST /api/v1/kyc/{tx_id}/ocr
```
Upload a document image. Extracts structured fields using OCR.

**Form data:**
- `file` — image file (JPEG, PNG, WebP, GIF)
- `side` — `front` (default) or `back`

**Response (new_id front):**
```json
{
  "tx_id": "a1b2c3d4e5f6...",
  "side": "front",
  "document_type": "new_id",
  "extracted_data": {
    "identity_number": "12345678901",
    "first_name": "JOHN",
    "last_name": "DOE",
    "date_of_birth": "01.01.1990",
    "place_of_birth": "ISTANBUL",
    "gender": "M",
    "expiry_date": "01.01.2030",
    "serial_number": "A12B34567"
  },
  "file_path": "a1b2c3d4.../ocr_front/abc123.jpg"
}
```

**Response (new_id back):**
```json
{
  "tx_id": "a1b2c3d4e5f6...",
  "side": "back",
  "document_type": "new_id",
  "extracted_data": {
    "mother_name": "JANE",
    "father_name": "JAMES",
    "issued_by": "T.C. IÇIŞLERI BAKANLIGI",
    "mrz_lines": [
      "I<TURXXXXXXXXXXXXXXXXXXXXXXXXXX",
      "XXXXXXXXXXXXXXXXXTUR<<<<<<<<<<<X",
      "DOE<<JOHN<<<<<<<<<<<<<<<<<<<<<<"
    ]
  },
  "file_path": "a1b2c3d4.../ocr_back/def456.jpg"
}
```

---

### NFC / MRZ
```
POST /api/v1/kyc/{tx_id}/nfc
```
Submit MRZ lines read from an NFC chip or document scan. Auto-detects TD3 (passport, 2×44) and TD1 (ID card, 3×30) formats.

**Request body (TD1 — ID card):**
```json
{
  "mrz_line1": "I<TURXXXXXXXXXXXXXXXXXXXXXXXXXX",
  "mrz_line2": "XXXXXXXXXXXXXXXXXTUR<<<<<<<<<<<X",
  "mrz_line3": "DOE<<JOHN<<<<<<<<<<<<<<<<<<<<<<"
}
```

**Request body (TD3 — passport):**
```json
{
  "mrz_line1": "P<TURDOE<<JOHN<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<",
  "mrz_line2": "XXXXXXXXX<XTUR9001011M3001010<<<<<<<<<<<<<<X"
}
```

**Response:**
```json
{
  "tx_id": "a1b2c3d4e5f6...",
  "parsed_data": {
    "mrz_type": "TD1",
    "document_type": "I",
    "issuing_country": "TUR",
    "document_number": "A12345678",
    "date_of_birth": "01.01.1990",
    "sex": "M",
    "expiry_date": "01.01.2030",
    "nationality": "TUR",
    "last_name": "DOE",
    "first_name": "JOHN"
  }
}
```

---

### Liveness
```
POST /api/v1/kyc/{tx_id}/liveness
```
Upload a short video. Frames are sampled at regular intervals and face detection is performed on each.

**Form data:**
- `file` — video file (MP4, WebM, MOV, AVI, MPEG)

**Response:**
```json
{
  "tx_id": "a1b2c3d4e5f6...",
  "face_detected": true,
  "liveness_score": 0.72,
  "result": "passed",
  "file_path": "a1b2c3d4.../liveness/video.mp4",
  "detail": {
    "frames_analyzed": 10,
    "frames_with_face": 9,
    "face_presence_ratio": 0.9,
    "avg_face_ratio": 0.14,
    "avg_blur_score": 182.5
  }
}
```

Liveness results:

| Result | Score |
|--------|-------|
| `passed` | ≥ 0.55 |
| `review` | 0.30 – 0.54 |
| `failed` | < 0.30 |

---

### Status
```
GET /api/v1/kyc/{tx_id}/status
```
Returns the current status and completed steps of a transaction.

**Response:**
```json
{
  "tx_id": "a1b2c3d4e5f6...",
  "status": "liveness_done",
  "document_type": "new_id",
  "client_reference": null,
  "steps_completed": ["start", "ocr", "nfc", "liveness"],
  "created_at": "2024-01-15T10:30:00",
  "updated_at": "2024-01-15T10:35:00"
}
```

## Tech Stack

- **Framework:** FastAPI + Uvicorn
- **Database:** PostgreSQL 15 + SQLAlchemy
- **OCR:** PaddleOCR (runs fully offline)
- **Image processing:** OpenCV + NumPy
- **Storage:** Local filesystem (Docker volume)

## Getting Started

### Prerequisites

- Docker
- Docker Compose

### 1. Clone the repository

```bash
git clone https://github.com/your-org/signlab-kyc-api.git
cd signlab-kyc-api
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://signlab:signlab123@db:5432/signlab_kyc
STORAGE_PATH=/app/storage
```

### 3. Start with Docker Compose

```bash
docker compose up --build
```

The API will be available at `http://localhost:8000`.

Interactive docs: `http://localhost:8000/docs`

## Database

Tables created automatically on startup:

| Table | Description |
|-------|-------------|
| `kyc_transactions` | One record per KYC session |
| `kyc_documents` | OCR results per document side |
| `kyc_nfc` | Raw MRZ lines and parsed data |
| `kyc_liveness` | Video analysis results |

## Storage

Uploaded files are saved under `STORAGE_PATH/{tx_id}/{step}/`:

```
storage/
└── a1b2c3d4e5f6.../
    ├── ocr_front/
    │   └── abc123.jpg
    ├── ocr_back/
    │   └── def456.jpg
    └── liveness/
        └── ghi789.mp4
```

## Local Development (without Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Set a local storage path in .env
STORAGE_PATH=/path/to/signlab_kyc_api/storage

uvicorn app.main:app --reload
```

> Note: Requires a running PostgreSQL instance and an updated `DATABASE_URL` in `.env`.
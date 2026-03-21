# Signlab KYC API

On-premise KYC (Know Your Customer) API built with FastAPI. Handles identity document OCR, MRZ/NFC parsing, and video-based liveness detection.

## Tech Stack

- **Framework:** FastAPI + Uvicorn
- **Database:** PostgreSQL 15 (Docker, port 5433)
- **ORM:** SQLAlchemy + Alembic (migrations)
- **OCR:** PaddleOCR (offline, no external API)
- **Liveness:** OpenCV Haar cascades
- **Auth:** JWT (HS256) + bcrypt password hashing
- **Python:** 3.12

## Project Structure

```
app/
├── api/v1/          # Route handlers (auth, users, documents, kyc)
├── core/            # Config (pydantic-settings) and security (JWT, bcrypt)
├── db/              # SQLAlchemy base and session
├── models/          # ORM models (User, KycTransaction, KycDocument, KycNfc, KycLiveness)
├── schemas/         # Pydantic request/response schemas
└── services/        # Business logic (document, kyc, liveness, mrz, storage, user)
tests/               # pytest unit and repository tests
alembic/             # Database migrations
```

## Common Commands

```bash
# Start PostgreSQL (Docker)
docker compose up -d db

# Start API (Docker)
docker compose up -d api

# Start API (local)
source .venv/bin/activate
DATABASE_URL="postgresql://signlab:signlab123@127.0.0.1:5433/signlab_kyc" \
SECRET_KEY="supersecretkey123456789abcdef0123456789abcdef" \
python -m uvicorn app.main:app --port 8000

# Run migrations
DATABASE_URL="postgresql://signlab:signlab123@127.0.0.1:5433/signlab_kyc" \
alembic upgrade head

# Create new migration after model changes
DATABASE_URL="postgresql://signlab:signlab123@127.0.0.1:5433/signlab_kyc" \
alembic revision --autogenerate -m "description"

# Run tests
DATABASE_URL="postgresql://signlab:signlab123@127.0.0.1:5433/signlab_kyc" \
SECRET_KEY="testsecret" \
python -m pytest tests/ -v
```

## Key Notes

- Docker API container uses `db:5432` for DB (docker-compose internal network). Local uses `127.0.0.1:5433`.
- `.env` file is for local development. Docker overrides `DATABASE_URL` in `docker-compose.yml`.
- Swagger UI: `http://localhost:8000/docs` — uses HTTPBearer auth (paste token directly).
- Admin seed user: `admin@signlab.com` / `changeme123` (created on startup).
- Token expiry: 60 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- PaddleOCR models are downloaded at Docker build time (offline at runtime).
- Database schema changes must go through Alembic migrations — never use `Base.metadata.create_all()` directly.

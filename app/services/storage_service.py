import uuid
from pathlib import Path
from app.core.config import get_settings

settings = get_settings()


def save_file(tx_id: str, category: str, original_filename: str, data: bytes) -> str:
    """Save bytes to storage/{tx_id}/{category}/ and return the relative path."""
    dir_path = Path(settings.STORAGE_PATH) / tx_id / category
    dir_path.mkdir(parents=True, exist_ok=True)

    suffix = Path(original_filename).suffix or ".bin"
    filename = f"{uuid.uuid4().hex}{suffix}"
    file_path = dir_path / filename
    file_path.write_bytes(data)

    # Return path relative to STORAGE_PATH so it's portable
    return str(file_path.relative_to(settings.STORAGE_PATH))

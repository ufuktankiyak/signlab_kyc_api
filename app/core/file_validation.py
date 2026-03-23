"""
Validate uploaded file content by checking magic bytes,
not just the client-provided Content-Type header.
"""

# Magic byte signatures for supported formats
_IMAGE_SIGNATURES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"RIFF": "image/webp",       # WebP is RIFF....WEBP
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
}

_VIDEO_SIGNATURES = {
    b"\x00\x00\x00": "video/mp4",       # ftyp box (MP4/MOV) — first 3 bytes are size
    b"\x1a\x45\xdf\xa3": "video/webm",  # EBML header (WebM/MKV)
}


def validate_image_bytes(data: bytes) -> str | None:
    """Return detected MIME type if data looks like a valid image, else None."""
    if len(data) < 8:
        return None
    for sig, mime in _IMAGE_SIGNATURES.items():
        if data[:len(sig)] == sig:
            # Extra check for WebP: bytes 8-12 must be "WEBP"
            if mime == "image/webp" and data[8:12] != b"WEBP":
                continue
            return mime
    return None


def validate_video_bytes(data: bytes) -> str | None:
    """Return detected MIME type if data looks like a valid video, else None."""
    if len(data) < 12:
        return None

    # MP4/MOV: check for 'ftyp' at byte 4
    if data[4:8] == b"ftyp":
        return "video/mp4"

    for sig, mime in _VIDEO_SIGNATURES.items():
        if data[:len(sig)] == sig:
            return mime

    return None

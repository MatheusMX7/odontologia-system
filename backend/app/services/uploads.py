import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from ..core.config import get_settings

MAX_BYTES = 2 * 1024 * 1024
_SIGNATURES = {
    ".png": lambda b: b.startswith(b"\x89PNG\r\n\x1a\n"),
    ".jpg": lambda b: b.startswith(b"\xff\xd8\xff"),
    ".jpeg": lambda b: b.startswith(b"\xff\xd8\xff"),
    ".webp": lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP",
}


async def save_image(file: UploadFile, subdir: str) -> str:
    """Valida extensão, tamanho e assinatura real do arquivo; grava com nome aleatório."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _SIGNATURES:
        raise HTTPException(422, "Formato de imagem não suportado. Use PNG, JPG ou WEBP.")
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(422, "A imagem deve ter no máximo 2 MB.")
    if not _SIGNATURES[ext](data):
        raise HTTPException(422, "O arquivo enviado não é uma imagem válida.")
    folder = get_settings().upload_path / subdir
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    (folder / name).write_bytes(data)
    return f"/uploads/{subdir}/{name}"

from __future__ import annotations

import re
import shutil
from pathlib import Path

from fastapi import UploadFile
from pypdf import PdfReader

from .config import Settings

UPLOAD_DIR = "合同文件/手工新增"
MAX_UPLOAD_BYTES = 100 * 1024 * 1024


def safe_pdf_filename(filename: str) -> str:
    name = Path(filename or "uploaded.pdf").name
    stem = Path(name).stem
    suffix = Path(name).suffix.lower()
    if suffix != ".pdf":
        raise ValueError("只允许上传 PDF 文件")
    cleaned = re.sub(r"[^0-9A-Za-z一-鿿._ -]+", "_", stem).strip(" ._")
    return f"{cleaned or 'uploaded'}.pdf"


def resolve_raw_path(settings: Settings, relative_path: str) -> Path:
    raw_dir = settings.raw_dir.resolve()
    path = (raw_dir / relative_path).resolve()
    path.relative_to(raw_dir)
    return path


def pdf_metadata(path: Path) -> tuple[int | None, str]:
    try:
        reader = PdfReader(str(path))
        page_count = len(reader.pages)
        text = ""
        for page in reader.pages[:3]:
            text += page.extract_text() or ""
        return page_count, "text_ok" if len(text.strip()) >= 50 else "low_or_scanned"
    except Exception:
        return None, "error"


async def save_uploaded_pdf(settings: Settings, upload: UploadFile | None) -> dict[str, object] | None:
    if upload is None or not upload.filename:
        return None
    filename = safe_pdf_filename(upload.filename)
    target_dir = settings.raw_dir / UPLOAD_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename
    if target.exists():
        stem = target.stem
        counter = 1
        while target.exists():
            target = target_dir / f"{stem}-{counter}.pdf"
            counter += 1
    size = 0
    with target.open("wb") as output:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                output.close()
                target.unlink(missing_ok=True)
                raise ValueError("PDF 文件不能超过 100 MB")
            output.write(chunk)
    page_count, text_status = pdf_metadata(target)
    return {
        "original_filename": filename,
        "relative_path": target.relative_to(settings.raw_dir).as_posix(),
        "file_ext": ".pdf",
        "size_bytes": target.stat().st_size,
        "page_count": page_count,
        "text_status": text_status,
    }


def copy_existing_pdf(settings: Settings, existing_relative_path: str) -> dict[str, object] | None:
    if not existing_relative_path:
        return None
    source = resolve_raw_path(settings, existing_relative_path)
    if source.suffix.lower() != ".pdf" or not source.exists():
        raise ValueError("登记的已有文件必须是 raw 目录下存在的 PDF")
    page_count, text_status = pdf_metadata(source)
    return {
        "original_filename": source.name,
        "relative_path": source.relative_to(settings.raw_dir).as_posix(),
        "file_ext": ".pdf",
        "size_bytes": source.stat().st_size,
        "page_count": page_count,
        "text_status": text_status,
    }

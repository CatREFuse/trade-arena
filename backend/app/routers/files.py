from __future__ import annotations

from io import BytesIO
from mimetypes import guess_type
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import settings
from app.routers.agents import _package_skill_archive

router = APIRouter(prefix="/api/file", tags=["files"])


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent


def _hosted_files_dir() -> Path:
    return (_project_root() / settings.hosted_files_dir).resolve()


def _resolve_hosted_file(file_name: str) -> Path:
    if Path(file_name).name != file_name:
        raise HTTPException(
            400,
            detail={"error": "INVALID_FILE_NAME", "message": "Invalid file name"},
        )
    return (_hosted_files_dir() / file_name).resolve()


def _build_default_skill_archive(target_file: Path) -> None:
    skill_dir = _project_root() / "cocoloop-trade-arena"
    if not skill_dir.exists():
        raise HTTPException(
            404,
            detail={
                "error": "SKILL_NOT_FOUND",
                "message": "Hosted skill package not found",
            },
        )

    archive: BytesIO = _package_skill_archive(skill_dir, "cocoloop-trade-arena")
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_bytes(archive.getvalue())


@router.get("/{file_name}")
async def get_hosted_file(file_name: str):
    hosted_dir = _hosted_files_dir()
    target_file = _resolve_hosted_file(file_name)
    if not str(target_file).startswith(str(hosted_dir)):
        raise HTTPException(
            403, detail={"error": "FORBIDDEN", "message": "Access denied"}
        )

    if not target_file.exists() and file_name == settings.hosted_skill_filename:
        _build_default_skill_archive(target_file)

    if not target_file.exists() or not target_file.is_file():
        raise HTTPException(
            404,
            detail={
                "error": "FILE_NOT_FOUND",
                "message": f"File '{file_name}' not found",
            },
        )

    media_type = guess_type(target_file.name)[0] or "application/octet-stream"
    return FileResponse(
        target_file,
        media_type=media_type,
        filename=target_file.name,
        headers={"Cache-Control": "no-store"},
    )

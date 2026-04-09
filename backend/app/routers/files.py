from __future__ import annotations

from io import BytesIO
from mimetypes import guess_type
from pathlib import Path
import re
import zipfile

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import settings
from app.routers.agents import _package_skill_archive, _read_skill_version

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


def _read_skill_version_from_archive(archive_path: Path) -> str:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            with archive.open("SKILL.md") as skill_md:
                content = skill_md.read().decode("utf-8")
    except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError):
        return ""

    match = re.search(
        r"""(?m)^version:\s*(?:"(?P<dq>[^"]+)"|'(?P<sq>[^']+)'|(?P<raw>[^\s#]+))\s*$""",
        content,
    )
    if not match:
        return ""
    return (match.group("dq") or match.group("sq") or match.group("raw")).strip()


def _ensure_latest_hosted_skill_archive(target_file: Path) -> None:
    skill_dir = _project_root() / "cocoloop-trade-arena"
    skill_md_path = skill_dir / "SKILL.md"
    if not skill_md_path.exists():
        raise HTTPException(
            404,
            detail={
                "error": "SKILL_METADATA_NOT_FOUND",
                "message": "Hosted skill SKILL.md not found",
            },
        )

    try:
        latest_version = _read_skill_version(skill_md_path)
    except ValueError as exc:
        raise HTTPException(
            500,
            detail={
                "error": "SKILL_METADATA_INVALID",
                "message": str(exc),
            },
        )

    if target_file.exists():
        current_version = _read_skill_version_from_archive(target_file)
        if current_version == latest_version:
            return

    _build_default_skill_archive(target_file)


@router.get("/{file_name}")
async def get_hosted_file(file_name: str):
    hosted_dir = _hosted_files_dir()
    target_file = _resolve_hosted_file(file_name)
    if not str(target_file).startswith(str(hosted_dir)):
        raise HTTPException(
            403, detail={"error": "FORBIDDEN", "message": "Access denied"}
        )

    if file_name == settings.hosted_skill_filename:
        _ensure_latest_hosted_skill_archive(target_file)

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

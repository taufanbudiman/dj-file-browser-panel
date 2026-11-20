"""Sandboxed, read-only filesystem access for the file browser panel.

Every path handled here is resolved with ``Path.resolve()`` and verified to
stay inside a configured root. Symlinks that resolve outside a root are never
followed. Nothing in this module mutates the filesystem.
"""

from __future__ import annotations

import mimetypes
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.utils.text import slugify

from .conf import panel_config


@dataclass(frozen=True)
class Root:
    """A configured browsable root directory."""

    slug: str
    name: str
    description: str
    path: Path  # resolved absolute path


@dataclass(frozen=True)
class DirEntry:
    """A single directory listing row."""

    name: str
    rel_path: str  # path relative to the root, posix-style, for URL building
    is_dir: bool
    is_safe: bool  # False for symlinks that escape the root
    size: int | None
    size_display: str
    modified: datetime | None
    url: str = ""


@dataclass
class Listing:
    """One page of a directory listing."""

    entries: list[DirEntry]
    total: int
    page: int
    per_page: int
    total_pages: int
    error: str | None = None


@dataclass(frozen=True)
class FileInfo:
    """Metadata (and optional preview) for a single file."""

    name: str
    rel_path: str
    size: int
    size_display: str
    modified: datetime
    mime_type: str
    preview: str | None
    preview_truncated: bool


def human_size(size: int | None) -> str:
    if size is None:
        return "—"
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            break
        value /= 1024
    if unit == "B":
        return f"{int(value)} B"
    return f"{value:.1f} {unit}"


def _iter_root_specs():
    """Yield ``(name, description, raw_path)`` for each configured root."""
    configured = panel_config.get_settings("ROOTS")
    if not configured:
        configured = [
            getattr(settings, attr, None) for attr in ("MEDIA_ROOT", "STATIC_ROOT")
        ]
    for item in configured:
        if not item:
            continue
        if isinstance(item, dict):
            yield item.get("name"), item.get("description", ""), item.get("path")
        else:
            yield None, "", item


def get_roots() -> list[Root]:
    """Return configured roots that exist and are directories.

    Roots that are missing, not directories, or fail to resolve are skipped
    (BR-04). Slugs are derived from the display name and deduplicated.
    """
    roots: list[Root] = []
    used_slugs: set[str] = set()
    for name, description, raw_path in _iter_root_specs():
        if not raw_path:
            continue
        try:
            resolved = Path(raw_path).expanduser().resolve()
        except (OSError, RuntimeError):
            continue
        if not resolved.is_dir():
            continue
        display_name = str(name) if name else (resolved.name or str(resolved))
        slug = slugify(display_name) or "root"
        candidate, n = slug, 2
        while candidate in used_slugs:
            candidate = f"{slug}-{n}"
            n += 1
        used_slugs.add(candidate)
        roots.append(
            Root(
                slug=candidate,
                name=display_name,
                description=str(description or ""),
                path=resolved,
            )
        )
    return roots


def get_root(slug: str) -> Root | None:
    for root in get_roots():
        if root.slug == slug:
            return root
    return None


def count_entries(root_path: Path) -> int | None:
    """Cheap entry count for the roots index (names only, no stat)."""
    try:
        with os.scandir(root_path) as scanner:
            return sum(1 for _ in scanner)
    except OSError:
        return None


def resolve_in_root(root: Root, rel_path: str = "") -> Path | None:
    """Resolve ``rel_path`` inside ``root``; ``None`` when it escapes.

    ``..`` segments, absolute paths outside the root, and symlinks that
    resolve outside the root are all rejected here (BR-02, BR-03).
    """
    try:
        candidate = (
            (root.path / rel_path).resolve() if rel_path else root.path.resolve()
        )
    except (OSError, RuntimeError, ValueError):
        return None
    if candidate != root.path and not candidate.is_relative_to(root.path):
        return None
    return candidate


def _is_within_root(path: Path, root: Root) -> bool:
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError, ValueError):
        return False
    return resolved == root.path or resolved.is_relative_to(root.path)


def _describe_entry(root: Root, path: Path, is_dir: bool) -> DirEntry:
    try:
        rel_path = path.relative_to(root.path).as_posix()
    except ValueError:
        rel_path = path.name

    safe = _is_within_root(path, root)
    size = None
    modified = None
    if safe and not is_dir:
        try:
            st = path.stat()
        except OSError:
            st = None
        if st is not None:
            size = st.st_size
            modified = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)

    return DirEntry(
        name=path.name,
        rel_path=rel_path,
        is_dir=is_dir,
        is_safe=safe,
        size=size,
        size_display=human_size(size),
        modified=modified,
    )


def list_directory(
    root: Root,
    rel_path: str = "",
    *,
    show_hidden: bool = False,
    page: int = 1,
    per_page: int = 100,
) -> Listing:
    """Return one page of a directory listing, directories first.

    Only lightweight metadata (names plus a paginated slice of stats) is held
    in memory; file contents are never read here.
    """
    target = resolve_in_root(root, rel_path)
    if target is None:
        return Listing(
            [], 0, 1, per_page, 0, "That path is outside the configured root."
        )
    if not target.exists():
        return Listing([], 0, 1, per_page, 0, "Path does not exist.")
    if not target.is_dir():
        return Listing([], 0, 1, per_page, 0, "Path is not a directory.")

    rows: list[tuple[str, bool]] = []
    try:
        with os.scandir(target) as scanner:
            for entry in scanner:
                if not show_hidden and entry.name.startswith("."):
                    continue
                try:
                    is_dir = entry.is_dir()
                except OSError:
                    is_dir = False
                rows.append((entry.name, is_dir))
    except PermissionError:
        return Listing([], 0, 1, per_page, 0, "Permission denied.")
    except OSError as exc:
        return Listing([], 0, 1, per_page, 0, f"Could not read directory: {exc}")

    rows.sort(key=lambda row: (not row[1], row[0].casefold()))
    total = len(rows)
    per_page = max(1, int(per_page))
    total_pages = -(-total // per_page) if total else 0
    page = max(1, min(int(page), total_pages or 1))
    start = (page - 1) * per_page

    entries = [
        _describe_entry(root, target / name, is_dir)
        for name, is_dir in rows[start : start + per_page]
    ]
    return Listing(entries, total, page, per_page, total_pages)


def _preview_allowed(mime_type: str) -> bool:
    cfg = panel_config.get_settings()
    if not cfg.get("PREVIEW_ENABLED"):
        return False
    try:
        max_bytes = int(cfg.get("PREVIEW_MAX_BYTES"))
    except (TypeError, ValueError):
        max_bytes = 0
    if max_bytes <= 0:
        return False
    allowed = cfg.get("PREVIEW_TYPES") or []
    return mime_type in allowed or mime_type.startswith("text/")


def _read_preview(path: Path) -> tuple[str | None, bool]:
    try:
        max_bytes = int(panel_config.get_settings("PREVIEW_MAX_BYTES"))
    except (TypeError, ValueError):
        return None, False
    if max_bytes <= 0:
        return None, False
    try:
        with path.open("rb") as handle:
            data = handle.read(max_bytes + 1)
    except OSError:
        return None, False
    truncated = len(data) > max_bytes
    return data[:max_bytes].decode("utf-8", errors="replace"), truncated


def get_file_info(root: Root, rel_path: str) -> tuple[FileInfo | None, str | None]:
    """Return ``(FileInfo, None)`` or ``(None, error_message)``."""
    target = resolve_in_root(root, rel_path)
    if target is None:
        return None, "That path is outside the configured root."
    if not target.exists():
        return None, "File does not exist."
    if target.is_dir():
        return None, "Path is a directory."
    try:
        st = target.stat()
    except OSError as exc:
        return None, f"Could not stat file: {exc}"

    try:
        rel = target.relative_to(root.path).as_posix()
    except ValueError:
        rel = target.name

    mime_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    preview = None
    truncated = False
    if _preview_allowed(mime_type):
        preview, truncated = _read_preview(target)

    info = FileInfo(
        name=target.name,
        rel_path=rel,
        size=st.st_size,
        size_display=human_size(st.st_size),
        modified=datetime.fromtimestamp(st.st_mtime, tz=timezone.utc),
        mime_type=mime_type,
        preview=preview,
        preview_truncated=truncated,
    )
    return info, None

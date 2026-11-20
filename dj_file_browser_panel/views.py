"""Views for the DJ File Browser Panel.

All views are read-only. Filesystem access goes through
:mod:`dj_file_browser_panel.browser`, which sandboxes every path inside a
configured root.
"""

from __future__ import annotations

import mimetypes
from dataclasses import replace
from urllib.parse import quote, urlencode

from django.http import FileResponse, Http404
from django.shortcuts import render
from django.urls import reverse

from . import browser
from .conf import panel_config


def _get_page_range(current_page: int, total_pages: int) -> list:
    """Smart page range for pagination display."""
    if total_pages <= 10:
        return list(range(1, total_pages + 1))

    start = max(1, current_page - 5)
    end = min(total_pages + 1, current_page + 6)
    pages = list(range(start, end))

    if 1 not in pages:
        pages = [1, "..."] + pages
    if total_pages not in pages:
        pages = pages + ["...", total_pages]

    return pages


def _int_param(request, name: str, default: int, minimum: int = 1) -> int:
    try:
        value = int(request.GET.get(name, default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


def _browse_url(root_slug: str, rel_path: str = "") -> str:
    """Build a browse URL, quoting each path segment safely."""
    base = reverse("dj_file_browser_panel:browse_root", args=[root_slug])
    if not rel_path:
        return base
    return f"{base}{quote(rel_path, safe='/')}/"


def _query_suffix(request, include_hidden: bool = True) -> str:
    """Query string fragment preserving non-page params for pagination links."""
    preserved = {}
    hidden = request.GET.get("hidden")
    if include_hidden and hidden in ("0", "1"):
        preserved["hidden"] = hidden
    per_page = request.GET.get("per_page")
    if per_page:
        preserved["per_page"] = per_page
    return urlencode(preserved)


def _show_hidden(request) -> bool:
    override = request.GET.get("hidden")
    if override == "1":
        return True
    if override == "0":
        return False
    return bool(panel_config.get_settings("SHOW_HIDDEN"))


def _breadcrumbs(root: browser.Root, rel_path: str) -> list[dict]:
    crumbs = [
        {
            "name": root.name,
            "url": reverse("dj_file_browser_panel:browse_root", args=[root.slug]),
        }
    ]
    acc = ""
    for part in [p for p in rel_path.split("/") if p]:
        acc = f"{acc}/{part}" if acc else part
        crumbs.append({"name": part, "url": _browse_url(root.slug, acc)})
    return crumbs


@panel_config.permission_required("index")
def index(request):
    roots = [
        {
            "slug": root.slug,
            "name": root.name,
            "description": root.description,
            "path": str(root.path),
            "url": reverse("dj_file_browser_panel:browse_root", args=[root.slug]),
            "entry_count": browser.count_entries(root.path),
        }
        for root in browser.get_roots()
    ]
    context = panel_config.get_context(
        request,
        title="File Browser",
        roots=roots,
    )
    return render(request, "admin/dj_file_browser_panel/index.html", context)


def _resolve_root(root_slug: str) -> browser.Root:
    root = browser.get_root(root_slug)
    if root is None:
        raise Http404(f"File browser root '{root_slug}' not found")
    return root


@panel_config.permission_required("browse")
def browse_root(request, root_slug):
    return _browse(request, root_slug, "")


@panel_config.permission_required("browse")
def browse(request, root_slug, rel_path):
    return _browse(request, root_slug, rel_path)


def _browse(request, root_slug: str, rel_path: str):
    root = _resolve_root(root_slug)
    show_hidden = _show_hidden(request)

    context = panel_config.get_context(
        request,
        title=root.name,
        root=root,
        root_url=reverse("dj_file_browser_panel:browse_root", args=[root.slug]),
        rel_path=rel_path,
        breadcrumbs=_breadcrumbs(root, rel_path),
        show_hidden=show_hidden,
        hidden_toggle="0" if show_hidden else "1",
        qs_no_hidden=_query_suffix(request, include_hidden=False),
    )

    target = browser.resolve_in_root(root, rel_path)
    if target is None or not target.exists():
        context["error"] = (
            "That path is outside the configured root."
            if target is None
            else "Path does not exist."
        )
        return render(request, "admin/dj_file_browser_panel/browse.html", context)

    if target.is_dir():
        return _browse_directory(request, context, root, rel_path, show_hidden)

    if request.GET.get("content") == "1":
        return _serve_embed_content(target)

    info, error = browser.get_file_info(root, rel_path)
    if error:
        context["error"] = error
        return render(request, "admin/dj_file_browser_panel/browse.html", context)

    parent_rel = rel_path.rsplit("/", 1)[0] if "/" in rel_path else ""
    context.update(
        {
            "file": info,
            "parent_url": _browse_url(root.slug, parent_rel),
            "file_content_url": _browse_url(root.slug, rel_path) + "?content=1",
        }
    )
    return render(request, "admin/dj_file_browser_panel/file_detail.html", context)


def _serve_embed_content(target) -> FileResponse:
    """Stream a previewable binary file (image/PDF) inline.

    The path was already resolved inside a configured root by the caller.
    Only MIME types classified as ``"embed"`` previews are served, and only
    while ``PREVIEW_ENABLED`` is on.
    """
    mime_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    if browser.preview_kind(mime_type) != "embed":
        raise Http404("File type is not previewable")
    response = FileResponse(target.open("rb"), content_type=mime_type)
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _browse_directory(
    request, context, root: browser.Root, rel_path: str, show_hidden: bool
):
    page = _int_param(request, "page", 1)
    default_per_page = int(panel_config.get_settings("PAGE_SIZE") or 100)
    per_page = min(_int_param(request, "per_page", default_per_page), 500)

    listing = browser.list_directory(
        root,
        rel_path,
        show_hidden=show_hidden,
        page=page,
        per_page=per_page,
    )

    if listing.error:
        context["error"] = listing.error
        return render(request, "admin/dj_file_browser_panel/browse.html", context)

    entries = [
        replace(
            entry, url=_browse_url(root.slug, entry.rel_path) if entry.is_safe else ""
        )
        for entry in listing.entries
    ]
    context.update(
        {
            "entries": entries,
            "total_entries": listing.total,
            "current_page": listing.page,
            "per_page": listing.per_page,
            "total_pages": listing.total_pages,
            "has_previous": listing.page > 1,
            "has_next": listing.page < listing.total_pages,
            "previous_page": listing.page - 1,
            "next_page": listing.page + 1,
            "page_range": _get_page_range(listing.page, listing.total_pages),
            "qs_extra": _query_suffix(request),
            "start_index": (listing.page - 1) * listing.per_page + 1
            if listing.total
            else 0,
            "end_index": min(
                (listing.page - 1) * listing.per_page + len(entries), listing.total
            ),
        }
    )
    return render(request, "admin/dj_file_browser_panel/browse.html", context)

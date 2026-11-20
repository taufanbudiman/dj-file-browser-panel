[![Django Control Room Panel](https://img.shields.io/badge/Django%20Control%20Room-Panel-0c4b33?logo=django)](https://djangocontrolroom.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python versions](https://img.shields.io/pypi/pyversions/dj-file-browser-panel.svg)](https://pypi.org/project/dj-file-browser-panel/)
[![Coverage](https://img.shields.io/badge/coverage-93%25-brightgreen)](https://github.com/taufanbudiman/dj-file-browser-panel)


# Django File Browser Panel

A strictly **read-only** Django Admin panel for browsing the local filesystem —
`MEDIA_ROOT`, `STATIC_ROOT`, and any other configured roots — without shell
access. Part of the [Django Control Room](https://djangocontrolroom.com)
ecosystem.

Answer "did my upload land?" in two clicks: browse directories, check file
sizes and modified times, and optionally preview small text files — all from
the Django admin.

**Compatible with [dj-control-room](https://djangocontrolroom.com).** Register
this panel in the Control Room to manage it from a centralized dashboard.

- **Official site:** [djangocontrolroom.com](https://djangocontrolroom.com)
- **Panel registry:** [djangocontrolroom.com/panels](https://djangocontrolroom.com/panels)

## Features

- **Browsable roots**: `MEDIA_ROOT` and `STATIC_ROOT` by default, or any list
  of directories via `DJ_FILE_BROWSER_PANEL_SETTINGS["ROOTS"]`.
- **Directory listings**: folders first, then files; name, human-readable
  size, and modified time. Dotfiles hidden by default with a toggle.
- **Breadcrumbs + pagination**: navigate deep trees; large directories are
  paginated, never loaded whole.
- **File details**: path, size, modified time, MIME type guess, and an
  optional preview — text files inline (size-capped), images and PDF
  embedded via the browser.
- **Hard read-only**: no upload, delete, rename, or chmod — there is no
  mutation code path at all.
- **Path sandboxing**: every path is resolved and must stay inside a
  configured root. `..` traversal, absolute paths outside roots, and symlink
  escapes are rejected; escaping symlinks render as disabled entries.
- **No models, no migrations**: `managed=False` placeholder only.
- **Django admin styling**: dark mode and admin skins supported through
  `dj-control-room-base`.

## Requirements

- Python 3.9+
- Django 4.2+
- `dj-control-room-base` 1.6+

## Installation

```bash
pip install dj-file-browser-panel dj-control-room
```

Add it to `INSTALLED_APPS`, include its URLs, and migrate (the base package
needs it; this panel has no migrations of its own):

```python
INSTALLED_APPS = [
    # ...
    "dj_control_room_base",
    "dj_file_browser_panel",
    "dj_control_room",
    # ...
]
```

```python
urlpatterns = [
    path("admin/dj-control-room-base/", include("dj_control_room_base.urls")),
    path("admin/files/", include("dj_file_browser_panel.urls")),
    path("admin/dj-control-room/", include("dj_control_room.urls")),
    path("admin/", admin.site.urls),
]
```

```bash
python manage.py migrate
```

Then visit `/admin/` and look for the "DJ FILE BROWSER PANEL" section.

## Configuration

```python
DJ_FILE_BROWSER_PANEL_SETTINGS = {
    # None -> MEDIA_ROOT + STATIC_ROOT. Entries may be path strings or
    # {"name": ..., "path": ..., "description": ...} dicts.
    "ROOTS": [
        {"name": "Media", "path": MEDIA_ROOT},
        {"name": "Static", "path": STATIC_ROOT},
        "/var/www/uploads",
    ],
    "PAGE_SIZE": 100,
    "SHOW_HIDDEN": False,
    # File content preview (off by default). Raster images (except SVG)
    # and PDF are embedded inline. PREVIEW_TYPES allowlists *text* preview
    # MIME types (plus any text/* type), capped at PREVIEW_MAX_BYTES.
    "PREVIEW_ENABLED": False,
    "PREVIEW_MAX_BYTES": 262144,
    "PREVIEW_TYPES": [
        "application/json",
        "text/csv",
        "text/plain",
    ],
}
```

All keys are optional; unset keys fall back to the defaults above. Roots
that don't exist or aren't directories are skipped — if none are valid the
panel shows an empty state instead of an error.

Access control follows the `dj-control-room-base` panel permission model:
staff users only, with optional `ALLOWED_GROUPS`, `REQUIRE_SUPERUSER`, and
per-scope `SCOPE_PERMISSIONS` overrides — see the
[dj-control-room-base](https://github.com/django-control-room/dj-control-room)
documentation.

## Development

```bash
pip install -e ".[dev]"
pytest   # runs the suite and writes coverage.xml + htmlcov/
ruff check . && ruff format .
```

`example_project/` is a runnable Django project for manual testing:

```bash
cd example_project
python manage.py migrate
python manage.py runserver
# visit http://127.0.0.1:8000/admin/files/
```

Tests run with `pytest-django` against `tmp_path` fixtures — they never touch
the repo root or real media directories.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE)
file for details.

from dj_control_room_base.core import PanelConfig

panel_config = PanelConfig(
    settings_key="DJ_FILE_BROWSER_PANEL_SETTINGS",
    defaults={
        # None -> fall back to MEDIA_ROOT + STATIC_ROOT. Each entry may be a
        # path string or {"name": ..., "path": ..., "description": ...}.
        "ROOTS": None,
        "PAGE_SIZE": 100,
        "SHOW_HIDDEN": False,
        # File content preview: opt-in, size-capped, mime-allowlisted.
        "PREVIEW_ENABLED": False,
        "PREVIEW_MAX_BYTES": 262144,
        "PREVIEW_TYPES": [
            "application/json",
            "application/xml",
            "text/csv",
            "text/markdown",
            "text/plain",
            "text/xml",
        ],
    },
)

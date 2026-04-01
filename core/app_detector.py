"""Detects the frontmost macOS application."""


def get_active_app() -> str:
    """Returns display name of the frontmost app, e.g. 'Code', 'Terminal'."""
    try:
        from AppKit import NSWorkspace
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        return app.localizedName() or ""
    except Exception:
        return ""


def is_vscode_active() -> bool:
    name = get_active_app().lower()
    return "code" in name or "vscode" in name

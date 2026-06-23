"""
Accessibility Bridge — reads screen content via OS accessibility APIs.

Linux: AT-SPI2 (python3-pyatspi, system package)
macOS: Accessibility API via PyObjC (future)
Windows: UI Automation via pywinauto (future)
"""

import logging
import platform
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


class AccessibilityBridge:
    """Cross-platform accessibility tree reader."""

    def __init__(self):
        self._platform = platform.system()
        self._backend = None
        self._init_backend()

    def _init_backend(self):
        if self._platform == "Linux":
            try:
                import gi
                gi.require_version("Atspi", "2.0")
                from gi.repository import Atspi
                Atspi.init()
                self._backend = "atspi"
                logger.info("Accessibility bridge: AT-SPI2 (Linux)")
            except (ImportError, ValueError) as e:
                logger.warning(
                    f"AT-SPI not available ({e}). "
                    "Install with: sudo apt install python3-gi gir1.2-atspi-2.0 at-spi2-core"
                )
                self._backend = "xdotool_fallback"
        elif self._platform == "Darwin":
            logger.warning("macOS accessibility bridge not yet implemented (Goal 41)")
            self._backend = None
        elif self._platform == "Windows":
            logger.warning("Windows accessibility bridge not yet implemented (Goal 41)")
            self._backend = None

    def get_active_window(self) -> dict:
        """Get info about the currently focused window."""
        if self._backend == "atspi":
            return self._atspi_active_window()
        elif self._backend == "xdotool_fallback":
            return self._xdotool_active_window()
        return {"title": "unknown", "app": "unknown", "role": "unknown"}

    def get_window_text(self, max_depth: int = 10) -> str:
        """Extract all readable text from the focused window's accessibility tree."""
        if self._backend == "atspi":
            return self._atspi_window_text(max_depth)
        return ""

    def get_window_structure(self, max_depth: int = 5) -> list:
        """Get a structured list of UI elements in the active window."""
        if self._backend == "atspi":
            return self._atspi_window_structure(max_depth)
        return []

    def find_element(self, name: str = None, role: str = None) -> Optional[dict]:
        """Find a UI element by name or role in the active window."""
        structure = self.get_window_structure(max_depth=8)
        for elem in structure:
            if name and name.lower() in elem.get("name", "").lower():
                return elem
            if role and elem.get("role", "").lower() == role.lower():
                return elem
        return None

    # ---- AT-SPI2 implementation (Linux) ----

    def _atspi_active_window(self) -> dict:
        try:
            from gi.repository import Atspi
            desktop = Atspi.get_desktop(0)
            for i in range(desktop.get_child_count()):
                app = desktop.get_child_at_index(i)
                if app is None:
                    continue
                for j in range(app.get_child_count()):
                    win = app.get_child_at_index(j)
                    if win is None:
                        continue
                    states = win.get_state_set()
                    if states and states.contains(Atspi.StateType.ACTIVE):
                        return {
                            "title": win.get_name() or "untitled",
                            "app": app.get_name() or "unknown",
                            "role": win.get_role_name() or "window",
                        }
            return {"title": "unknown", "app": "unknown", "role": "window"}
        except Exception as e:
            logger.error(f"AT-SPI error: {e}")
            return self._xdotool_active_window()

    def _atspi_window_text(self, max_depth: int = 10) -> str:
        """Walk the accessibility tree and collect all text."""
        try:
            from gi.repository import Atspi
            desktop = Atspi.get_desktop(0)
            texts = []

            def walk(node, depth):
                if node is None or depth > max_depth:
                    return
                name = node.get_name()
                if name:
                    texts.append(name)
                try:
                    text_iface = node.get_text()
                    if text_iface:
                        content = text_iface.get_text(0, text_iface.get_character_count())
                        if content and content != name:
                            texts.append(content)
                except Exception:
                    pass
                for i in range(node.get_child_count()):
                    walk(node.get_child_at_index(i), depth + 1)

            # Find active window and walk it
            for i in range(desktop.get_child_count()):
                app = desktop.get_child_at_index(i)
                if app is None:
                    continue
                for j in range(app.get_child_count()):
                    win = app.get_child_at_index(j)
                    if win is None:
                        continue
                    states = win.get_state_set()
                    if states and states.contains(Atspi.StateType.ACTIVE):
                        walk(win, 0)
                        break

            return "\n".join(texts)
        except Exception as e:
            logger.error(f"AT-SPI text extraction error: {e}")
            return ""

    def _atspi_window_structure(self, max_depth: int = 5) -> list:
        """Get structured element list from accessibility tree."""
        try:
            from gi.repository import Atspi
            desktop = Atspi.get_desktop(0)
            elements = []

            def walk(node, depth):
                if node is None or depth > max_depth:
                    return
                elem = {
                    "name": node.get_name() or "",
                    "role": node.get_role_name() or "",
                    "depth": depth,
                }
                if elem["name"] or elem["role"] in ("heading", "link", "button", "entry", "table"):
                    elements.append(elem)
                for i in range(node.get_child_count()):
                    walk(node.get_child_at_index(i), depth + 1)

            for i in range(desktop.get_child_count()):
                app = desktop.get_child_at_index(i)
                if app is None:
                    continue
                for j in range(app.get_child_count()):
                    win = app.get_child_at_index(j)
                    if win is None:
                        continue
                    states = win.get_state_set()
                    if states and states.contains(Atspi.StateType.ACTIVE):
                        walk(win, 0)
                        break
            return elements
        except Exception as e:
            logger.error(f"AT-SPI structure error: {e}")
            return []

    # ---- Fallback using xdotool (if AT-SPI unavailable) ----

    def _xdotool_active_window(self) -> dict:
        try:
            win_id = subprocess.check_output(
                ["xdotool", "getactivewindow"], text=True, timeout=2
            ).strip()
            win_name = subprocess.check_output(
                ["xdotool", "getactivewindow", "getwindowname"], text=True, timeout=2
            ).strip()
            return {"title": win_name, "app": "unknown", "role": "window", "id": win_id}
        except Exception:
            return {"title": "unknown", "app": "unknown", "role": "window"}

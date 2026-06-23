"""
Action Executor — turns resolved intents into real OS actions.
Handles app launching, file operations, and UI navigation.
"""

import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ActionExecutor:
    """Executes resolved user intents as real system actions."""

    def __init__(self):
        self._app_registry: dict = {}
        self._build_app_registry()

    def _build_app_registry(self):
        """Scan for installed applications and build name->command mapping."""
        # Read .desktop files on Linux
        app_dirs = [
            Path("/usr/share/applications"),
            Path.home() / ".local/share/applications",
        ]
        for app_dir in app_dirs:
            if not app_dir.exists():
                continue
            for desktop_file in app_dir.glob("*.desktop"):
                try:
                    name, cmd, aliases = self._parse_desktop_file(desktop_file)
                    if name and cmd:
                        self._app_registry[name.lower()] = cmd
                        for alias in aliases:
                            self._app_registry[alias.lower()] = cmd
                except Exception:
                    continue

        # Add common aliases
        common_aliases = {
            "browser": "xdg-open http://",
            "chrome": "google-chrome",
            "firefox": "firefox",
            "terminal": "x-terminal-emulator",
            "file manager": "xdg-open .",
            "files": "xdg-open .",
            "calculator": "gnome-calculator",
            "text editor": "xdg-open",
            "settings": "gnome-control-center",
        }
        for alias, cmd in common_aliases.items():
            if alias not in self._app_registry:
                self._app_registry[alias] = cmd

        logger.info(f"App registry: {len(self._app_registry)} entries")

    def _parse_desktop_file(self, path: Path) -> tuple:
        """Parse a .desktop file for Name, Exec, and GenericName."""
        name = ""
        generic = ""
        cmd = ""
        for line in path.read_text(errors="ignore").splitlines():
            if line.startswith("Name=") and not name:
                name = line.split("=", 1)[1].strip()
            elif line.startswith("GenericName="):
                generic = line.split("=", 1)[1].strip()
            elif line.startswith("Exec="):
                cmd = line.split("=", 1)[1].strip()
                # Remove %u, %f, etc. field codes
                cmd = " ".join(p for p in cmd.split() if not p.startswith("%"))
        aliases = [generic] if generic else []
        return name, cmd, aliases

    def open_application(self, app_name: str) -> tuple[bool, str]:
        """Launch or foreground an application by name/alias."""
        key = app_name.lower().strip()

        # Check if already running (try to focus it)
        if self._try_focus_window(app_name):
            return True, f"{app_name} is already open, brought it to the front."

        # Look up in registry
        cmd = self._app_registry.get(key)
        if not cmd:
            # Fuzzy match: check if the key is a substring of any registry entry
            for reg_name, reg_cmd in self._app_registry.items():
                if key in reg_name or reg_name in key:
                    cmd = reg_cmd
                    break

        if not cmd:
            return False, f"I don't know how to open '{app_name}'. Could you be more specific?"

        try:
            subprocess.Popen(
                cmd, shell=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            time.sleep(1.5)  # Wait for window to appear

            # Verify it actually opened
            if self._try_focus_window(app_name):
                return True, f"Opened {app_name}."
            else:
                return True, f"Launched {app_name}, but I couldn't verify the window appeared."
        except Exception as e:
            return False, f"Failed to open {app_name}: {e}"

    def _try_focus_window(self, name: str) -> bool:
        """Try to find and focus a window matching the given name."""
        try:
            result = subprocess.run(
                ["wmctrl", "-l"], capture_output=True, text=True, timeout=2
            )
            for line in result.stdout.splitlines():
                if name.lower() in line.lower():
                    win_id = line.split()[0]
                    subprocess.run(["wmctrl", "-i", "-a", win_id], timeout=2)
                    return True
        except FileNotFoundError:
            # wmctrl not installed — try xdotool
            try:
                subprocess.run(
                    ["xdotool", "search", "--name", name, "windowactivate"],
                    timeout=2, capture_output=True,
                )
                return True
            except Exception:
                pass
        except Exception:
            pass
        return False

    def file_search(self, query: str, directory: str = None) -> list[dict]:
        """Search for files matching a query."""
        search_dir = directory or str(Path.home())
        results = []

        try:
            # Use 'find' for name matching (works everywhere)
            output = subprocess.check_output(
                ["find", search_dir, "-maxdepth", "5",
                 "-iname", f"*{query}*", "-not", "-path", "*/.*"],
                text=True, timeout=10, stderr=subprocess.DEVNULL,
            )
            for line in output.strip().splitlines()[:10]:  # Limit to 10 results
                p = Path(line)
                results.append({
                    "name": p.name,
                    "path": str(p),
                    "is_dir": p.is_dir(),
                    "size": p.stat().st_size if p.is_file() else 0,
                })
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            logger.warning(f"File search error: {e}")

        return results

    def file_open(self, path: str) -> tuple[bool, str]:
        """Open a file with its default application."""
        p = Path(path).expanduser()
        if not p.exists():
            return False, f"File not found: {path}"
        try:
            subprocess.Popen(["xdg-open", str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True, f"Opened {p.name}."
        except Exception as e:
            return False, f"Failed to open {p.name}: {e}"

    def create_folder(self, name: str, location: str = None) -> tuple[bool, str]:
        """Create a new folder."""
        base = Path(location).expanduser() if location else Path.home() / "Documents"
        target = base / name
        try:
            target.mkdir(parents=True, exist_ok=False)
            return True, f"Created folder '{name}' in {base}."
        except FileExistsError:
            return False, f"A folder named '{name}' already exists in {base}."
        except Exception as e:
            return False, f"Failed to create folder: {e}"

    def delete_file(self, path: str, use_trash: bool = True) -> tuple[bool, str]:
        """
        Delete a file or folder.
        By default moves to trash (recoverable) rather than permanent delete.
        """
        p = Path(path).expanduser()
        if not p.exists():
            return False, f"File not found: {path}"

        try:
            if use_trash:
                try:
                    import send2trash
                    send2trash.send2trash(str(p))
                    return True, f"Moved {p.name} to trash."
                except ImportError:
                    # Fallback: move to ~/.local/share/Trash
                    trash_dir = Path.home() / ".local/share/Trash/files"
                    trash_dir.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(p), str(trash_dir / p.name))
                    return True, f"Moved {p.name} to trash."
            else:
                if p.is_dir():
                    shutil.rmtree(str(p))
                else:
                    p.unlink()
                return True, f"Permanently deleted {p.name}."
        except Exception as e:
            return False, f"Failed to delete {p.name}: {e}"

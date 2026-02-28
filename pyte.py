"""Pyte compatibility shim.

If the real ``pyte`` package is installed, this module proxies to it.
Otherwise, it falls back to a minimal local implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib.machinery
import importlib.util
import os
import sys
from typing import Any


def _load_real_pyte() -> Any | None:
    here = os.path.realpath(os.path.dirname(__file__))
    search_paths = [p for p in sys.path if os.path.realpath(p or os.getcwd()) != here]
    spec = importlib.machinery.PathFinder.find_spec("pyte", search_paths)
    if spec is None or spec.loader is None or not spec.origin:
        return None
    if os.path.realpath(spec.origin) == os.path.realpath(__file__):
        return None

    alias = "_ghostty_real_pyte"
    alias_spec = importlib.util.spec_from_file_location(
        alias,
        spec.origin,
        submodule_search_locations=list(spec.submodule_search_locations or []),
    )
    if alias_spec is None or alias_spec.loader is None:
        return None

    module = importlib.util.module_from_spec(alias_spec)
    sys.modules[alias] = module
    try:
        alias_spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(alias, None)
        for key in list(sys.modules):
            if key.startswith(f"{alias}."):
                sys.modules.pop(key, None)
        return None
    return module


_real_pyte = _load_real_pyte()

if _real_pyte is not None and hasattr(_real_pyte, "Screen") and hasattr(_real_pyte, "Stream"):
    Screen = _real_pyte.Screen
    Stream = _real_pyte.Stream
    Cursor = getattr(_real_pyte, "Cursor", None)
else:

    @dataclass
    class Cursor:
        x: int = 0
        y: int = 0


    class Screen:
        def __init__(self, columns: int, lines: int):
            self.columns = columns
            self.lines = lines
            self.cursor = Cursor()
            self._grid = [[" " for _ in range(columns)] for _ in range(lines)]

        @property
        def display(self):
            return ["".join(row) for row in self._grid]

        def scroll_up(self, lines: int = 1):
            for _ in range(max(0, lines)):
                self._grid.pop(0)
                self._grid.append([" " for _ in range(self.columns)])


    class Stream:
        def __init__(self, screen: Screen | None = None):
            self.screen = screen
            self._esc = ""

        def feed(self, text: str):
            if not self.screen:
                return
            for ch in text:
                if self._esc:
                    self._esc += ch
                    if self._esc.startswith("\x1b["):
                        if len(self._esc) >= 3 and self._is_csi_final(ch):
                            self._apply_csi(self._esc)
                            self._esc = ""
                        elif len(self._esc) > 64:
                            self._esc = ""
                    else:
                        self._esc = ""
                    continue

                if ch == "\x1b":
                    self._esc = ch
                elif ch == "\r":
                    self.screen.cursor.x = 0
                elif ch == "\n":
                    if self.screen.cursor.y >= self.screen.lines - 1:
                        self.screen.scroll_up(1)
                    else:
                        self.screen.cursor.y += 1
                elif ch == "\x08":
                    self.screen.cursor.x = max(0, self.screen.cursor.x - 1)
                else:
                    self._put(ch)

        @staticmethod
        def _is_csi_final(ch: str) -> bool:
            return 0x40 <= ord(ch) <= 0x7E

        def _put(self, ch: str):
            x, y = self.screen.cursor.x, self.screen.cursor.y
            if 0 <= x < self.screen.columns and 0 <= y < self.screen.lines:
                self.screen._grid[y][x] = ch
            if x + 1 >= self.screen.columns:
                self.screen.cursor.x = 0
                if y >= self.screen.lines - 1:
                    self.screen.scroll_up(1)
                    self.screen.cursor.y = self.screen.lines - 1
                else:
                    self.screen.cursor.y = y + 1
            else:
                self.screen.cursor.x += 1

        def _apply_csi(self, seq: str):
            if not self.screen:
                return

            params = seq[2:-1]
            final = seq[-1]
            c = self.screen.cursor

            values = []
            for raw in params.split(";") if params else []:
                if raw.isdigit():
                    values.append(int(raw))
                elif raw == "":
                    values.append(0)
                else:
                    values.append(0)

            def v(index: int, default: int) -> int:
                if index >= len(values):
                    return default
                return values[index] if values[index] != 0 else default

            if final == "A":
                c.y = max(0, c.y - v(0, 1))
            elif final == "B":
                c.y = min(self.screen.lines - 1, c.y + v(0, 1))
            elif final == "C":
                c.x = min(self.screen.columns - 1, c.x + v(0, 1))
            elif final == "D":
                c.x = max(0, c.x - v(0, 1))
            elif final in {"H", "f"}:
                row = v(0, 1)
                col = v(1, 1)
                c.y = min(self.screen.lines - 1, max(0, row - 1))
                c.x = min(self.screen.columns - 1, max(0, col - 1))
            elif final == "J":
                mode = values[0] if values else 0
                if mode == 2:
                    self.screen._grid = [[" " for _ in range(self.screen.columns)] for _ in range(self.screen.lines)]
                    c.x = 0
                    c.y = 0
            elif final == "K":
                y = c.y
                for x in range(c.x, self.screen.columns):
                    self.screen._grid[y][x] = " "

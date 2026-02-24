"""Minimal pyte-compatible subset for GhosTTY prototype.

Implements only the Screen/Stream APIs used by this repository.
"""

from dataclasses import dataclass


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
                if self._esc in ("\x1b[A", "\x1b[B", "\x1b[C", "\x1b[D"):
                    self._apply_esc(self._esc)
                    self._esc = ""
                elif len(self._esc) >= 3 and not self._esc.startswith("\x1b["):
                    self._esc = ""
                continue

            if ch == "\x1b":
                self._esc = ch
            elif ch == "\r":
                self.screen.cursor.x = 0
            elif ch == "\n":
                self.screen.cursor.y = min(self.screen.lines - 1, self.screen.cursor.y + 1)
            elif ch == "\x08":
                self.screen.cursor.x = max(0, self.screen.cursor.x - 1)
            else:
                self._put(ch)

    def _put(self, ch: str):
        x, y = self.screen.cursor.x, self.screen.cursor.y
        if 0 <= x < self.screen.columns and 0 <= y < self.screen.lines:
            self.screen._grid[y][x] = ch
        if x + 1 >= self.screen.columns:
            self.screen.cursor.x = 0
            self.screen.cursor.y = min(self.screen.lines - 1, y + 1)
        else:
            self.screen.cursor.x += 1

    def _apply_esc(self, seq: str):
        c = self.screen.cursor
        if seq == "\x1b[A":
            c.y = max(0, c.y - 1)
        elif seq == "\x1b[B":
            c.y = min(self.screen.lines - 1, c.y + 1)
        elif seq == "\x1b[C":
            c.x = min(self.screen.columns - 1, c.x + 1)
        elif seq == "\x1b[D":
            c.x = max(0, c.x - 1)

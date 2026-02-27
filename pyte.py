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
                self.screen.cursor.y = min(self.screen.lines - 1, self.screen.cursor.y + 1)
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
            self.screen.cursor.y = min(self.screen.lines - 1, y + 1)
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

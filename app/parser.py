import hashlib
import re

ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
CTRL_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


def normalize_screen(raw: str) -> tuple[str, list[str], bool, str]:
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = ANSI_RE.sub("", text)
    text = CTRL_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line.rstrip() for line in text.split("\n")]
    prompt_detected = bool(lines and re.search(r"[:>\]]\s*$", lines[-1]))
    digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
    return text, lines, prompt_detected, f"sha256:{digest}"

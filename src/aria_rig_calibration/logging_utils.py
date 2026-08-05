"""Structured logging with warning/error collectors for the toolkit."""
from __future__ import annotations
import logging
from pathlib import Path


class CollectingLogger:
    """Wraps a stdlib logger and collects warnings/errors for the run's warnings.csv/errors.csv."""

    def __init__(self, log_file: Path | None = None, level: str = "INFO") -> None:
        self.warnings: list[dict] = []
        self.errors: list[dict] = []
        self._log = logging.getLogger("aria_rig")
        self._log.handlers.clear()
        self._log.setLevel(getattr(logging, level, logging.INFO))
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        sh = logging.StreamHandler(); sh.setFormatter(fmt); self._log.addHandler(sh)
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(log_file, mode="w", encoding="utf-8"); fh.setFormatter(fmt); self._log.addHandler(fh)

    def info(self, msg, *a):
        self._log.info(msg, *a)

    def warning(self, msg, *a):
        self._log.warning(msg, *a); self.warnings.append({"message": (msg % a) if a else msg})

    def error(self, msg, *a):
        self._log.error(msg, *a); self.errors.append({"message": (msg % a) if a else msg})

    def close(self):
        """Close and detach handlers so the log file is released (needed before deleting the run dir)."""
        for h in list(self._log.handlers):
            try:
                h.close()
            finally:
                self._log.removeHandler(h)

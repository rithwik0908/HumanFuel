"""Console entry point. Delegates to scripts/run_analysis.py so a single orchestrator drives both
the installed command and direct ``python scripts/run_analysis.py`` invocation."""
from __future__ import annotations
import runpy
from pathlib import Path


def main() -> None:
    """Run the analysis pipeline (see ``scripts/run_analysis.py`` for the full argument list)."""
    script = Path(__file__).resolve().parents[2] / "scripts" / "run_analysis.py"
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()

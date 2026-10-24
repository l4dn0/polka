"""Double-click launcher for Windows (opens without a black console)."""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).with_name("polka.py")), run_name="__main__")

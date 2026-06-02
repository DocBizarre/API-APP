"""Wrapper qui lance l'app EMS en mode parc."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ems_project = HERE / "ems_project"
if ems_project.is_dir():
    sys.path.insert(0, str(ems_project))

from main import AppEMS
AppEMS(mode="parc").mainloop()

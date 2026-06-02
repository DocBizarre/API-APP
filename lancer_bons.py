"""Wrapper qui lance l'app EMS en mode bons."""
import sys
from pathlib import Path

# Ajout du dossier ems_project au sys.path pour que les imports relatifs marchent
HERE = Path(__file__).resolve().parent
ems_project = HERE / "ems_project"
if ems_project.is_dir():
    sys.path.insert(0, str(ems_project))

from main import AppEMS
AppEMS(mode="bons").mainloop()

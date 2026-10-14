"""Keep consolidation test stores and mutations within this checkout."""
from pathlib import Path
import tempfile

def temporary_directory():
    root=Path(__file__).resolve().parents[1]/'out/test_scratch'
    root.mkdir(parents=True,exist_ok=True)
    return tempfile.TemporaryDirectory(dir=root)

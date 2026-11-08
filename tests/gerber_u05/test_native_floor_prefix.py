from pathlib import Path
import hashlib
import pytest
from src.gerber_u05.prefix import NATIVE_FLOOR_CHECK,native_floor_check_delta


@pytest.mark.parametrize('name',sorted(NATIVE_FLOOR_CHECK))
def test_only_exact_t05_floor_check_revision_is_adoptable(name):
 before,after=NATIVE_FLOOR_CHECK[name]
 root=Path(__file__).resolve().parents[2]
 assert hashlib.sha256((root/name).read_bytes()).hexdigest()==after
 assert native_floor_check_delta(name,before,after)
 assert not native_floor_check_delta(name,'0'*64,after)
 assert not native_floor_check_delta(name,before,'0'*64)
 assert not native_floor_check_delta('src/unknown.py',before,after)

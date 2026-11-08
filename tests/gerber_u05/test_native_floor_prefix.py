from pathlib import Path
import hashlib
import pytest
from src.gerber_u05.prefix import NATIVE_FLOOR_CHECK,native_floor_check_delta,STAGE_ENTRY_T05_ONLY,stage_entry_delta


@pytest.mark.parametrize('name',sorted(NATIVE_FLOOR_CHECK))
def test_only_exact_t05_floor_check_revision_is_adoptable(name):
 before,after=NATIVE_FLOOR_CHECK[name]
 root=Path(__file__).resolve().parents[2]
 current=hashlib.sha256((root/name).read_bytes()).hexdigest()
 assert current==after or STAGE_ENTRY_T05_ONLY.get(name)==(after,current)
 assert native_floor_check_delta(name,before,after)
 assert not native_floor_check_delta(name,'0'*64,after)
 assert not native_floor_check_delta(name,before,'0'*64)
 assert not native_floor_check_delta('src/unknown.py',before,after)


@pytest.mark.parametrize('name',sorted(STAGE_ENTRY_T05_ONLY))
def test_stage_entry_retains_exact_upstream_transition_hashes(name):
 before,after=STAGE_ENTRY_T05_ONLY[name]
 root=Path(__file__).resolve().parents[2]
 assert hashlib.sha256((root/name).read_bytes()).hexdigest()==after
 assert before==NATIVE_FLOOR_CHECK[name][1]
 assert before!=after and len(before)==len(after)==64


@pytest.mark.parametrize('name',sorted(STAGE_ENTRY_T05_ONLY))
def test_stage_entry_adopts_only_explicit_t05_revision_chain(name):
 before,after=STAGE_ENTRY_T05_ONLY[name]
 assert stage_entry_delta(name,before,after)
 assert stage_entry_delta(name,NATIVE_FLOOR_CHECK[name][0],after)
 assert not stage_entry_delta(name,'0'*64,after)
 assert not stage_entry_delta(name,before,'0'*64)

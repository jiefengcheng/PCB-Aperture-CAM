"""Exact retained witness for a shared-end finite overlay disconnection."""
import os
from pathlib import Path
import pytest
from shapely import from_wkb,to_wkb
from src.original_copper_owners import OriginalOwners
from src.gerber_u05.finite_profile_union import certified_union
from src.gerber_u05.native_contact_support import assemble
from src.gerber_u05.normalized_additions import verify


def witness():
    name=os.environ.get('PCB_T04_NATIVE_CONTACT_REPRO')
    if not name:pytest.skip('Retained full-board finite-overlay operands not supplied')
    root=Path(name)
    load=lambda n:from_wkb((root/n).read_bytes())
    bodies={str(i):load(f'route_union/{i}.wkb')for i in range(5)}
    return bodies,load('operands/430693:430718_0_cap.wkb')


def test_saved_shared_end_recovery_preserves_the_exact_declared_source_floor():
    bodies,cap=witness();before={s:to_wkb(g)for s,g in bodies.items()}
    joined,method=certified_union(bodies['2'],cap)
    assert method!='EXACT_FLOOR_FALLBACK'and joined.covers(bodies['2'])
    assert len(OriginalOwners(assemble(list(bodies),bodies,{})).owners)==2
    fixed=dict(bodies,**{'2':joined})
    assert len(OriginalOwners(assemble(list(fixed),fixed,{})).owners)==1
    assert before=={s:to_wkb(g)for s,g in bodies.items()}


def test_saved_shared_end_recovery_remains_subject_to_foreign_clearance():
    bodies,cap=witness();joined,_=certified_union(bodies['2'],cap)
    addition=joined.difference(bodies['2'])
    assert not addition.is_empty
    blocker=addition.representative_point().buffer(.001)
    assert not verify(bodies['2'],joined,[dict(id='foreign',geometry=blocker)])['passed']

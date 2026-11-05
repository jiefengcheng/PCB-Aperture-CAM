import sys
from pathlib import Path
import pytest
from src.gerber_u05 import pipeline
from src.growth_void_support import ContactSupport
from src.growth_void_remedy_v09 import RemedyContract
from shapely.geometry import box

def row(name,g,w=.1):return dict(id=name,original=g,width_mm=w)

def test_distant_global_connection_cannot_authorize_parallel_gap_fill():
 records=[row('a',box(0,0,3,.1)),row('b',box(0,.15,3,.25)),row('end',box(-.05,0,.05,.25))]
 check=ContactSupport(records,.04002).check(box(1,.1,2,.15))
 assert not check['passed'] and check['missing_source_contact_support_mm2']>.04

def test_local_original_junction_has_bound_support():
 records=[row('a',box(0,0,.3,.1)),row('b',box(.1,0,.2,.3))]
 check=ContactSupport(records,.04002).check(box(.12,.08,.16,.14))
 assert check['passed'] and check['source_pairs']==[['a','b']]

def test_no_original_contact_gets_no_permission():
 records=[row('a',box(0,0,.1,.1)),row('b',box(.11,0,.21,.1))]
 assert not ContactSupport(records,.04002).check(box(.1,.02,.11,.08))['passed']

def test_invalid_or_duplicate_source_metadata_rejects():
 with pytest.raises(ValueError,match='INVALID_CONTACT_SOURCE'):ContactSupport([row('a',box(0,0,1,1),float('nan'))],.04)
 with pytest.raises(ValueError,match='UNIQUE_CONTACT_SOURCES'):ContactSupport([row('a',box(0,0,1,1)),row('a',box(1,0,2,1))],.04)

def test_file_uncertainty_and_area_epsilon_cannot_silently_relax():
 with pytest.raises(ValueError,match='REMEDY_FILE_POLICY_CHANGED'):RemedyContract(file_uncertainty_mm=.001).validate()
 with pytest.raises(ValueError,match='REMEDY_FILE_POLICY_CHANGED'):RemedyContract(area_epsilon_mm2=.01).validate()

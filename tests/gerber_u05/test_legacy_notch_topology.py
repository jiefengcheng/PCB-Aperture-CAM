import sys
from pathlib import Path
from src.gerber_u05 import pipeline
from src.growth_void_remedy_v09 import plan,holes
from shapely.geometry import box

def test_narrowing_mouth_cannot_create_a_new_trapped_void():
 source=box(0,0,1,1).difference(box(.3,.3,1.1,.7))
 current=source.union(box(.8,.3,1,.48)).union(box(.8,.52,1,.7))
 report,_,after=plan(source,current)
 assert not holes(current)
 assert not holes(after), 'Open-notch remedy must not leave a newly trapped cavity'

def test_real_growth_narrowed_notch_has_a_positive_fill():
 source=box(0,0,1,1).difference(box(.75,.43,1.1,.57))
 current=source.union(box(.8,.43,1,.49)).union(box(.8,.51,1,.57))
 report,fills,after=plan(source,current)
 assert any(r['kind']=='notch'for r in fills)
 assert after.area>current.area
 assert not holes(after)

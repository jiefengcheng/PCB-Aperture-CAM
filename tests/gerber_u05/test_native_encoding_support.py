import copy
import pytest
from shapely.geometry import Polygon
from src.gerber_u05 import exporter as e
G=1e-6

def support(tmp_path,radius=G):
 store=e.p.Store(tmp_path/'store');x,y=1.,1.;shape=Polygon([(x-radius,y),(x,y-radius),(x+radius,y),(x,y+radius)])
 rows=[];blocks=[];e.append_regions(shape,'t05','route',rows,blocks,store)
 for row in rows:row['encoding_support']=dict(cap_radius_mm=G,component_area_mm2=G*G/2,gap_to_encoded_owner_mm=G/2)
 value=dict(candidate=dict(decisions=[dict(source_id='route',status='GROWN')]))
 return store,rows,value

def test_existing_one_grid_support_remains_explicitly_accounted_for(tmp_path):
 store,rows,value=support(tmp_path);parents=e.encoding_support_parents(store,rows,value)
 assert len(parents)==1 and parents[0][0][:2]==('t05','route')
 assert e.encoding_support_parents(store,[],value)==[]

@pytest.mark.parametrize('change',['owner','radius','component_area','gap','diamond','parent_sha'])
def test_encoding_support_cannot_become_a_material_exemption(tmp_path,change):
 store,rows,value=support(tmp_path,radius=2*G if change=='diamond'else G)
 if change=='owner':rows[0]['source_id']='unrelated'
 elif change=='radius':rows[0]['encoding_support']['cap_radius_mm']=2*G
 elif change=='component_area':rows[0]['encoding_support']['component_area_mm2']=2*G*G
 elif change=='gap':rows[0]['encoding_support']['gap_to_encoded_owner_mm']=2*G
 elif change=='parent_sha':rows[0]['component_reference_proof']['partition_parent_reference_proof']['export_reference_sha256']='0'*64
 with pytest.raises(ValueError,match='NATIVE_ENCODING_SUPPORT'):e.encoding_support_parents(store,rows,value)

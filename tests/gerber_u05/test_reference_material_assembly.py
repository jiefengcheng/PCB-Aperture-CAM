import copy
from pathlib import Path
import pytest
from shapely import from_wkb,to_wkb
from shapely.geometry import box
from shapely.affinity import translate
from src.gerber_u05 import pipeline as p,legacy_export
from src.gerber_u05.reference_recipe import append_reference_region,reconstruct_reference_material
from src.gerber_u05.native_assembly import assemble

def fixture(tmp_path):
 file=Path(__file__).parent/'fixtures/reference_minimum_grid_hole/region.wkb'
 shape=from_wkb(file.read_bytes());store=p.Store(tmp_path/'runtime');records=[];blocks=[]
 refs=append_reference_region(shape,'inclusive_remedy','test',records,blocks,store)
 for row in records:row['owner']=0
 body=('%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,0.1*%\n'+''.join(blocks)+'M02*\n').encode()
 native=legacy_export.parse(body)
 shapes=[p.affine_scale(p.source_profile.object_geometry(obj)[0],1,-1,origin=(0,0))for obj in native.objects]
 parents=[(('inclusive_remedy','test',p.digest(to_wkb(ref))),ref)for ref in refs]
 return box(40,40,41,41),shapes,records,parents,{key:0 for key,_ in parents}

def test_reparsed_exact_faces_reassemble_the_independent_parent(tmp_path):
 current,shapes,records,parents,owners=fixture(tmp_path)
 after,image,material,owner_rows,proof=reconstruct_reference_material(current,shapes,records,parents,owners,grid_mm=1e-6)
 expected=assemble(current,[ref for _,ref in parents],grid_mm=1e-6)
 assert to_wkb(image)==to_wkb(expected)
 assert len(shapes)>1 and len(material)==1 and len(material[0].interiors)==1
 assert after.covers(current) and owner_rows==[dict(owner=0)]
 assert proof['status']=='EXACT_PARSED_NATIVE_MATERIAL'
 assert proof['partitions']['tolerance_allowance']is False

@pytest.mark.parametrize('corruption',['missing_face','moved_face','owner'])
def test_assembly_never_hides_native_corruption(tmp_path,corruption):
 current,shapes,records,parents,owners=fixture(tmp_path)
 if corruption=='missing_face':shapes=shapes[:-1];records=records[:-1]
 elif corruption=='moved_face':shapes[0]=translate(shapes[0],xoff=5e-6)
 else:records=copy.deepcopy(records);records[0]['owner']=1
 with pytest.raises(ValueError):reconstruct_reference_material(current,shapes,records,parents,owners,grid_mm=1e-6)

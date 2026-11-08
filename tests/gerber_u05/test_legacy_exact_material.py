from pathlib import Path
import pytest
from shapely import from_wkb,to_wkb
from src.gerber_u05 import pipeline as p,legacy_export as e
from src.gerber_u05.native_assembly import weld,assemble
from src.gerber_u05.native_material import equality
G=1e-6


def encoded(tmp_path,target):
 store=p.Store(tmp_path/'runtime');rows=[];blocks=[];parents=e.append_regions(target,'t05','route',rows,blocks,store)
 body=b'%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,0.100000*%\n'+''.join(blocks).encode()+b'M02*\n'
 actual=[p.affine_scale(p.source_profile.object_geometry(o)[0],1,-1,origin=(0,0))for o in e.parse(body).objects]
 identities=[(('t05','route',r['component_reference_proof']['partition_parent_reference_proof']['export_reference_sha256']),shape)for r,shape in zip(rows,parents)]
 return store,rows,actual,identities,parents


@pytest.mark.parametrize('fixture',['exact_cut_in/target_1.wkb','failed_reference.wkb'])
def test_legacy_encoding_proves_complete_native_material_and_preserves_holes(tmp_path,fixture):
 target=from_wkb((Path(__file__).parent/'fixtures'/fixture).read_bytes());store,rows,actual,identities,parents=encoded(tmp_path,target)
 # Fixture has one native parent; any number of serialized positive faces.
 reference,_=e.export_reference(e.connected_native_normalization(target)[0]);identity=rows[0]['component_reference_proof']['partition_parent_reference_proof']['export_reference_sha256'];joined,proof=weld(rows,actual,[(('t05','route',identity),reference)],grid_mm=G)
 assert proof['parsed_regions']==len(actual) and proof['parents']==1 and not proof['tolerance_allowance']
 assert len(joined[0][1].interiors)==len(target.interiors)
 reference,_=e.export_reference(e.connected_native_normalization(target)[0]);equality(reference,joined[0][1],grid_mm=G)


def test_reparsed_corruption_cannot_be_hidden_by_the_material_parent(tmp_path):
 target=p.box(0,0,.001,.001);store,rows,actual,identities,parents=encoded(tmp_path,target)
 actual[0]=actual[0].union(p.box(.001,0,.001002,.0005))
 with pytest.raises(ValueError,match='MATERIAL_CHANGED'):weld(rows,actual,identities,grid_mm=G)

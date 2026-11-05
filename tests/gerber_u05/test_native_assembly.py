import copy,hashlib
from pathlib import Path
import pytest
from shapely import to_wkb,from_wkb,constrained_delaunay_triangles
from shapely.geometry import Polygon,box
from shapely.affinity import translate
from src.gerber_u05.native_assembly import weld,assemble
from src.gerber_u05.native_material import equality
G=1e-6

def encoded(target,pieces,status='EXACT_INTEGER_GRID_PARTITION'):
 sha=hashlib.sha256(to_wkb(target)).hexdigest();key=('t04_finish','original-owner',sha)
 rows=[dict(stage=key[0],source_id=key[1],component_reference_proof=dict(partition_parent_reference_proof={'export_reference_sha256':sha},serialization_part=i,serialization_partition=dict(status=status,parts=len(pieces))))for i in range(len(pieces))]
 return rows,[(key,target)]

def split_square():
 square=box(0,0,4*G,4*G);triangles=list(constrained_delaunay_triangles(square).geoms)
 return square,triangles

def test_representation_count_and_legal_subdivision_do_not_change_copper():
 target,pieces=split_square();rows,parents=encoded(target,pieces);joined,proof=weld(rows,pieces,parents,grid_mm=G)
 assert proof['parsed_regions']==2 and proof['parents']==1 and not proof['tolerance_allowance']
 source=box(-10*G,-10*G,-5*G,-5*G)
 assert to_wkb(assemble(source,[target],grid_mm=G))==to_wkb(assemble(source,[g for _,g in joined],grid_mm=G))
 equality(target,joined[0][1],grid_mm=G)

def test_missing_piece_fails_even_when_corrupt_ledger_also_loses_row():
 target,pieces=split_square();rows,parents=encoded(target,pieces)
 with pytest.raises(ValueError,match='PART_COUNT_CHANGED'):weld(rows[:-1],pieces[:-1],parents,grid_mm=G)

def test_duplicate_equal_area_triangle_cannot_replace_its_neighbor():
 target,pieces=split_square();rows,parents=encoded(target,pieces)
 assert pieces[0].area==pieces[1].area
 with pytest.raises(ValueError,match='BOUNDARY'):weld(rows,[pieces[0],pieces[0]],parents,grid_mm=G)

def test_shifted_grid_edge_fails_exact_material_proof():
 target,pieces=split_square();rows,parents=encoded(target,pieces);pieces[0]=translate(pieces[0],xoff=G)
 with pytest.raises(ValueError):weld(rows,pieces,parents,grid_mm=G)

def test_filling_source_hole_cannot_pass_as_more_simple_regions():
 target=Polygon([(0,0),(8*G,0),(8*G,8*G),(0,8*G)],holes=[[(2*G,2*G),(2*G,6*G),(6*G,6*G),(6*G,2*G)]])
 pieces=list(constrained_delaunay_triangles(target).geoms);pieces+=list(constrained_delaunay_triangles(box(2*G,2*G,6*G,6*G)).geoms)
 rows,parents=encoded(target,pieces)
 with pytest.raises(ValueError,match='AREA_CHANGED'):weld(rows,pieces,parents,grid_mm=G)

def test_parent_identity_and_owner_inventory_are_mandatory():
 target,pieces=split_square();rows,parents=encoded(target,pieces);rows[0]['source_id']='foreign-owner'
 with pytest.raises(ValueError,match='INVENTORY_CHANGED'):weld(rows,pieces,parents,grid_mm=G)

def test_part_indices_cannot_hide_an_omitted_or_repeated_record():
 target,pieces=split_square();rows,parents=encoded(target,pieces);rows[1]['component_reference_proof']['serialization_part']=0
 with pytest.raises(ValueError,match='PART_INVENTORY'):weld(rows,pieces,parents,grid_mm=G)

def test_minimum_positive_face_is_retained_and_cannot_be_omitted():
 target=Polygon([(0,0),(G,0),(0,G)]);rows,parents=encoded(target,[target],'ORIGINAL_CUT_IN_ENCODING');joined,proof=weld(rows,[target],parents,grid_mm=G)
 assert joined[0][1].area==G*G/2 and proof['parents']==1
 with pytest.raises(ValueError,match='PARENT_INVENTORY'):weld([],[],parents,grid_mm=G)

def test_retained_point_touch_hole_partition_assembles_without_hole_loss():
 target=from_wkb((Path(__file__).parent/'fixtures/failed_reference.wkb').read_bytes())
 pieces=list(constrained_delaunay_triangles(target).geoms);rows,parents=encoded(target,pieces);joined,proof=weld(rows,pieces,parents,grid_mm=G)
 equality(target,joined[0][1],grid_mm=G)
 assert len(target.interiors)==len(joined[0][1].interiors)==1 and len(pieces)==211

def test_old_tolerated_rounded_bridge_is_rejected_by_actual_material_check():
 from src.pcb_data_abi.board_geometry import bridge_contour
 from src.gerber_image import contour
 target=from_wkb((Path(__file__).parent/'fixtures/exact_cut_in/target_1.wkb').read_bytes());points=bridge_contour(target);actual=contour(points+[points[0]])
 rows,parents=encoded(target,[actual],'ORIGINAL_CUT_IN_ENCODING')
 with pytest.raises(ValueError,match='MATERIAL_CHANGED'):weld(rows,[actual],parents,grid_mm=G)

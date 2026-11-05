from pathlib import Path
import pytest
from shapely import from_wkb,set_precision,to_wkb
from shapely.geometry import Polygon,box
from shapely.ops import unary_union
from src.gerber_u05 import pipeline as p
from src.gerber_u05 import legacy_export as e
from test_gerber_source import source_circle
from src.component_absorption import absorb
from src.component_voids import RemedyContract,plan,holes
from src.native_grid_reference import reference,normalize,fidelity
q=Path(__file__).resolve().parent

def actual():return from_wkb((q/'fixtures/actual_t04_fill.wkb').read_bytes())

def test_retained_actual_failure_is_absorbed_into_existing_shape_before_storage(tmp_path):
 g=set_precision(actual(),.000001,mode='pointwise');x,y,x1,y1=g.bounds;owner=box(x-.01,y-.01,x1+.01,y1+.01)
 grown,receipt=absorb(g,owner,owner,[],RemedyContract())
 assert receipt['holes_absorbed']==1 and not grown.interiors
 assert grown.exterior.equals(g.exterior)and g.difference(grown).is_empty
 assert receipt['records'][0]['new_physical_copper_mm2']==0
 # One existing region, with the microscopic void absorbed; no hole artifact.
 store=p.Store(tmp_path/'store');records=[];blocks=[];e.append_regions(grown,'t04_finish','existing-owner',records,blocks,store)
 assert len(records)==1
 base,_=e.canonical_base(source_circle());native=e.parse((base+''.join(blocks)+'M02*\n').encode());observed=p.affine_scale(p.source_profile.object_geometry(native.objects[-1])[0],1,-1,origin=(0,0))
 assert fidelity(grown,observed)['passed']and not observed.interiors

def test_original_microscopic_source_hole_is_protected():
 g=actual();grown,receipt=absorb(g,g,g,[],RemedyContract())
 assert grown.equals(g)and receipt['holes_absorbed']==0
 assert receipt['records'][0]['status']=='KEEP_ORIGINAL_SOURCE_VOID'

def test_new_thin_hole_can_be_absorbed_after_original_inclusive_checks():
 hole=Polygon([(0,0),(.00015,.00019),(.00012,.000151999999)])
 outer=box(-.001,-.001,.001,.001);current=outer.difference(hole);source=current.difference(box(0,0,.001,.000002))
 grown,receipt=absorb(current,current,source,[],RemedyContract())
 assert receipt['holes_absorbed']==1 and not grown.interiors
 assert any(r['check']['passed']for r in receipt['records'])

def test_distinct_foreign_copper_still_blocks_absorption():
 g=actual();h=Polygon(g.interiors[0]);source=g.difference(h.buffer(.0001));pt=h.representative_point();foreign=box(pt.x-.00000001,pt.y-.00000001,pt.x+.00000001,pt.y+.00000001)
 grown,receipt=absorb(g,g,source,[('foreign',foreign)],RemedyContract())
 assert receipt['holes_absorbed']==0 and len(grown.interiors)==1
 assert any('FOREIGN_CLEARANCE_FAILED'in r.get('check',{}).get('reasons',[])for r in receipt['records'])

def test_resolvable_hole_is_not_a_microscopic_encoding_shortcut():
 g=box(0,0,1,1).difference(box(.4,.4,.6,.6));owner=box(0,0,1,1)
 grown,receipt=absorb(g,owner,owner,[],RemedyContract())
 assert receipt['holes_absorbed']==0 and grown.equals(g)

def test_original_sub_epsilon_source_void_is_never_a_growth_hole():
 h=Polygon([(0,0),(.000001,0),(0,.000001)]);source=box(-1,-1,1,1).difference(h)
 report,fills,after=plan(source,source)
 assert not fills and len(holes(after))==1
 assert any(r['status']=='KEEP_SOURCE_VOID'for r in report['records'])

@pytest.mark.parametrize('tagged',[False,True])
def test_minimum_positive_triangle_survives_coordinate_bound_normalization(tagged):
 g=Polygon([(38.4,-13.7),(38.400001,-13.7),(38.4,-13.699999)])
 if tagged:g=set_precision(g,.000001,mode='pointwise')
 out=normalize(g);assert out.is_valid and out.area>0 and out.hausdorff_distance(g)<1e-13

def test_default_reuses_one_owner_surface_across_downstream_stages(tmp_path,monkeypatch):
 from src.gerber_u05 import component_finish as finish
 from src.gerber_u05.component_policy import capture_job
 from src import component_clearance as cc
 run=tmp_path/'job';run.mkdir();capture_job(run);store=p.Store(run/'runtime')
 first=box(.8,.8,1.2,1.2);second=box(2.8,.8,3.2,1.2);c1=box(.96,1.1,1.04,2.1);c2=box(2.96,1.1,3.04,2.1)
 source=box(0,0,4,2).difference(unary_union([first,second,c1,c2]));ctx=cc.bind(source,'0'*64,{'original':source});own=ctx.owner('original');ctx.reserved={own:source}
 grown=source.union(box(.96,1.1,1.04,2));original_ref=p.geomref(store,source)
 scene=dict(viewport_mm=[-1,-1,5,3],lineage=[dict(stage='source')],objects=[dict(source_id='original',kind='fixed_source',original_ref=original_ref,geometry_ref=p.geomref(store,grown),metadata={})])
 monkeypatch.setattr(finish,'native_before',lambda store,scene,binding,junction_result=None:unary_union(list(p.operands(store,scene)[1].values())))
 four=finish.finish(store,scene,{},'t04');scene4=store.get_json(four['output_scene_ref'],kind='scene');material4=[r for r in scene4['objects']if r['kind']=='component_remedy']
 assert four['summary']['fills']>0 and len(material4)==1
 sid=material4[0]['source_id'];assert four['fills'][0]['logical_patch_ref']==material4[0]['geometry_ref']
 second_growth=grown.union(box(2.96,1.1,3.04,2));scene4['objects'][0]['geometry_ref']=p.geomref(store,second_growth)
 five=finish.finish(store,scene4,{},'t05');scene5=store.get_json(five['output_scene_ref'],kind='scene');material5=[r for r in scene5['objects']if r['kind']=='component_remedy']
 assert five['summary']['fills']>0 and len(material5)==1
 assert material5[0]['source_id']==sid and material5[0]['original_ref']==material4[0]['original_ref']
 assert p.geometry(store,material5[0]['geometry_ref']).covers(p.geometry(store,material4[0]['geometry_ref']))
 assert five['representation']=='ABSORB_INTO_ORIGINAL_OWNER_SURFACE'

import gzip
import json
from pathlib import Path
import subprocess
import sys

import pytest
from shapely import set_precision, STRtree
from shapely.geometry import box, Point, LineString, Polygon
from shapely.ops import unary_union

from src.shared_copper_context import CopperContext, geometry_key
from src import indexed_polygon_distance as distance


def open_context(tmp_path, values=None, **kwargs):
    return CopperContext(values or dict(a=box(0,0,2,2),b=box(3,0,4,2)),
                         source_binding=dict(source='test-source'), frame=dict(units='mm',axes='X_RIGHT_Y_DOWN'),
                         root=tmp_path/'prepared', **kwargs)


def test_restart_reuses_preparation_and_preserves_source_order(tmp_path):
    with open_context(tmp_path) as c:
        key=c.key; assert c.stats['source_board_unions']==1
        assert c.source.sources(box(-1,-1,5,5))==('a','b')
    with open_context(tmp_path) as c:
        assert c.key==key and c.stats['source_board_unions']==0
        assert c.stats['source_warm_loads']==1 and c.stats['source_index_builds']==1
        assert c.source.sources(box(-1,-1,5,5))==('a','b')
    # A fresh interpreter owns fresh native handles and authenticates disk data.
    code="""from pathlib import Path
from shapely.geometry import box
from src.shared_copper_context import CopperContext
with CopperContext(dict(a=box(0,0,2,2),b=box(3,0,4,2)),source_binding=dict(source='test-source'),frame=dict(units='mm',axes='X_RIGHT_Y_DOWN'),root=Path(__import__('sys').argv[1])) as c:
 print(c.stats['source_warm_loads'],c.stats['source_board_unions'])
"""
    result=subprocess.run([sys.executable,'-B','-c',code,str(tmp_path/'prepared')],capture_output=True,text=True,check=True)
    assert result.stdout.strip()=='1 0'


def test_role_subset_reuses_resident_and_restart_preparation_and_tracks_revision(tmp_path):
    with open_context(tmp_path)as c:
        image=c.prepared_subset(c.source,['a'])
        assert c.prepared_subset(c.source,['a'])is image
        revision=c.acquire(dict(a=box(-2,0,2,2)))
        changed=c.prepared_subset(revision,['a'])
        assert changed.bounds[0]==-2 and image.bounds[0]==0
        assert c.stats['source_subset_unions']==2
        assert c.stats['source_index_builds']==1
        assert c.prepared_subset(c.source,[]).is_empty
    with open_context(tmp_path)as c:
        assert c.prepared_subset(c.source,['a']).equals(box(0,0,2,2))
        assert c.stats['source_subset_warm_loads']==1
        assert c.stats['source_subset_unions']==0


def test_role_subset_corruption_stops_instead_of_rebuilding(tmp_path):
    with open_context(tmp_path)as c:
        c.prepared_subset(c.source,['a']);directory=c.directory
    path=next((directory/'source_subsets').glob('*.json.gz'));path.write_bytes(b'broken')
    with open_context(tmp_path)as c:
        with pytest.raises(ValueError,match='SHARED_COPPER_CORRUPT_ENTRY'):c.prepared_subset(c.source,['a'])
        assert c.stats['source_subset_unions']==0



def test_growth_outside_old_bounds_merge_split_and_reopen(tmp_path):
    with open_context(tmp_path) as c:
        base=c.source
        joined=c.acquire(dict(a=box(0,0,3.5,2)))
        assert len(joined.owners)==1 and len(base.owners)==2
        assert joined.sources(box(2.5,.5,2.8,1))==('a',)
        assert base.sources(box(2.5,.5,2.8,1))==()
        assert joined.membership['a']==joined.membership['b']
        assert joined.changes['a']['added']
        split=c.acquire(dict(a=box(0,0,1,2)),parent=joined)
        assert len(split.owners)==2
        assert split.sources(box(2.5,.5,2.8,1))==()
        assert c.stats['source_index_builds']==1
        assert c.acquire(dict(a=box(0,0,3.5,2))) is joined
    with open_context(tmp_path) as c:
        joined=c.acquire(dict(a=box(0,0,3.5,2)))
        assert c.stats['revision_warm_loads']==1 and c.stats['affected_owner_unions']==0
        assert len(joined.owners)==1


def test_queries_match_fresh_index_after_empty_and_overlap_changes(tmp_path):
    values=dict(a=box(0,0,2,2),alias=box(0,0,2,2),b=box(4,0,5,1))
    with open_context(tmp_path,values) as c:
        rev=c.acquire(dict(a=Polygon(),alias=box(-3,-3,-1,-1),b=box(-2,-2,5,1)))
        assert len(rev.owners)==1
        for window in [box(-4,-4,-1,-1),box(0,0,1,1),box(4,0,5,1),box(10,10,11,11)]:
            expected=tuple(s for s,g in rev.values.items() if g.intersects(window))
            assert rev.sources(window)==expected
        assert c.stats['revision_overlay_index_builds']==1
        assert c.source.values['a'].equals(values['a'])


def test_original_holes_and_touching_ownership_are_preserved(tmp_path):
    donut=box(0,0,6,6).difference(box(2,2,4,4))
    values=dict(fill=donut,inside_hole=box(2.5,2.5,3.5,3.5),touch=box(6,0,7,1))
    with open_context(tmp_path,values) as c:
        assert len(c.source.owners)==2
        assert c.source.membership['fill']==c.source.membership['touch']
        assert c.source.membership['fill']!=c.source.membership['inside_hole']
        assert c.source.image().equals(unary_union(list(values.values())))


def test_owner_closure_accounts_for_one_source_occurrence_in_multiple_owners(tmp_path):
    values=dict(a=box(0,0,2,2),b=box(5,0,7,2),multi=unary_union([box(0,0,1,1),box(5,0,6,1)]))
    with open_context(tmp_path,values) as c:
        revision=c.acquire(dict(a=box(0,0,.5,2)))
        assert len(revision.owners)==2
        assert unary_union(list(revision.owners.values())).equals(revision.image())
        assert len(revision.membership['multi'])==2


def test_changed_order_frame_precision_source_and_kernel_do_not_reuse(tmp_path,monkeypatch):
    with open_context(tmp_path) as c: key=c.key
    with open_context(tmp_path,dict(b=box(3,0,4,2),a=box(0,0,2,2))) as c: assert c.key!=key
    with open_context(tmp_path,dict(a=set_precision(box(0,0,2,2),.001),b=box(3,0,4,2))) as c: assert c.key!=key
    monkeypatch.setattr('shapely.geos_version_string','changed-kernel')
    with open_context(tmp_path) as c: assert c.key!=key


@pytest.mark.parametrize('file',['source.json.gz','geometry'])
def test_corruption_stops_and_retains_bad_bytes(tmp_path,file):
    with open_context(tmp_path) as c: folder=c.directory
    target=folder/file if file!='geometry' else next((folder/'geometry').glob('*.json.gz'))
    target.write_bytes(b'bad-entry')
    with pytest.raises(ValueError,match='CORRUPT_ENTRY'): open_context(tmp_path)
    assert target.read_bytes()==b'bad-entry'


def test_interrupted_publication_does_not_replace_committed_entry(tmp_path):
    with open_context(tmp_path) as c: folder=c.directory
    (folder/'.source.json.gz.interrupted.pending').write_bytes(b'partial')
    with open_context(tmp_path) as c: assert c.stats['source_warm_loads']==1


def test_capacity_and_close_are_explicit(tmp_path):
    with pytest.raises(ValueError,match='CAPACITY_EXCEEDED'): open_context(tmp_path,limit=1)
    with open_context(tmp_path) as c: source=c.source
    with pytest.raises(ValueError,match='CONTEXT_CLOSED'): source.sources(box(0,0,1,1))


@pytest.mark.parametrize('gap',[0,.0401,.040100000001,.2])
def test_t02_t05_exact_distance_and_pinned_boundary_reuse(tmp_path,gap):
    a=Point(0,0).buffer(1,quad_segs=512)
    b=Point(2+gap,0).buffer(1,quad_segs=512)
    distance.clear();expected=distance.distance(a,b)
    with open_context(tmp_path,dict(a=a,b=b)) as c:
        with c.activate():
            distance.clear()
            assert distance.distance(a,b).hex()==expected.hex()
            first=distance.boundary_index(a)
            assert distance.boundary_index(a)[0] is first[0]
            assert c.stats['boundary_index_builds']<=2
    with open_context(tmp_path,dict(a=a,b=b)) as c:
        with c.activate():
            distance.boundary_index(a);assert c.stats['boundary_warm_loads']==1
    distance.clear()


def test_boundary_order_corruption_and_pinned_budget(tmp_path):
    a=Point(0,0).buffer(1,quad_segs=512)
    with open_context(tmp_path,dict(a=a)) as c:
        c.boundary_index(a);folder=c.directory
    path=next((folder/'boundaries').glob('*.json.gz'))
    record=json.loads(gzip.decompress(path.read_bytes()))
    record['value']['ordered_parts'].reverse()
    from src.shared_copper_context import digest,encoded
    record['sha256']=digest(encoded(record['value']))
    path.write_bytes(gzip.compress(encoded(record)))
    with open_context(tmp_path,dict(a=a)) as c:
        with pytest.raises(ValueError,match='BOUNDARY_ORDER_CHANGED'):c.boundary_index(a)


def test_batched_cleanup_matches_legacy_without_per_feature_board_work(tmp_path):
    from src.gerber_u05.source_edge_cleanup import CleanupBatch,legacy_trim_supported_feature
    from src.bulk_edge_restore import fit_straight_flanks
    values=dict(fill=box(0,0,4,4),a=LineString([(-.02,1),(2,1)]).buffer(.0254,quad_segs=128),
                b=LineString([(-.02,3),(2,3)]).buffer(.0254,quad_segs=128))
    rows={s:dict(kind='stroke',metadata={}) for s in values};features=[]
    expected=dict(values)
    for sid,y in [('a',1),('b',3)]:
        domain=box(-.1,y-.2,0,y+.2);edge=LineString([(0,y-.5),(0,y+.5)])
        _,evidence=fit_straight_flanks([(0,y-.5),(0,y-.3)],[(0,y+.3),(0,y+.5)],(.2,y),domain)
        f=dict(causing_id=sid,domain=domain,smooth_edge=edge,reference_evidence=evidence,backing_point=(.2,y))
        features.append(f);expected,_=legacy_trim_supported_feature(rows,expected,values,**f)
    with open_context(tmp_path,values) as c:
        batch=CleanupBatch(rows,values,c.source,features)
        for i in range(2):batch.propose(i)
        assert c.stats['assembled_board_unions']==0 and c.stats['affected_owner_unions']==0
        result,proof=batch.finish()
        assert c.stats['cleanup_batch_board_unions']==1 and c.stats['affected_owner_unions']==1
        assert proof['passed'] and len(proof['records'])==2
        assert all(result.values[s].wkb==g.wkb for s,g in expected.items())


def test_existing_component_and_t02_t05_engine_and_structure_are_shared(tmp_path):
    from src import component_distance
    from src.component_clearance import Context
    a=Point(0,0).buffer(1,quad_segs=9000);b=box(3,0,3.1,.1)
    component_distance.VALUES.clear();distance.clear()
    expected=component_distance.distance(a,b)
    component_distance.VALUES.clear();distance.clear()
    with open_context(tmp_path,dict(a=a,b=b)) as c:
        with c.activate():
            cc=Context(c.source.image(),'test-source',dict(a=a,b=b))
            assert cc.index is c.owner_index
            assert cc.ids=={s:list(v) for s,v in c.source.membership.items()}
            assert component_distance.distance(a,b).hex()==expected.hex()
            engine=distance.measurement_engine()
            tree,_=distance.boundary_index(a)
            assert distance.boundary_index(a)[0] is tree
            assert c.boundary_index(a)[0] is tree
            assert distance.measurement_engine() is engine
            assert len(engine.handles)==1 and c.stats['boundary_index_builds']==1
            adjacency=c.boundary_adjacency(a)
            assert adjacency[0]['previous']==len(adjacency)-1
            assert adjacency[len(adjacency)-1]['next']==0
        assert c.diagnostics()['retained_bytes']<=c.limit
    assert engine.closed and not engine.handles
    component_distance.VALUES.clear();distance.clear()


def test_t02_t05_stage_uses_same_context_without_changing_stage_proof(tmp_path,monkeypatch):
    from src.gerber_u05 import pipeline
    from src.shared_copper_context import ACTIVE
    root=tmp_path/'run';root.mkdir()
    geometries=dict(a=box(0,0,1,1));result=dict(summary=dict(routes=1),output_scene_ref=dict(sha256='unchanged'))
    seen=[]
    monkeypatch.setattr(pipeline,'Store',lambda path:object())
    monkeypatch.setattr(pipeline,'load',lambda path:dict(scene_ref={},source_ref=dict(sha256='a'*64)))
    monkeypatch.setattr(pipeline,'validate_scene',lambda *args:{})
    monkeypatch.setattr(pipeline,'operands',lambda *args:({},geometries,geometries))
    def stage(*args,**kwargs):
        c=ACTIVE.get();assert c is not None;seen.append(c.key);return result
    monkeypatch.setattr(pipeline,'_stage',stage)
    assert pipeline.stage(root,'t02')==result
    assert pipeline.stage(root,'t05')==result
    assert seen[0]==seen[1]


def test_native_plotting_view_reopens_without_substituting_cleanup_vertices(tmp_path):
    from src.original_copper_owners import OriginalOwners
    source=unary_union([Polygon([(0,0),(1,0),(2,0),(2,2),(0,2),(0,0)]),box(3,0,4,2)])
    baseline=OriginalOwners(source)
    with open_context(tmp_path,role='native-stage') as c:
        assert c.owner_index is None  # inactive cleanup representation stays on disk
        native=c.original_owner_index(source)
        assert native.fingerprint==baseline.fingerprint
        assert c.original_memberships(c.source.values,native)==baseline.memberships(c.source.values)
        assert c.original_owner_index(source) is native
    with open_context(tmp_path,role='native-stage') as c:
        native=c.original_owner_index(source)
        assert native.fingerprint==baseline.fingerprint
        assert c.stats['owner_partition_warm_loads']==1
        assert c.stats['owner_partition_membership_checks']==2


def test_altered_native_owner_assignment_rejected_even_with_recomputed_envelope(tmp_path):
    from src.shared_copper_context import digest,encoded
    source=unary_union([Polygon([(0,0),(1,0),(2,0),(2,2),(0,2),(0,0)]),box(3,0,4,2)])
    with open_context(tmp_path,role='native-stage') as c:
        c.original_owner_index(source)
        path=c.directory/'owner_partitions'/(geometry_key(source)+'.json.gz')
    envelope=json.loads(gzip.decompress(path.read_bytes()))
    envelope['value']['membership']['a']=envelope['value']['membership']['b']
    envelope['sha256']=digest(encoded(envelope['value']))
    path.write_bytes(gzip.compress(encoded(envelope)))
    with open_context(tmp_path,role='native-stage') as c:
        with pytest.raises(ValueError,match='OWNER_MEMBERSHIP_CHANGED'):c.original_owner_index(source)

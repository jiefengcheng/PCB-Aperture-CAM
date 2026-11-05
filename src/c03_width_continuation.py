"""Append-only C03 width recovery from the exact qualified U05 candidate.

All predecessor native nodes remain immutable. This adapter checks new complete
exposed source groups in the complete CURRENT native copper context. No old
candidate copper supplies the new width construction; original native source
parameters and the unchanged source-offset kernel do that work.
"""
import json,copy
from pathlib import Path
from collections import defaultdict
import sexpdata
from shapely import from_wkb,to_wkb
from src.stage_abi.store import ArtifactStore,canonical,digest
from src.stage_abi.scene import validate_scene
from src.stage_abi.width import width_parameters
from src.native_inventory import inventory
from src.native_reference import one
from src.pcb_data_abi.board_native import encode
from src.c03_width_recovery import qualify
from src.u03_board.width import WholeBoardWidthAdapter
from src.u05_board.store import ReadOnlyStore


def read(p):return json.loads(Path(p).read_bytes())

def upstream_u05(predecessor):
    p=Path(predecessor).absolute();seen=set()
    while not (p/'U05_RECEIPT.json').is_file():
        if str(p) in seen:raise ValueError('C03_PREDECESSOR_CHAIN_CYCLE')
        seen.add(str(p));r=read(p/'C03_WIDTH_RECOVERY_RECEIPT.json')
        if r['status']!='PASS_APPEND_ONLY_C03_WIDTH_RECOVERY':raise ValueError('C03_QUALIFIED_WIDTH_PREDECESSOR_REQUIRED')
        p=Path(r['retained_predecessor']).absolute()
    return p


class WidthContinuation:
    def __init__(self,predecessor,output):
        self.predecessor=Path(predecessor).absolute();self.out=Path(output).absolute();self.store=ArtifactStore(self.out/'runtime');self.inputs={}
        self.upstream_u05=upstream_u05(self.predecessor);self.width_predecessors=[];p=self.predecessor
        while p!=self.upstream_u05:
            r=self.read(p/'C03_WIDTH_RECOVERY_RECEIPT.json');self.body(p/'checkpoints/014.json',r['checkpoint_sha256']);self.body(r['kicad']);self.width_predecessors.append(p);p=Path(r['retained_predecessor']).absolute()
        u05=self.read(self.upstream_u05/'U05_RECEIPT.json')
        if u05['status']!='PASS_U05_RETAINED_CONTINUATION_EXPORT':raise ValueError('C03_QUALIFIED_U05_REQUIRED')
        self.body(self.upstream_u05/'U05_CHECKPOINT.json',u05['checkpoint_sha256'])
        self.receipt=self.read(self.predecessor/('C03_WIDTH_RECOVERY_RECEIPT.json' if self.width_predecessors else 'U05_RECEIPT.json'));self.receipt_path=self.predecessor/('C03_WIDTH_RECOVERY_RECEIPT.json' if self.width_predecessors else 'U05_RECEIPT.json')
        self.start=self.read(self.upstream_u05/'U05_START.json');self.source_root=Path(self.start['predecessor']['root']);self.source_store=ReadOnlyStore(self.source_root/'runtime')
        self.raw=self.body(self.receipt['kicad']);export=self.read(self.predecessor/'data_output/pcb_gerber_export.json')
        for p,h in export['output_sha256'].items():self.body(p,h)
        self.original_receipt=self.read(self.source_root/'RECEIPT.json');binding=self.source_store.get_json(self.original_receipt['binding_ref'],kind='t01-binding');self.original_raw=self.source_store.get(binding['source_ref'],kind='native-source');self.manifest=self.read(self.source_root/'data_board/source_manifest.json')
        self.original={r['id']:self.body(self.source_root/'data_board/source_wkb'/(r['geometry_sha256']+'.wkb'),r['geometry_sha256']) for r in self.manifest['objects']}
        scene=self.source_store.get_json(self.read(self.source_root/'u02_t03/t03_search.json')['candidate']['output_scene_ref'],kind='scene');self.t01_current={r['source_id']:self.source_store.get(r['geometry_ref'],kind='geometry') for r in scene['objects']};self.selection=self.read(self.source_root/'U03_SELECTION.json')
        self.prior_width=self.read(self.source_root/'u03_t04/t04_run.json')['result']['candidate'];self.prior_factors={s:r['factor']for r in self.prior_width['construction']if r['factor']>1 for s in r['complete_source_ids']};self.replaced_source_ids=set(self.prior_factors);self.prior_part_sha256={s:r['nominal_ref']['sha256']for s,r in self.prior_width['parts'].items()}
        for p in reversed(self.width_predecessors):
            candidate=self.read(p/'operations/width_construct.json')['result']['candidate']
            for r in candidate['construction']:
                if r['factor']<=1:continue
                for s in r['complete_source_ids']:
                    if s in self.prior_factors:raise ValueError('C03_PREDECESSOR_WIDTH_SOURCE_REPEATED')
                    self.prior_factors[s]=r['factor'];self.prior_part_sha256[s]=candidate['parts'][s]['nominal_ref']['sha256']
        self.meta={r['id']:r for r in self.manifest['objects']};self.adapter=WholeBoardWidthAdapter()

    def body(self,p,h=None):
        p=Path(p)
        if p.is_symlink() or not p.is_file():raise ValueError('C03_UNSAFE_RETAINED_INPUT')
        b=p.read_bytes();actual=digest(b)
        if h is not None and actual!=h:raise ValueError('C03_RETAINED_INPUT_CHANGED:'+str(p))
        self.inputs[str(p)]=actual;return b

    def read(self,p):return json.loads(self.body(p))
    def verify_inputs(self):
        if any(digest(Path(p).read_bytes())!=h for p,h in self.inputs.items()):raise ValueError('C03_RETAINED_INPUT_CHANGED_DURING_OPERATION')

    def admission(self):
        report=qualify(self.original_raw,self.manifest['objects'],self.original,self.t01_current,selection=self.selection)
        groups=[];inherited=[]
        runs={p['path_id']:p for p in report['admitted_paths']}
        previous_groups={}
        if self.width_predecessors:
            previous=self.read(self.predecessor/'operations/source_admission.json')['admission']
            previous_groups={m:set(g['members'])for g in previous['groups']for m in g['members']}
        unmet={r['reference_id']for r in report['reference_width_obligations']if r['required_positive'] and any(self.prior_factors.get(s,1.)+1e-12<r['required_factor']for s in r['source_ids'])}
        for g in report['groups']:
            sources={s for m in g['members']for s in runs[m.removeprefix('route:')]['source_ids']}
            split_retry=any(m.removeprefix('route:')in unmet and m in previous_groups and previous_groups[m]!=set(g['members'])for m in g['members']) and not sources.intersection(self.replaced_source_ids)
            if sources.intersection(self.prior_factors)and not split_retry:inherited.append(dict(group=g,disposition='KEEP_COMPLETE_GROUP_WITH_QUALIFIED_PREDECESSOR_WIDTH'))
            else:groups.append(g)
        ids={m.removeprefix('route:')for g in groups for m in g['members']}
        return dict(report,continuation_groups=groups,continuation_paths=[p for p in report['admitted_paths']if p['path_id'] in ids],retained_width_groups=inherited,predecessor_native_sha256=digest(self.raw),prior_width_factors=self.prior_factors,execution='RETAINED_U05_PLUS_NEW_COMPLETE_GROUPS; no predecessor node replacement')

    def model(self,admission):
        if admission['predecessor_native_sha256']!=digest(self.raw):raise ValueError('C03_WIDTH_PREDECESSOR_CHANGED')
        # Freshly enumerate EVERY current native copper source, including T01,
        # T02, the prior width contours and every qualified T05 contour.
        inv=inventory(self.raw);rows=[r for r in inv['objects']if 'F.Cu' in r['layers']]
        if any(r['coverage']!='GEOMETRY_AVAILABLE' or r['kind']not in ('segment','arc','gr_circle','gr_poly') for r in rows):raise ValueError('C03_CURRENT_FCU_CONTEXT_NOT_QUALIFIED')
        bank=defaultdict(list)
        for row in rows:
            fragment=self.raw[slice(*row['source_span'])];key=digest(encode(sexpdata.loads(fragment.decode())).encode());bank[key].append(row)
        source_bindings={};used=set();objects=[];source_ref=self.store.put('native-source',self.original_raw)
        for p in admission['continuation_paths']:
            members=p['source_ids'];core=[]
            for sid in members:
                old=self.meta[sid];node=sexpdata.loads(self.original_raw[slice(*old['source_span'])].decode());key=digest(encode(node).encode());matches=[r for r in bank[key]if r['id']not in used]
                if not matches:raise ValueError('C03_CURRENT_NATIVE_SOURCE_NODE_NOT_UNCHANGED:'+sid)
                match=matches[0];used.add(match['id']);blob=inv['payloads'][match['geometry_sha256']]
                if blob!=self.original[sid]:raise ValueError('C03_CURRENT_NATIVE_SOURCE_COPPER_CHANGED:'+sid)
                source_bindings[sid]=dict(native_id=match['id'],native_span=match['source_span'],original_span=old['source_span'],node_sha256=key,geometry_sha256=match['geometry_sha256'])
                core.append(from_wkb(blob))
            from shapely.ops import unary_union
            cid='route:'+p['path_id'];chain=dict(component_id=cid,source_ids=members,source_sha256=digest(self.original_raw));g=unary_union(core);ref=self.store.put('geometry',to_wkb(g));native=self.store.put_json('native-route',dict(source_ref=source_ref,chain=chain,manifest_rows={s:self.meta[s]for s in members},geometry_refs={s:self.store.put('geometry',self.original[s])for s in members}))
            objects.append(dict(source_id=cid,kind='trace',original_ref=ref,geometry_ref=ref,metadata=dict(native_route_ref=native,nominal_width_mm=p['uniform_original_width_mm'],native_source_ids=members,complete_route_qualification=dict(family=admission['c03_width_family'],admission_sha256=digest(canonical(admission))))))
        for row in rows:
            if row['id'] in used:continue
            ref=self.store.put('geometry',inv['payloads'][row['geometry_sha256']]);objects.append(dict(source_id='retained:'+row['id'],kind='fixed_source',original_ref=ref,geometry_ref=ref,metadata=dict(native_source_ids=[row['id']],nominal_width_mm=float(one(sexpdata.loads(self.raw[slice(*row['source_span'])].decode()),'width',[0])[0]) if row['kind'] in ('segment','arc') else 0.,retained_native_predecessor=True)))
        if len(source_bindings)!=len(used):raise ValueError('C03_CURRENT_NATIVE_ALIAS_PARTITION_CONFLICT')
        if len(used)+sum(r['kind']=='fixed_source'for r in objects)!=len(rows):raise ValueError('C03_CURRENT_NATIVE_CONTEXT_PARTITION_INCOMPLETE')
        scene=dict(source_sha256=digest(self.original_raw),frame='native-kicad-mm',units='mm',layer='F.Cu',viewport_mm=self.selection['bounds_mm'],objects=objects,findings=[],lineage=[dict(stage='retained-qualified-native-width-prefix',receipt_sha256=digest(self.receipt_path.read_bytes()),native_sha256=digest(self.raw))],acceptance=dict(owner='PENDING',independent='NOT_RUN'))
        scene_ref=self.store.put_json('scene',scene);policy=dict(stage='t04',parameters=width_parameters());bounds=dict(max_source_objects=len(objects),max_targets=len(admission['continuation_paths']),max_evaluations=30*len(admission['continuation_groups'])+10,max_output_bytes=12_000_000_000,max_seconds=14400)
        details=self.adapter.plan(self.store,scene,policy,dict(stage='t04',scene_ref=scene_ref,source_ids=['route:'+p['path_id']for p in admission['continuation_paths']],groups=admission['continuation_groups']),bounds)
        plan=dict(stage='t04',scene_ref=scene_ref,policy_ref=self.store.put_json('policy',policy),profile_id='c03-retained-u05-width-recovery-v1',implementation=self.adapter.describe()['implementation'],details=details)
        context=dict(scene_ref=scene_ref,policy=policy,plan=plan,source_bindings=source_bindings,current_native_copper_occurrences=len(rows),current_native_source_partition_complete=True,current_native_source_sha256=digest(self.raw))
        return context

    def run(self,context,checkpoint=lambda x:None):
        scene=validate_scene(self.store,context['scene_ref']);return self.adapter.run(self.store,scene,context['policy'],context['plan'],checkpoint)
    def verify(self,context,candidate):
        scene=validate_scene(self.store,context['scene_ref']);return self.adapter.verify(self.store,scene,context['policy'],context['plan'],candidate,dict(scope='complete-source-nominal-envelope-and-upper-proofs'),lambda x:None)
    def coverage(self,admission,candidate):
        # Earlier contours stay physically present. Appending a lesser contour
        # cannot lower the existing factor; exact node/plot preservation proves
        # this independently at native export. No earlier contour is replaced.
        factors=dict(self.prior_factors)
        for r in candidate['construction']:
            for s in r['complete_source_ids']:factors[s]=max(factors.get(s,1.),r['factor'])
        records=[dict(r,actual_factors={s:factors.get(s,1.)for s in r['source_ids']},met=all(factors.get(s,1.)+1e-12>=r['required_factor']for s in r['source_ids']))for r in admission['reference_width_obligations']]
        positive=[r for r in records if r['required_positive']]
        return dict(records=records,original_positive=len(positive),met=sum(r['met']for r in positive),unmet=sum(not r['met']for r in positive),previous_width_factors_preserved=True,blocked=['T01:C028','T02:R304','T02:R305'],full_original_recovery='NOT_ESTABLISHED')

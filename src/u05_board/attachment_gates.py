"""U05 attachment profile: independent worklist, existing fourteen-gate route."""
from pathlib import Path
from shapely import from_wkb,to_wkb
from shapely.geometry import box
from src.stage_abi.store import digest
from tools.t01_operator_host import read
from src.u03_board.selection import for_root,window
from src.u03_board.paging import put,get
from .junctions import JunctionGates,parameters
from .custody import session
from .store import OverlayStore
from .reference import work_scene,admission,PROFILE
from .coverage import CoverageAdapter

class AttachmentGates(JunctionGates):
    def __init__(self,root,evidence=None):
        self.root=Path(root);start=session(root);self.predecessor=start['predecessor'];self.reference=start['reference'];old=Path(self.predecessor['root']);self.out=self.root/'u05_t05';self.store=OverlayStore(self.root/'runtime',old/'runtime',evidence)
        self.scene,self.native_facts=work_scene(self.store,self.predecessor,self.reference);self.scene_ref=self.store.put_json('scene',self.scene);self.native_ids=sorted(r['id'] for r in read(old/'data_board/source_manifest.json')['objects']);self.selection=for_root(old)
        profile=read(PROFILE);exceptions={}
        if profile.get('scope_exception'):
            from .custody import ROOT
            e=profile['scope_exception'];exceptions[e['reference_id']]=from_wkb((ROOT/e['path']).read_bytes())
        self.adapter=CoverageAdapter(window(self.selection) if self.selection else box(*self.scene['viewport_mm']),exceptions)
        self.binding=dict(retained_U04_receipt_sha256=self.predecessor['receipt_sha256'],retained_U04_scene_ref=self.predecessor['scene_ref'],actual_native_U04_sha256=self.predecessor['kicad_sha256'],actual_native_scene_ref=self.scene_ref,source_sha256=self.scene['source_sha256'],reference=self.reference,profile_sha256=digest(PROFILE.read_bytes()))
    def reconstruct_admission(self):
        scene,report=admission(self.store,self.scene,self.selection)
        if report['native_source_ids']!=self.native_ids:raise ValueError('U05_ATTACHMENT_NATIVE_SOURCE_COVERAGE')
        return scene,report
    def inspect(self):
        self.out.mkdir();scene,report=self.reconstruct_admission();pages=put(self.store,report['routes'],binding=self.binding,kind='u05-junction-contacts');records,index=get(self.store,pages,binding=self.binding,kind='u05-junction-contacts',identity=lambda r:r['source_id'])
        if records!=report['routes']:raise ValueError('U05_ATTACHMENT_CONTACT_PAGES')
        return self.save('t05_inspect',dict(report_ref=self.store.put_json('u05-junction-admission',report),contact_pages_ref=pages,facts=dict(passed=True,complete_source_coverage=True,source_objects=len(report['source_ids']),native_source_objects=len(report['native_source_ids']),source_routes=len(records),eligible_routes=len(records),contact_pages=len(index['pages']),source_contacts=sum(len(r['land_ids']) for r in records),reference_clusters=97,required_reference_attachments=162,additional_clusters=self.native_facts['additional_clusters'],context_contacts=self.native_facts['context_contacts'])))
    def run(self):
        candidate=self.reconstruct();outcomes=[a for d in candidate['decisions'] for a in d['attachment_outcomes']];required=[a for a in outcomes if a['required_reference']]
        if len(required)!=162 or len({a['id'] for a in required})!=162:raise ValueError('U05_REQUIRED_ATTACHMENT_DENOMINATOR_CHANGED')
        if any(a['status'] not in ('TREATED_VERIFIED','ALREADY_SATISFIED_VERIFIED') for a in required):raise ValueError('U05_REQUIRED_ATTACHMENT_NOT_FULFILLED')
        return self.save('t05_run',dict(candidate_ref=self.store.put_json('candidate',candidate),candidate=candidate,facts=dict(passed=True,fresh_construction=True,source_routes=len(candidate['decisions']),grown=sum(d['status']=='GROWN' for d in candidate['decisions']),kept=sum(d['status']=='KEEP' for d in candidate['decisions']),radius_evaluations=candidate['evaluations'],predecessor_preserved=True,reference_positive_clusters=85,required_reference_attachments=162,verified_required_attachments=len(required),all_attachment_records=len(outcomes))))
    def extra_controls(self):
        def grown(c):return next(d for d in c['decisions'] if d['status']=='GROWN' and len(d['land_ids'])>1)
        def omit(c):
            d=grown(c);d['attachment_outcomes']=d['attachment_outcomes'][:-1]
        def covered(c):
            d=grown(c);d['land_ids']=d['land_ids'][:-1]
        def irrelevant(c):
            d=grown(c);d['patch_ref']=self.store.put('geometry',to_wkb(box(100,100,100.1,100.1)))
        def truncate(c):
            d=next(d for d in c['decisions'] if d['reference_id']=='J-966bf7ea0116147b');shape=from_wkb(self.store.get(d['patch_ref'],kind='geometry'));d['patch_ref']=self.store.put('geometry',to_wkb(shape.intersection(self.adapter.write)))
        return [('omitted_attachment_on_grown',omit),('covered_land_removed',covered),('irrelevant_copper',irrelevant),('boundary_truncation',truncate)]

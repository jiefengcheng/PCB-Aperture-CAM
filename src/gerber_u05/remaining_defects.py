"""Whole-board actual-file inventory of remaining eligible internal remedies."""
import sys,json,collections
from pathlib import Path
from . import exporter as e
p=e.p;run=Path(sys.argv[1])
from src import component_clearance as cc
from src.component_voids import plan,parts
from .component_policy import read_job
from .native_component_checks_final import decoded_groups
p.configure();
from .guard import install_read_fence
install_read_fence(run.parent);e.verify_sources(run);store,binding=e.context(run);proofs=[p.load(run/'export'/('proof_'+m+'.json'))for m in('1','2')]
if p.canonical(proofs[0])!=p.canonical(proofs[1])or proofs[0]['status']!='PASS':raise ValueError('PAIRED_NATIVE_PROOFS_REQUIRED')
body=(run/'export/top.art.gbr').read_bytes();parsed=e.parse(body);ledger=p.load(run/'export/ledger.json');n=binding['source_objects'];observed={}
if p.digest(body)!=proofs[0]['generated_sha256']or len(parsed.objects)!=n+proofs[0]['appended_positive_regions']:raise ValueError('NATIVE_AUDITED_MATERIAL_BYTES_CHANGED')
if any(not obj.polarity_dark or not isinstance(obj,p.go.Region)for obj in parsed.objects[n:]):raise ValueError('NATIVE_AUDITED_APPEND_ROLE_CHANGED')
for row in proofs[0]['native_material_assembly']['material_parents']:observed.setdefault(row['source_id'],[]).append(p.geometry(store,row['geometry_ref']))
groups=decoded_groups(cc.ACTIVE.index.source,observed);current=cc.joined(groups.values());source=cc.ACTIVE.index.source;_,contracts=read_job(run);reports=[];eligible=[]
source_parts=parts(source);reservations={i:cc.ACTIVE.reserved[cc.ACTIVE.index.membership(g)[0]]for i,g in enumerate(source_parts)}
for contract in contracts:
 report,fills,_=plan(source,current,contract,reserved=reservations,checkpoint=lambda r:print(json.dumps(dict(radius_mm=contract.notch_radius_mm,**r)),flush=True)if r['component']%32==0 else None)
 counts=dict(collections.Counter(r['status']for r in report['records']));reports.append(dict(radius_mm=contract.notch_radius_mm,status_counts=counts,plan=report));eligible.extend(dict(radius_mm=contract.notch_radius_mm,kind=f['kind'],bounds_mm=list(f['geometry'].bounds),area_mm2=f['geometry'].area)for f in fills)
result=dict(status='PASS'if not eligible else'FAIL_REMAINING_ELIGIBLE_DEFECTS',generated_sha256=p.digest(body),eligible=eligible,radii=reports,source_voids='Preserved; source holes and inherited notches are not growth defects',true_foreign_clearance='Preserved with actual frozen original-owner witnesses',integration='NOT_INTEGRATED')
p.save(run/'REMAINING_DEFECT_AUDIT.json',result);print(json.dumps(dict(status=result['status'],eligible=len(eligible))),flush=True)
if eligible:raise ValueError('REMAINING_ELIGIBLE_INTERNAL_DEFECTS:'+str(len(eligible)))

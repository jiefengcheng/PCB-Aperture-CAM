"""Deliver only checked selected artwork and its final parsed-file rendering."""
import datetime
from pathlib import Path
from . import pipeline as p
from .guard import verify_sources

def deliver(run):
 from .source_assembly import verify_run
 assembly=verify_run(run)
 if assembly is None:raise ValueError('CLIENT_OUTER_ENCLOSURE_ASSEMBLY_REQUIRED_FOR_DELIVERY')
 verify_sources(run);proofs=[p.load(run/'export'/('proof_'+m+'.json'))for m in('1','2')]
 body=(run/'export/top.art.gbr').read_bytes();image=run/'visual/corrected_growth.png';render=p.load(run/'visual/RECEIPT.json');inventory=p.load(run/'input_inventory.json')
 if p.canonical(proofs[0])!=p.canonical(proofs[1])or proofs[0]['status']!='PASS'or p.digest(body)!=proofs[0]['generated_sha256']:raise ValueError('DELIVERY_NATIVE_PROOFS_CHANGED')
 for path in('negative_controls/RESULT.json','REMAINING_DEFECT_AUDIT.json'):
  check=p.load(run/path)
  if check['status']!='PASS'or check['generated_sha256']!=p.digest(body):raise ValueError('DELIVERY_CHECKS_CHANGED:'+path)
 if render['generated_sha256']!=p.digest(body)or not any(Path(row['path'])==image and row['sha256']==p.digest(image.read_bytes())for row in render['files']):raise ValueError('FINAL_PARSED_RENDER_CHANGED')
 from src.pcb_data_abi.input_directory import collect_raw
 root,blobs,ignored=collect_raw(inventory['input_directory'])
 if {n:p.digest(b)for n,b in blobs.items()}!=inventory['files']or ignored!=inventory['ignored']:raise ValueError('SOURCE_INPUT_CUSTODY_CHANGED')
 stamp=datetime.datetime.now(datetime.UTC).strftime('%Y%m%dT%H%M%S%fZ');out=root.with_name(root.name+'_U05_040mm_'+stamp);out.mkdir()
 target=out/inventory['selected'];target.write_bytes(body);picture=out/'final_render.png';picture.write_bytes(image.read_bytes())
 if set(v.name for v in out.iterdir())!={target.name,picture.name}or target.read_bytes()!=body or picture.read_bytes()!=image.read_bytes():raise ValueError('DELIVERY_COPY_VERIFICATION_FAILED')
 receipt=dict(status='CHECKED_FILES_DELIVERED',directory=str(out),gerber=str(target),render=str(picture),gerber_sha256=p.digest(body),render_sha256=p.digest(picture.read_bytes()),source_sha256=p.load(run/'source.json')['source_ref']['sha256'],companions_copied=0,owner='PENDING_USER',independent='NOT_RUN',electrical_manufacturing='NOT_ESTABLISHED',custody_finding='.DS_Store: prior FAIL EXPLICIT_UNWAIVED_UNATTRIBUTED')
 receipt['source_assembly']=assembly
 p.save(run/'DELIVERY.json',receipt);return receipt

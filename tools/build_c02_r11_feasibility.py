#!/usr/bin/env python3
"""Read-only R11 fixed-center rectangle-domain infeasibility packet."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import json,csv,math,hashlib,shutil,html
from xml.etree import ElementTree as ET
from shapely import from_wkb,to_wkb
from shapely.geometry import Point,box
from shapely.ops import nearest_points
from shapely.affinity import scale
from src.crop_circle_sources import path_for
from src.crop_stage_growth import GrowthScene,GrowthContract,check_proposal
from src.native_inventory import geometry
from sexpdata import loads

BASE=ROOT/'out/crop_dynamic_tasks';PRE=BASE/'c02_valid_stage_growth_20261028_02'
OUT=BASE/'c02_r11_feasibility_20261028_03'
ZIP=BASE/'C02-VALID-STAGE-FOCUSED-GROWTH-20261028-REV02.zip'
ZIP_SHA='f324c021c147c9d5f14d63f38542520b0bc35cbf6fc7169d6edb168df0e810f2'
sha=lambda b:hashlib.sha256(b).hexdigest()
def save(p,d):p.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')

def main():
 if OUT.exists():raise ValueError('FRESH_OUTPUT_REQUIRED')
 if sha(ZIP.read_bytes())!=ZIP_SHA:raise ValueError('PREDECESSOR_ARCHIVE_HASH_MISMATCH')
 OUT.mkdir();(OUT/'inputs').mkdir();(OUT/'visuals').mkdir();(OUT/'implementation').mkdir()
 raw=(PRE/'inputs/ORG_source.kicad_pcb').read_bytes()
 manifest=json.loads((PRE/'inputs/source_manifest.json').read_text());rows={r['id']:r for r in manifest['objects']}
 d=next(r for r in json.loads((PRE/'t02/decisions.json').read_text()) if r['key']=='R11')
 sid=d['source_id'];tid=manifest['source_sha256']+':bytes:1492399:1492516'
 geoms={}
 for role,identity in [('R11',sid),('fixed_trace',tid)]:
  row=rows[identity];blob=(PRE/'inputs/source_wkb'/f"{row['geometry_sha256']}.wkb").read_bytes()
  assert sha(blob)==row['geometry_sha256']
  span=raw[slice(*row['source_span'])];fresh=geometry(loads(span.decode()),row['kind'])
  assert sha(to_wkb(fresh,byte_order=1))==sha(blob)
  (OUT/f'inputs/{role}.wkb').write_bytes(blob);(OUT/f'inputs/{role}.source').write_bytes(span)
  geoms[role]=from_wkb(blob)
 core=geoms['R11'];trace=geoms['fixed_trace'];q,p=nearest_points(core,trace)
 x0,y0,x1,y1=core.bounds;w=x1-x0;h=y1-y0;a=p.x-q.x;b=q.y-p.y;gap=core.distance(trace)
 assert q.distance(Point(x1,y0))<1e-12 and a>0 and b>0 and abs(math.hypot(a,b)-gap)<1e-12
 assert gap<.020
 c=GrowthContract();epsilon=c.comparison_epsilon_mm;amin=1e-10
 umax=.25*w/2;vmax=.25*h/2
 area_bound_coefficient=max(2*h+4*vmax,2*w)
 uplusv_lower_bound=amin/area_bound_coefficient
 gap_reduction_lower_bound=min(a,b)*min(uplusv_lower_bound,min(a,b))/(2*gap)
 assert gap_reduction_lower_bound>epsilon
 probes=[]
 for fx in [1,1.000001,1.001,1.01,1.10,1.25]:
  for fy in [1,1.000001,1.001,1.01,1.10,1.25]:
   if fx==fy==1:continue
   proposal=scale(core,fx,fy,origin=core.centroid)
   actual=proposal.distance(trace)
   probes.append({'factor_x':fx,'factor_y':fy,'gap_mm':actual,'worsens_original':actual+epsilon<gap})
 assert all(r['worsens_original'] for r in probes)
 with (OUT/'diagnostic_probes.csv').open('w',newline='') as f:
  out=csv.DictWriter(f,fieldnames=list(probes[0]));out.writeheader();out.writerows(probes)
 bindings={'predecessor_archive_sha256':ZIP_SHA,'source_sha256':sha(raw),
  'source_manifest_sha256':sha((PRE/'inputs/source_manifest.json').read_bytes()),'source_object_count':len(rows),
  'fixed_T01_cumulative_sha256':sha((PRE/'t01/cumulative.wkb').read_bytes()),
  'fixed_T01_circle_candidate_sha256':sha((PRE/'t01/candidate.wkb').read_bytes()),
  'fixed_current_cumulative_T01_T02_sha256':sha((PRE/'t02/cumulative.wkb').read_bytes()),
  'R11_source_id':sid,'R11_wkb_sha256':rows[sid]['geometry_sha256'],'R11_span':rows[sid]['source_span'],
  'trace_source_id':tid,'trace_wkb_sha256':rows[tid]['geometry_sha256'],'trace_span':rows[tid]['source_span'],
  'trace_is_not_a_replacement':tid not in [x['source_id'] for x in json.loads((PRE/'t02/decisions.json').read_text())],
  'source_context_dependency':'Complete 17,849-object bank and all fixed replacements in the already retained REV02 archive; this packet does not duplicate the bank.'}
 report={'packet':'C02-R11-READ-ONLY-FEASIBILITY-20261028-REV03','classification':'NO_FEASIBLE_GROWTH_WITHIN_DECLARED_DOMAIN',
  'bindings':bindings,'domain':{'shape':'axis-aligned complete rectangle','center':'fixed at original centroid',
     'source_core':'fully retained','axis_factor_x':[1,1.25],'axis_factor_y':[1,1.25],
     'positive_growth_objective_area_threshold_mm2':amin,'trace_and_all_other_copper':'immutable'},
  'witness':{'rectangle_corner_mm':[q.x,q.y],'fixed_trace_point_mm':[p.x,p.y],
      'outward_x_mm':a,'outward_negative_y_mm':b,'original_gap_mm':gap,
      'source_width_mm':w,'source_height_mm':h,'raw_fragment_reconstruction_hashes_match':True},
  'proof':{'candidate_outward_displacements':'u=(factor_x-1)*W/2 >=0, v=(factor_y-1)*H/2 >=0',
     'contained_witness_point':'q* = (q.x + min(u,a), q.y - min(v,b)) is inside every candidate rectangle',
     'squared_distance_to_fixed_trace_point':'(a-min(u,a))^2 + (b-min(v,b))^2',
     'strict_decrease':'Because a,b > 0, this is strictly smaller than a^2+b^2 whenever u or v is positive.',
     'full_domain_coverage':'Every allowed positive centered nonshrinking rectangle contains a point strictly closer to the unchanged trace than the original minimum gap. Additional fixed obstacles cannot restore feasibility.',
     'area_addition_formula':'2*H*u + 2*W*v + 4*u*v',
     'area_upper_bound_coefficient_mm':area_bound_coefficient,
     'u_plus_v_lower_bound_for_completed_objective_mm':uplusv_lower_bound,
     'gap_reduction_lower_bound_for_completed_objective_mm':gap_reduction_lower_bound,
     'comparison_epsilon_mm':epsilon,
     'numerical_objective_coverage':'The conservative decrease bound for objective-sized growth exceeds comparison epsilon, so numerical tolerance does not create a completed-growth loophole.'},
  'probe_count':len(probes),'all_diagnostic_probes_worsen_gap':True,
  'disposition':{'R11':'KEEP_EXACT_SOURCE; POSITIVE_GROWTH_OBJECTIVE_NOT_COMPLETED',
      'new_geometry_committed':False,'T02_freeze_status':'NOT_FROZEN_PENDING_DISPOSITION_DECISION',
      'downstream_repair_obligation_from_R11_rejected_growth':'NONE',
      'scope_change_enacted':False,
      'scope_option':'An explicit decision could exclude the unmet positive-growth objective while retaining R11 exact source and NOT_COMPLETED. This packet does not enact that decision or count KEEP as growth success.'},
  'limits':['No global impossibility outside the fixed-center axis-aligned nonshrinking domain.',
     'No new accepted geometry, trace change, other rectangle change, native export, T03/T04, electrical recovery or ledger edit.',
     'Proof is for the hash-bound polygonal F.Cu geometry representation; no electrical/manufacturing claim.']}
 save(OUT/'R11_FEASIBILITY.json',report)
 for src,dest in [('inputs/ORG_source.kicad_pcb','ORG_source.kicad_pcb'),('t01/cumulative.wkb','fixed_T01_cumulative.wkb'),('t02/cumulative.wkb','fixed_cumulative_T01_T02.wkb')]:shutil.copyfile(PRE/src,OUT/'inputs'/dest)
 shutil.copyfile(PRE/'AUDIT_RESULT_REV02.md',OUT/'PREDECESSOR_AUDIT.md')
 shutil.copyfile(ROOT/'tools/build_c02_r11_feasibility.py',OUT/'implementation/build_c02_r11_feasibility.py')
 # Full C02 is the primary panel; a geometry-derived neighborhood is supplemental.
 ns={'s':'http://www.w3.org/2000/svg'};ET.register_namespace('',ns['s'])
 full=ET.fromstring((PRE/'t02/full_crop.svg').read_text());full.set('x','0');full.set('y','100')
 localbounds=(q.x-.24,q.y-.24,q.x+.24,q.y+.24);scene=from_wkb((OUT/'inputs/fixed_cumulative_T01_T02.wkb').read_bytes())
 pieces=[f'<path d="{path_for(scene.intersection(box(*localbounds)))}" fill="#ed4260" fill-rule="evenodd"/>',
  f'<path d="{path_for(core)}" fill="none" stroke="#ffd94b" stroke-width=".003"/>',
  f'<line x1="{q.x}" y1="{q.y}" x2="{p.x}" y2="{p.y}" stroke="#61e3cf" stroke-width=".002"/>']
 svg='<svg xmlns="http://www.w3.org/2000/svg" width="2420" height="1780" viewBox="0 0 2420 1780"><rect width="2420" height="1780" fill="#edf3f7"/><text x="40" y="52" font-family="Arial" font-size="30" fill="#142a3f">C02 / R11 — read-only feasibility, fixed-center rectangle growth</text>'
 svg+=ET.tostring(full,encoding='unicode')
 svg+='<text x="1840" y="148" font-family="Arial" font-size="23" fill="#142a3f">Exact R11 source neighborhood</text>'
 svg+=f'<svg x="1840" y="180" width="540" height="540" viewBox="{localbounds[0]} {localbounds[1]} .48 .48"><rect x="{localbounds[0]}" y="{localbounds[1]}" width=".48" height=".48" fill="#071621"/>{"".join(pieces)}</svg>'
 lines=['Gold: exact original R11 boundary.','Teal: exact nearest surface witness.',f'Original gap: {gap*1000:.6f} µm.',f'Outward X distance: {a*1000:.6f} µm.',f'Outward −Y distance: {b*1000:.6f} µm.','Both are positive: centered growth','on either axis approaches the trace.','','Domain: fixed center, complete rectangle,','1 ≤ factor X,Y ≤ 1.25; no shrink.','A clipped outward corner point is','inside every enlarged rectangle and','strictly closer to the fixed trace point.','','NO FEASIBLE POSITIVE GROWTH','within this declared domain.','R11 = exact KEEP / NOT_COMPLETED.','No global impossibility claim.','No later-stage repair obligation.']
 for i,line in enumerate(lines):svg+=f'<text x="1840" y="{770+i*35}" font-family="Arial" font-size="22" fill="#243b50">{html.escape(line)}</text>'
 svg+='<text x="40" y="1730" font-family="Arial" font-size="21" fill="#243b50">Read-only evidence: ORG, fixed T01, current cumulative scene and trace widths unchanged. T02 freeze disposition remains separate. T03/T04 NOT_RUN.</text></svg>'
 (OUT/'visuals/full_c02_and_R11_witness.svg').write_text(svg)
 (OUT/'README.md').write_text('''# R11 bounded completion-feasibility / REV03\n\nRead-only follow-up admitted by the REV02 audit. `R11_FEASIBILITY.json` defines and proves the fixed-center, axis-aligned, complete-rectangle, nonshrinking [1,1.25]² domain. It does not claim impossibility for shifts, asymmetric growth, rotation, other policies or modified obstacles. No new accepted geometry is generated.\n\nThe exact original rectangle corner and fixed trace witness have outward separation in both axes. Every positive centered enlargement contains a point closer to that same fixed trace point, so it worsens the already-subminimum original gap. The objective-sized-growth lower bound exceeds the comparison epsilon. Thirty-five finite probes are diagnostic only; the continuous-domain argument provides the coverage.\n\nAll context is bound to the already audited REV02 archive, source-bank manifest, fixed T01 and fixed cumulative scene. The original source and exact pair fragments/WKB are bundled here. Fresh native-fragment reconstruction matches both pair WKB hashes. A single immutable blocking witness suffices to rule out this domain; the other fixed 17,847 source objects cannot make it feasible.\n\nR11 remains exact KEEP and NOT_COMPLETED. No downstream repair obligation, scope exclusion, freeze, trace edit, other rectangle edit, T03/T04, native export or ledger change is enacted. An explicit scope decision could decline this positive-growth objective without false completion credit, but that is separate from the proof. The full C02 image remains primary; the actual local neighborhood is supplemental.\n''')
 print(json.dumps({'out':str(OUT),'classification':report['classification'],'probe_count':len(probes),'gap_reduction_lower_bound_mm':gap_reduction_lower_bound}))
if __name__=='__main__':main()

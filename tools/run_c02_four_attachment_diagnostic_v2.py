#!/usr/bin/env python3
"""Versioned replay: exact REV05 geometry and two pinned binding representations.

Original strict runner is preserved. Candidate construction/checking below is
retained verbatim except for the explicit source-binding call and evidence.
"""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import argparse, hashlib, json, shutil, subprocess
from dataclasses import asdict
from shapely import from_wkb,to_wkb
from shapely.affinity import scale
from shapely.geometry import box,Point
from src.crop_attachment_diagnostic import bind_circle_attachment,bind_overlapping_feed_attachment,check_attachment_diagnostic
from src.crop_stage_growth import GrowthContract,check_proposal,original_attachment_port
from tools.run_c02_r080_attachment_revision import compute as compute_r080

SITES=('R003','R005','R006','R012')
SOURCE_SPANS={'R003':('1650795:1650921',None),'R005':('1651778:1651902',None),
              'R006':('1652641:1652766',None),'R012':('408354:408443','408262:408351')}


def sha(data):return hashlib.sha256(data).hexdigest()


from dataclasses import replace
from src.crop_pinned_circle_binding import PINS, bind_pinned_circle


def bind_to_authoritative_scene(raw, binding, scene):
    evidence = []
    for role, sid, blob in [('target', binding.target_id, binding.target_wkb),
                            ('obstacle', binding.obstacle_id, binding.obstacle_wkb),
                            ('feed', binding.feed_id, binding.feed_wkb)]:
        if sid is None:
            continue
        cached = to_wkb(scene.objects[sid]['geometry'])
        if role == 'obstacle' and sid in PINS:
            kept, row = bind_pinned_circle(raw, sid, cached)
            assert kept == cached
            assert row['reconstructed_wkb_sha256'] == sha(blob)
            binding = replace(binding, obstacle_wkb=kept)
        else:
            if blob != cached:
                raise ValueError('UNPINNED_SOURCE_BINDING_NOT_EXACT')
            row = dict(status='CANONICAL_EXACT', source_id=sid,
                       reconstructed_wkb_sha256=sha(blob), authoritative_wkb_sha256=sha(cached),
                       geometry_authority='EXACT_REV05_CACHED_WKB_ONLY', acceptance='NONE')
        evidence.append(dict(role=role, **row))
    return binding, evidence


def compute(predecessor):
    p=Path(predecessor)
    _,base=compute_r080(p)  # unchanged accepted R080 replay, never rectangle search
    scene=base['scene'];raw=base['source'];prefix=sha(raw)+':bytes:'
    contract=GrowthContract();crop=box(*base['bounds'])
    decisions={d['key']:d for d in json.loads((p/'t02/decisions.json').read_text())}
    fixed={sid:sha(to_wkb(g)) for sid,g in scene.replacements.items()}
    bindings={};proposals={};reports=[];binding_evidence=[]
    before=base['after'];after=before
    for site in SITES:
        d=decisions[site];sid=d['source_id'];ob,feed=SOURCE_SPANS[site]
        binding=(bind_circle_attachment(raw,sid,prefix+ob) if feed is None else
                 bind_overlapping_feed_attachment(raw,sid,prefix+ob,prefix+feed))
        binding, evidence = bind_to_authoritative_scene(raw, binding, scene)
        binding_evidence.extend(evidence)
        bindings[sid]=binding
        core=scene.objects[sid]['geometry'];cap=scale(core,1.25,1.25,origin=core.centroid)
        assert sha(binding.target_wkb)==sha(to_wkb(core))
        assert sha(binding.obstacle_wkb)==sha(to_wkb(scene.objects[binding.obstacle_id]['geometry']))
        if feed is not None:assert sha(binding.feed_wkb)==sha(to_wkb(scene.objects[binding.feed_id]['geometry']))
        neighbors=scene.neighbors(sid,cap)
        checks=[]
        for name,factors in [('FULL_CAP',(1.25,1.25)),('X',(1.001,1.0)),('Y',(1.0,1.001))]:
            proposal=scale(core,*factors,origin=core.centroid)
            q=check_attachment_diagnostic(core,proposal,neighbors,binding,crop=crop,cap=cap,contract=contract)
            ordinary=check_proposal(core,proposal,neighbors,crop=crop,cap=cap,contract=contract)
            saved=d['full_1p25_cap_check'] if name=='FULL_CAP' else d['next_axis_increment_diagnostics'][name]
            checks.append(dict(name=name,axis_factors_xy=list(factors),proposal_sha256=sha(to_wkb(proposal)),
                               saved_REV05_check=saved,current_full_context_ordinary_check=ordinary,diagnostic_check=q))
        selected=next(q for q in checks if q['name']=='X')
        assert selected['diagnostic_check']['passed'],(site,selected)
        assert not checks[0]['diagnostic_check']['passed'],(site,'FULL_CAP_MUST_REMAIN_REJECTED')
        proposal=scale(core,1.001,1.,origin=core.centroid)
        exposed=proposal.difference(before)
        assert exposed.area>1e-10
        after=after.union(proposal.difference(core))
        proposals[sid]=proposal
        # Same original finite port as previously used for the source attachment.
        port=original_attachment_port(core,from_wkb(binding.obstacle_wkb) if feed is None else from_wkb(binding.feed_wkb),binding.width_mm,contract)
        original_port_neighbor=binding.obstacle_id if feed is None else binding.feed_id
        old_port=next(q for q in selected['current_full_context_ordinary_check']['pairs'] if q['neighbor_id']==original_port_neighbor)
        assert port.area==old_port['attachment_port_area_mm2']
        reports.append(dict(site=site,source_id=sid,obstacle_source_id=binding.obstacle_id,
            feed_source_id=binding.feed_id,mode=binding.mode,original_fragments_sha256=list(binding.fragments_sha256),
            source_sha256=binding.source_sha256,axis_factors_xy=[1.001,1.0],fixed_witness_basis='Retained isolated +0.001 X factor probe; no new search.',
            new_exposed_copper_mm2=exposed.area,target_added_area_mm2=proposal.difference(core).area,
            zoom_center_mm=list(exposed.representative_point().coords[0]),
            original_port_unchanged=True,port_wkb_sha256=sha(to_wkb(port)),probes=checks,
            status='PROPOSED_POSITIVE_GROWTH_PENDING_AUDIT'))
    for sid,g in proposals.items():scene.accept(sid,g)
    final=[]
    circle=json.loads((p/'t01/decision.json').read_text());cg=scene.replacements[circle['source_id']]
    center=tuple(cg.centroid.coords[0])
    for sid,g in sorted(scene.replacements.items()):
        core=scene.objects[sid]['geometry'];is_circle=sid==circle['source_id']
        cap=(Point(*center).buffer(1.5*circle['original_radius_mm'],quad_segs=128) if is_circle else scale(core,1.25,1.25,origin=core.centroid))
        neighbors=scene.neighbors(sid,cap,circle['aliases'] if is_circle else ())
        q=(check_attachment_diagnostic(core,g,neighbors,bindings[sid],crop=crop,cap=cap,contract=contract) if sid in bindings else
           check_proposal(core,g,neighbors,crop=crop,cap=cap,contract=contract,
               attachment_supports=[base['support']] if sid==base['support'].target_id else ()))
        assert q['passed'],(sid,q)
        final.append(dict(source_id=sid,check=q))
        if sid not in proposals:assert fixed[sid]==sha(to_wkb(g))
    assert before.difference(after).area<=1e-12
    report=dict(schema='four-attachment-fixed-diagnostic/1',source_sha256=sha(raw),contract=asdict(contract),
                predecessor='REV05 + REV08-qualified R080 WKB',predecessor_sha256=sha(to_wkb(before)),
                cumulative_sha256=sha(to_wkb(after)),new_exposed_area_mm2=after.difference(before).area,
                original_or_predecessor_copper_removed_mm2=before.difference(after).area,
                fixed_other_replacements=71,all_final_replacement_checks=75,all_final_checks='PASS_DIAGNOSTIC_MODEL_SPACE',
                previously_qualified_growth_witnesses=70,additional_proposed_witnesses=4,
                accepted_completion_count_unchanged=70,selected_denominator=74,status='PROPOSED_POSITIVE_GROWTH_PENDING_AUDIT',
                freeze_status='NOT_FROZEN',production_checker_changed=False,trace_geometry_or_width_changed=False,
                historical_ledger_changed=False,t03='DEFERRED_PENDING_FINAL_VALID_PREDECESSOR',t04='NOT_RUN',sites=reports,
                limitations=['Diagnostic visible-surface classification requires separate audit; not production acceptance.',
                    'Circle source geometry and its visible surface outside unchanged original ports are preserved.',
                    'Only the original finite ports qualify; no net/component exemptions, no new search.',
                    'No native export, electrical intent or manufacturing claim.'])
    return report,dict(base=base,before=before,after=after,exposed=after.difference(before),proposals=proposals,
                       bindings=bindings,scene=scene,final=final,decisions=decisions,source_binding_evidence=binding_evidence)


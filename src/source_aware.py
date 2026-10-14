"""Separate source-aware decision over hash-bound completion evidence.
No parser, tolerances, or original decision is modified.
"""
import json

def terminal_identity(t):
    return (t.get("source_id"), t.get("pin"), tuple(t.get("layers",[])), tuple(t.get("center_mm",[])))

def electrical_status(terminals, observed):
    """Unknown assignments never establish electrical acceptance (fixture agnostic)."""
    if not terminals or any(not t.get('net') for t in terminals):
        return 'NOT_ESTABLISHED'
    return observed if observed in ('PASS','FAIL','NOT_ESTABLISHED','NOT_RUN') else 'NOT_ESTABLISHED'

def evaluate(report, manifest):
    checks={}
    checks['regressions']=report.get('regressions',{}).get('status')=='PASS'
    checks['FC1']=report.get('raw_parser_to_fc1',{}).get('status')=='PASS'
    checks['history']=report.get('historical_evidence_integrity',{}).get('status')=='PASS'
    checks['original_matrix']=report.get('required_matrix_integrity')=='PASS'
    checks['fixture_set']=set(report.get('boards',{}))==set(manifest['fixtures'])
    electrical={}
    for name,rule in manifest['fixtures'].items():
        b=report.get('boards',{}).get(name,{})
        ts=b.get('source_terminals',[])
        ids=[terminal_identity(t) for t in ts]
        checks[name+'/identities']=len(ts)==rule['terminals'] and len(set(ids))==len(ids) and all(i[0] and len(i[3])==2 for i in ids)
        layers=b.get('layers',{})
        checks[name+'/layer_set']=set(layers)==set(manifest['layers'])
        for layer in manifest['layers']:
            record=layers.get(layer,{})
            for key in ('replay','historical_geometry_preservation'):
                checks[name+'/'+layer+'/'+key]=record.get(key,{}).get('status')=='PASS'
        for key in ('anchors','physical_connections'):
            records=b.get(key,{})
            checks[name+'/'+key]=set(records)=={'F.Cu','B.Cu'} and all(v.get('status')=='PASS' for v in records.values())
        checks[name+'/exposure']=b.get('nominal_exposure',{}).get('no_edit_preservation',{}).get('status')=='PASS'
        faults=b.get('faults',[])
        checks[name+'/faults']=len(faults)==len(manifest['faults']) and {f['name'] for f in faults}==set(manifest['faults']) and all(f.get('status')=='PASS' for f in faults)
        electrical[name]=electrical_status(ts,b.get('electrical_profile'))
        intent=b.get('intent',{})
        if rule['electrical']=='required_missing_intent_refusal':
            checks[name+'/refusal']=bool(ts) and all(not t.get('net') for t in ts) and electrical[name]=='NOT_ESTABLISHED' and b.get('electrical_profile')=='NOT_ESTABLISHED' and set(intent)=={'F.Cu','B.Cu'} and all(v.get('connections')=='NOT_ESTABLISHED' and v.get('no_short')=='NOT_ESTABLISHED' for v in intent.values())
        elif rule['electrical']=='qualified_same_layer':
            checks[name+'/electrical']=electrical[name]=='PASS' and set(intent)=={'F.Cu','B.Cu'} and all(v.get('connections')=='PASS' and v.get('no_short')=='PASS' and len(v.get('source_justified_same_layer_pairs',[]))>=120 for v in intent.values())
        else:checks[name+'/electrical_policy']=False
    return {'profile':manifest['id'],'status':'PASS' if all(checks.values()) else 'FAIL','required_checks':checks,'electrical_acceptance':electrical,'original_overall':report.get('overall'),'manufacturing':'NOT_ESTABLISHED','Cursor':'NOT_RUN: CHANNEL_UNAVAILABLE'}

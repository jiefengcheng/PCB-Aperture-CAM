#!/usr/bin/env python3
"""Full-source saved-geometry audit without constructor or runner imports."""
import hashlib,json,math,re,sys
from pathlib import Path
from shapely import from_wkb,to_wkb
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.native_inventory import inventory

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def gh(g):return hashlib.sha256(to_wkb(g,byte_order=1)).hexdigest()

def main(out):
    assert out.resolve().is_relative_to(ROOT/'out')
    r=json.loads((out/'report.json').read_bytes());p=json.loads((out/'policy.json').read_bytes());bindings=json.loads((out/'obstacle_bindings.json').read_bytes())
    assert sha(out/'policy.json')==r['policy_sha256'];assert sha(out/'obstacle_bindings.json')==r['obstacle_bindings_sha256']
    assert p['hard_radius_factor']==r['hard_factor_ceiling']==1.5
    for name,h in r['code_sha256'].items():assert sha(out/'review_source'/name)==h
    source=(ROOT/p['source']).read_bytes();assert hashlib.sha256(source).hexdigest()==p['source_sha256']==r['source_sha256']
    inv=inventory(source);rows=[row for row in inv['objects'] if 'F.Cu' in row['layers']]
    assert len(rows)==17849 and all(row['geometry_sha256'] for row in rows)
    shapes={row['id']:from_wkb(inv['payloads'][row['geometry_sha256']]) for row in rows}
    g={}
    for name,h in r['geometry_sha256'].items():assert sha(out/(name+'.wkb'))==h;g[name]=from_wkb((out/(name+'.wkb')).read_bytes())
    for k in ['a','b']:
        assert shapes[r[k]['source_id']].equals_exact(g[k+'_core'],0)
        assert r[k+'_radius_mm']<=1.5*r[k]['radius']
        assert abs(r[k+'_radius_mm']/r[k]['radius']-r['shared_factor'])<1e-12
        envelope=g['a_round' if k=='a' else 'b_envelope']
        assert max(abs(math.dist(r[k]['center'],v)-r[k+'_radius_mm']) for v in envelope.exterior.coords)<1e-12
        h=r[k+'_radius_mm']/math.sqrt(2);cx,cy=r[k]['center'];theta=math.radians(-45)
        expected=[(cx+x*math.cos(theta)-y*math.sin(theta),cy+x*math.sin(theta)+y*math.cos(theta)) for x,y in [(-h,-h),(h,-h),(h,h),(-h,h)]]
        assert all(math.dist(a,b)<1e-12 for a,b in zip(expected,list(g[k+'_square'].exterior.coords)[:4]))
    assert 1<=r['shared_factor']<=1.5
    side=r['a_square_side'];coordinates=list(g['a_square'].exterior.coords)[:4];i=side['index'];a,b=coordinates[i],coordinates[(i+1)%4]
    normal=((b[1]-a[1])/math.dist(a,b),-(b[0]-a[0])/math.dist(a,b));mid=((a[0]+b[0])/2,(a[1]+b[1])/2)
    squaregap=sum(normal[j]*(r['b']['center'][j]-mid[j]) for j in range(2))-r['b_radius_mm']
    assert squaregap>=.020
    cases=[]
    for target,key,envelope_key,replaced in [('a','a_round','a_round','b'),('b','b_final','b_envelope','a'),('b','b_at_cap_control','b_cap','a')]:
        core=g[target+'_core'];candidate=g[key];addition=candidate.difference(core);site=r[target]
        assert candidate.is_valid and core.difference(candidate).area<=1e-10 and candidate.difference(g[envelope_key]).area<=1e-10
        assert max(math.dist(site['center'],v) for v in candidate.exterior.coords)<=1.5*site['radius']+1e-12
        parts=[addition] if addition.geom_type=='Polygon' else list(addition.geoms);assert all(part.distance(core)<=1e-9 for part in parts)
        bound={row['source_id']:row for row in bindings[target]};ports=0;relevant=0;minimum=math.inf
        for row in rows:
            sid=row['id']
            if sid in site['aliases']:continue
            shape=shapes[sid]
            if sid in r[replaced]['aliases']:shape=g['a_round' if replaced=='a' else 'b_final'];sid=r[replaced]['source_id']
            # The source query uses .02002, so require coverage only where the
            # hard .020 exclusion can reach novel copper. Still scan every row.
            if shape.distance(candidate)>.02002:continue
            relevant+=1;assert sid in bound;entry=bound[sid];assert entry['geometry_sha256']==gh(shape)
            port=None
            if row['kind'] in ['segment','arc'] and shape.intersects(core.buffer(1e-7,quad_segs=128)):
                width=float(re.search(r'\(\s*width\s+([0-9.]+)\s*\)',source[slice(*row['source_span'])].decode()).group(1))
                port=shape.buffer(max(.005,width/2+.005),quad_segs=128).intersection(core.buffer(site['enlarged_radius']-site['radius'],quad_segs=128))
                assert port.equals_exact(from_wkb(bytes.fromhex(entry['port_zone_wkb'])),0);ports+=1
                assert addition.intersection(shape).difference(port).area<=1e-10
            else:assert entry['port_zone_wkb'] is None;minimum=min(minimum,addition.distance(shape))
            exclusion=shape.buffer(.020,quad_segs=128)
            if port is not None:exclusion=exclusion.difference(port)
            assert addition.intersection(exclusion).area<=1e-10
        assert minimum>=.020
        cases.append({'candidate':key,'full_source_records_scanned':len(rows),'hard_gap_relevant_objects':relevant,'ports':ports,'minimum_within_audit_band_mm':minimum if math.isfinite(minimum) else None,'status':'PASS'})
    negative_max=max(math.dist(r['b']['center'],v) for v in g['over_cap_negative'].exterior.coords)
    assert negative_max>1.5*r['b']['radius'] and r['negative']['rejected'] is True
    result={'status':'PASS_BALANCED_CAPPED_LOCAL_AUDIT','report_sha256':sha(out/'report.json'),'auditor_sha256':sha(Path(__file__)),'scope':'Same-author fresh-process saved-geometry audit; no editing constructor or runner imported. Shared parser/kernel.','cases':cases,'hard_cap_checked_on_both_envelopes_and_all_accepted_contours':True,'shared_scale_verified':True,'over_cap_negative_status':'FAIL_EXPECTED','square_pair_constraint_active':False}
    (out/'local_audit.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main(Path(sys.argv[1]))

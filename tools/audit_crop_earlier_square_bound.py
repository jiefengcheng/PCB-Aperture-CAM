#!/usr/bin/env python3
"""Fresh-process full-inventory check; imports neither editing constructor nor runner."""
import hashlib,json,math,re,sys
from pathlib import Path
from shapely import from_wkb,to_wkb
from shapely.geometry import LineString
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.native_inventory import inventory

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def gh(g):return hashlib.sha256(to_wkb(g,byte_order=1)).hexdigest()

def main(out):
    assert out.resolve().is_relative_to(ROOT/'out')
    r=json.loads((out/'report.json').read_bytes());p=json.loads((out/'policy.json').read_bytes())
    assert sha(out/'policy.json')==r['policy_sha256']
    assert sha(out/'obstacle_bindings.json')==r['obstacle_bindings_sha256']
    for relative,h in r['code_sha256'].items():assert sha(out/'review_source'/relative)==h
    source=(ROOT/p['source']).read_bytes();assert hashlib.sha256(source).hexdigest()==r['source_sha256']==p['source_sha256']
    inv=inventory(source);rows=[row for row in inv['objects'] if 'F.Cu' in row['layers']]
    assert len(rows)==17849 and all(row['geometry_sha256'] for row in rows)
    shapes={row['id']:from_wkb(inv['payloads'][row['geometry_sha256']]) for row in rows}
    g={}
    for name,h in r['geometry_sha256'].items():assert sha(out/(name+'.wkb'))==h;g[name]=from_wkb((out/(name+'.wkb')).read_bytes())
    for k in ['a','b']:assert shapes[r[k]['source_id']].equals_exact(g[k+'_core'],0)
    assert max(abs(math.dist(r['a']['center'],v)-r['a_radius_mm']) for v in g['a_round'].exterior.coords)<1e-12
    theta=math.radians(p['orientation_degrees']);cx,cy=r['a']['center'];h=r['a_radius_mm']/math.sqrt(2)
    vertices=[(cx+x*math.cos(theta)-y*math.sin(theta),cy+x*math.sin(theta)+y*math.cos(theta)) for x,y in [(-h,-h),(h,-h),(h,h),(-h,h)]]
    assert all(math.dist(v,e)<1e-12 for v,e in zip(list(g['a_square'].exterior.coords)[:4],vertices))
    side=r['a_square_bound']['side']; i=side['index'];a,b=vertices[i],vertices[(i+1)%4]
    assert all(math.dist(v,e)<1e-12 for v,e in zip(side['vertices'],[a,b]))
    ex,ey=b[0]-a[0],b[1]-a[1];ln=math.hypot(ex,ey);normal=(ey/ln,-ex/ln)
    assert all(abs(x-y)<1e-12 for x,y in zip(side['normal'],normal))
    distance=sum(normal[j]*(r['b']['center'][j]-side['midpoint'][j]) for j in range(2))
    assert abs(r['b_radius_mm']-(distance-p['construction_exclusion_mm']-p['safety_mm']))<1e-12
    assert g['b_envelope'].distance(LineString(side['vertices']))>=p['hard_experimental_gap_mm']
    bindings=json.loads((out/'obstacle_bindings.json').read_bytes());cases=[]
    for target,candidate_key,replaced,expected_safe in [('a','a_round','b',True),('b','b_final','a',True),('b','b_round_bound_control','a',True),('b','b_direct_unsafe','a',False)]:
        site=r[target];core=g[target+'_core'];candidate=g[candidate_key];addition=candidate.difference(core)
        assert candidate.is_valid and core.difference(candidate).area<=1e-10
        assert candidate.difference(g['a_round'] if target=='a' else g['b_envelope']).area<=1e-10
        if expected_safe:
            parts=[addition] if addition.geom_type=='Polygon' else list(addition.geoms)
            assert all(part.distance(core)<=1e-9 for part in parts)
        bound={v['source_id']:v for v in bindings[target]};violations=[];ports=0;minimum=math.inf;applicable=0
        for row in rows:
            sid=row['id']
            if sid in site['aliases']:continue
            shape=shapes[sid]
            if sid in r[replaced]['aliases']:
                shape=g['a_round' if replaced=='a' else 'b_final'];sid=r[replaced]['source_id']
            # Skip only after a complete source scan and geometric distance bound.
            if shape.distance(candidate)>.026:continue
            applicable+=1;assert sid in bound,'MISSING_OBSTACLE:'+sid
            entry=bound[sid];assert entry['geometry_sha256']==gh(shape)
            port=None
            if row['kind'] in ['segment','arc'] and shape.intersects(core.buffer(1e-7,quad_segs=128)):
                width=float(re.search(r'\(\s*width\s+([0-9.]+)\s*\)',source[slice(*row['source_span'])].decode()).group(1))
                port=shape.buffer(max(.005,width/2+.005),quad_segs=128).intersection(core.buffer(site['enlarged_radius']-site['radius'],quad_segs=128))
                assert port.equals_exact(from_wkb(bytes.fromhex(entry['port_zone_wkb'])),0);ports+=1
                if expected_safe:assert addition.intersection(shape).difference(port).area<=1e-10
            else:assert entry['port_zone_wkb'] is None;minimum=min(minimum,addition.distance(shape))
            exclusion=shape.buffer(p['hard_experimental_gap_mm'],quad_segs=128)
            if port is not None:exclusion=exclusion.difference(port)
            intrusion=addition.intersection(exclusion).area
            if intrusion>1e-10:violations.append({'source_id':sid,'intrusion_mm2':intrusion})
        assert (not violations)==expected_safe
        if expected_safe:assert minimum>=p['hard_experimental_gap_mm']
        cases.append({'candidate':candidate_key,'full_source_records_scanned':len(rows),'applicable':applicable,'ports':ports,'minimum_unexempted_gap_mm':minimum,'status':'PASS' if expected_safe else 'FAIL_EXPECTED','violations':violations})
    assert g['a_round'].intersection(g['b_envelope']).area>1e-8
    assert g['a_round'].distance(g['b_final'])>=p['hard_experimental_gap_mm']
    assert abs(g['a_round'].intersection(g['b_direct_unsafe']).area-r['unsafe_direct_stop_overlap_mm2'])<1e-12
    result={'status':'PASS_SCOPED_FEASIBILITY_AUDIT','report_sha256':sha(out/'report.json'),'auditor_sha256':sha(Path(__file__)),'scope':'Same-author full-source local audit; shared native parser and geometry kernel. No editing constructor or runner imported.','cases':cases}
    (out/'local_audit.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main(Path(sys.argv[1]))

"""Run the authorized FC-1 mathematical oracle; no Gerber implementation."""
from pathlib import Path
import hashlib, importlib.metadata, json, math, platform, subprocess, zipfile
from shapely.ops import unary_union
from .fc1_oracle import (analytic_area, placed_polygons, assess_polygons,
    synthetic_probes, png_comparison, polygon_vs_analytic_grid, QUADRANTS,
    ARC_SEGMENTS, LINEAR_BUDGET, AREA_BUDGET)
from tools.preflight import verify_manifest
from tools.qualify_public import inventory, parser_probe

ROOT=Path(__file__).resolve().parents[1]
PREFIX='2026_03_24_Gerber_Layer_Format_Test_Files/'
NAME='Block_with_different_orientations'
SOURCE=ROOT/'external/sources/Ucamco/gerber-layer-format-test-files_en.zip'
OUT=ROOT/'out/fc1/run_001'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def eligible(file,known_hash):
    # This is custody-bound eligibility, not recognition of Gerber semantics.
    return {'status':'PASS' if sha(file)==known_hash else 'NOT_ESTABLISHED',
            'reason':'Exact hash-bound official oracle source' if sha(file)==known_hash else 'Outside the one-file hash-bound oracle; no semantic/parser coverage is asserted.'}

def custody():
    assert verify_manifest()==70
    public=json.loads((ROOT/'contracts/public_sources.json').read_text())['sources']
    assert sha(SOURCE)==public['Ucamco']['archive_sha256']
    for name in ('GlowStitch','HALPI2-HDMI-FPC'):
        local=ROOT/'external/sources'/name
        assert inventory(local)==public[name]['source_inventory']
        assert subprocess.check_output(['git','-C',str(local),'rev-parse','HEAD'],text=True).strip()==public[name]['commit']
        assert subprocess.check_output(['git','-C',str(local),'status','--porcelain'],text=True).strip()==''
    with zipfile.ZipFile(SOURCE) as z:
        for row in public['Ucamco']['inventory']:
            assert hashlib.sha256(z.read(row['path'])).hexdigest()==row['sha256']
    return public

def main():
    public=custody()
    if OUT.exists():raise SystemExit('FC-1 run exists and is frozen; do not overwrite')
    OUT.mkdir(parents=True)
    with zipfile.ZipFile(SOURCE) as z:
        for ext in ('gbr','png'):(OUT/(NAME+'.'+ext)).write_bytes(z.read(PREFIX+NAME+'.'+ext))
        nested=z.read(PREFIX+'Nested_blocks.gbr')
    source=OUT/(NAME+'.gbr');png=OUT/(NAME+'.png');known=sha(source)
    ledger_path=ROOT/'tests/fc1_expected.json';ledger=json.loads(ledger_path.read_text())
    shapes=placed_polygons();positive=assess_polygons(shapes)
    # Literal source-derived ledger is separate from builder-produced results.
    ledger_ok=abs(analytic_area()-ledger['base_area_mm2'])<1e-12 and abs(sum(s.area for s in shapes)-ledger['total_area_mm2'])<4*AREA_BUDGET
    ledger_ok &= all(max(abs(a-b) for a,b in zip(s.bounds,e))<LINEAR_BUDGET for s,e in zip(shapes,ledger['placement_bounds_mm']))
    controls=[]
    intended={'wrong_mirror':(2,'landmark'),'wrong_order':(2,'landmark'),'wrong_scale':(3,'area'),
              'clear_as_dark':(0,'hole'),'major_arc':(0,'absent_major_arc'),'wrong_arc_center':(0,'arc_mid'),'inch_units':(0,'bounds')}
    for name,(idx,reason) in intended.items():
        assessed=assess_polygons(placed_polygons(name));row=assessed['placements'][idx]
        if reason=='area':correct=row['area_error_mm2']>AREA_BUDGET
        elif reason=='bounds':correct=row['max_bounds_error_mm']>LINEAR_BUDGET
        elif reason=='landmark':correct=any(x['status']=='FAIL' for x in row['landmarks'])
        else:correct=next(x for x in row['landmarks'] if x['name']==reason)['status']=='FAIL'
        controls.append({'name':name,'expected':'FAIL','actual':assessed['status'],'intended_reason':reason,
                         'intended_placement':idx,'status':'PASS' if assessed['status']=='FAIL' and correct else 'FAIL','assessment':assessed})
    raw=source.read_bytes();mutations={
       'undefined_aperture':raw.replace(b'D12*\r\nX0Y0D03*',b'D99*\r\nX0Y0D03*'),
       'recursive_block':raw.replace(b'%AB*%',b'D12*\r\nX0Y0D03*\r\n%AB*%'),
       'nested_block':nested,
       'missing_units':raw.replace(b'%MOMM*%\r\n',b''),
       'unknown_operation':raw.replace(b'M02*',b'G999*\r\nM02*')}
    unsupported=[];folder=OUT/'unsupported_controls';folder.mkdir()
    for name,data in mutations.items():
        assert data!=raw;file=folder/(name+'.gbr');file.write_bytes(data)
        scope=eligible(file,known)
        unsupported.append({'name':name,'sha256':sha(file),'oracle_scope':scope,
                            'status':'PASS' if scope['status']=='NOT_ESTABLISHED' else 'FAIL',
                            'parser_probe':'NOT_RUN: these are oracle scope controls, not parser-implementation tests.'})
    probes=synthetic_probes();raster=png_comparison(png);grid=polygon_vs_analytic_grid()
    probe=parser_probe(source)
    old=json.loads((ROOT/'out/v1_5/Ucamco/compatibility.json').read_text())
    retained=next(x for x in old['results'] if x['path']==PREFIX+NAME+'.gbr')['gerbonara_parse_and_primitive_expansion']
    parser_preserved=probe['status']==retained['status']=='NOT_ESTABLISHED' and bool(probe['warnings'])
    whole=unary_union(shapes)
    (OUT/'oracle_preview.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="789" height="605" viewBox="0 0 789 605"><rect width="789" height="605" fill="black"/><g transform="matrix(36 0 0 -36 208 448)">'+whole.svg(scale_factor=0,fill_color='#ff5e18',opacity=1)+'</g></svg>\n')
    checks={'custody':'PASS','positive':positive['status'],'literal_ledger':'PASS' if ledger_ok else 'FAIL',
            'analytic_grid':grid['status'],'raster_crosscheck':raster['status'],
            'fault_controls':'PASS' if all(c['status']=='PASS' for c in controls) else 'FAIL',
            'synthetic_probes':'PASS' if all(c['status']=='PASS' for c in probes.values()) else 'FAIL',
            'unsupported_scope_controls':'PASS' if all(c['status']=='PASS' for c in unsupported) else 'FAIL',
            'parser_failure_preserved':'PASS' if parser_preserved else 'FAIL'}
    custody()
    prior=json.loads((ROOT/'out/fc1/prior_evidence_hashes.json').read_text())
    changed=[f for f,d in prior.items() if not (ROOT/f).is_file() or sha(ROOT/f)!=d]
    checks['prior_evidence_unchanged']='PASS' if not changed else 'FAIL'
    report={'gate':'FC-1','report_version':'1','scope':'Independent mathematical oracle qualification for one source hash; not Gerber parser support or production validation.',
            'authorization':'User approved reconciliations and FC-1 only: Sure. go ahead, 2026-10-14.',
            'sources':{'archive_sha256':sha(SOURCE),'gerber_member':PREFIX+NAME+'.gbr','gerber_sha256':known,'png_sha256':sha(png),'expected_ledger_sha256':sha(ledger_path)},
            'tool_versions':{**{x:importlib.metadata.version(x) for x in ('shapely','numpy','gerbonara')},'python':platform.python_version()},
            'error_budget':{'coordinate_resolution_mm':1e-6,'circle_segments_per_quadrant':QUADRANTS,'arc_centerline_segments':ARC_SEGMENTS,'linear_mm':LINEAR_BUDGET,'area_mm2':AREA_BUDGET,
               'max_flash_disk_sag_mm':.5*(1-math.cos(math.pi/(4*QUADRANTS))),
               'max_arc_centerline_sag_mm':2*(1-math.cos(math.pi/(4*ARC_SEGMENTS)))},
            'checks':checks,'overall':'PASS' if all(v=='PASS' for v in checks.values()) else 'FAIL',
            'positive':positive,'analytic_grid':grid,'raster_crosscheck':raster,
            'negative_controls':controls,'synthetic_probes':probes,'unsupported_scope_controls':unsupported,
            'current_parser_probe':probe,'extended_parser_support':'NOT_ESTABLISHED','realistic_validation':'NOT_ESTABLISHED',
            'cursor_review':{'status':'NOT_RUN','reason':'CHANNEL_UNAVAILABLE'},
            'changed_prior_evidence':changed,'limitations':['Oracle is hand-authored for one exact source hash and does not parse commands.','Raster comparison excludes a two-pixel boundary band and is secondary, not a precision oracle.','Reset leakage and clearing pre-existing copper require separately labeled synthetic scene extensions.','Unsupported input checks reject hash-mismatched inputs, not their Gerber semantics.','Same coordinator authored both mathematical routes; no independent human or Cursor review occurred.']}
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'overall':report['overall'],'checks':checks,'raster':raster,'analytic_grid':grid},indent=2))
    if report['overall']!='PASS':raise SystemExit(1)
if __name__=='__main__':main()

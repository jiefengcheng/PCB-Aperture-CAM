"""Non-semantic scene/evidence adapter over frozen Gerber results.
No acceptance computation, native editing or pcb_Z access. Display differences
and simplified paths are derivatives, never replacement validation metrics.
"""
from pathlib import Path
import hashlib,json,math,shutil
import sexpdata
from shapely import affinity,from_wkb
from shapely.geometry import box,LineString
from .validator import layers
from .gerber_image import read_image
from .native_reference import children,one
ROOT=Path(__file__).resolve().parents[1]
class UnverifiedEvidence(ValueError):pass
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bound(path,expected):
    p=Path(path)
    if not p.is_file() or sha(p)!=expected:raise UnverifiedEvidence('STALE / UNVERIFIED: missing or mismatched '+str(p))
    return p

def svg_path(geometry,tolerance=.001):
    g=geometry.simplify(tolerance,preserve_topology=True)
    polygons=list(g.geoms) if g.geom_type=='MultiPolygon' else ([] if g.is_empty else [g])
    out=[]
    for p in polygons:
        if p.geom_type!='Polygon':raise ValueError('non-polygon composed image')
        for ring in [p.exterior,*p.interiors]:
            out.append('M'+' L'.join(f'{x:.5f} {y:.5f}' for x,y in ring.coords)+' Z')
    return ' '.join(out)

def bounds(g,pad=.7):
    if g.is_empty:return None
    a,b,c,d=g.bounds;return [a-pad,b-pad,c-a+pad*2,d-b+pad*2]

def build_scene(manifest,out):
    from tools.preflight import verify_manifest
    verify_manifest()
    out=Path(out);(out/'evidence').mkdir(parents=True,exist_ok=True)
    reports={};provenance=[];geometry={};store={}
    def evidence(path,digest=None,name=None):
        path=Path(path);path=path if path.is_absolute() else ROOT/path
        if digest:bound(path,digest)
        if not path.is_file():raise UnverifiedEvidence('missing evidence '+str(path))
        key=hashlib.sha256(str(path).encode()).hexdigest()[:12]+'_'+(name or path.name)
        target=out/'evidence'/key
        if not target.exists():shutil.copy2(path,target)
        logical=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
        record={'path':logical,'sha256':sha(path),'snapshot':'evidence/'+key}
        if record not in provenance:provenance.append(record)
        return record
    for name,rec in manifest['reports'].items():
        path=bound(ROOT/rec['path'],rec['sha256']);reports[name]=json.loads(path.read_text());evidence(path,rec['sha256'])
    v,h,c,sa=[reports[k] for k in ('v2','hal','completion','source_aware')]
    vr=(ROOT/manifest['reports']['v2']['path']).parent;cr=(ROOT/manifest['reports']['completion']['path']).parent
    for key in ('implementation_sha256',):
        for path,digest in v[key].items():bound(ROOT/path,digest)
    for path,digest in c['implementation_hashes'].items():bound(ROOT/path,digest)
    for path,digest in c['input_reference_bindings'].items():bound(ROOT/path,digest)
    # Every displayed/raw fault image is bound to its authoritative report receipt.
    for path,digest in v['output_sha256'].items():bound(vr/path,digest)
    for path,digest in c['output_hashes'].items():bound(cr/path,digest)
    def geom(g):
        key='g'+hashlib.sha256(g.wkb).hexdigest()[:20]
        if key not in geometry:
            store[key]=g;geometry[key]={'path':svg_path(g,manifest['display_simplification_mm']),'bounds':bounds(g,0),'basis':'Constrained display path; layer/object reference states whether exported image or source annotation'}
        return key
    def source_objects(board,roleplan=None):
        root=sexpdata.loads(Path(board).read_text());result=[]
        if roleplan:
            for node in children(root,'segment'):
                uid=str(one(node,'tstamp',one(node,'uuid',['']))[0]);a=one(node,'start');b=one(node,'end');width=one(node,'width')[0]
                role='dependent' if uid in roleplan['dependents'] else 'protected'
                result.append({'id':uid,'name':next((f'T{i+1}' for i,x in enumerate([*roleplan['dependents'],'0b757436-b9bf-53d1-bc3a-4f33f834f4ef','fedb7fa6-33ba-5854-a304-9e38f5c0df42']) if x==uid),uid),'role':role,'layer':'F.Cu','center':[(a[0]+b[0])/2,(a[1]+b[1])/2],'shape':geom(LineString([a,b]).buffer(width/2)),'basis':'Native-source expected segment annotation, not observed copper','net':str(one(node,'net')[0])})
        return result
    def pairs_for_synthetic(report,objects,intent):
        check=next((x for x in report.get('checks',[]) if x['id']=='connectivity'),{});assigned=check.get('actual',{}).get('terminal_components',{})
        return [{'a':a,'b':b,'net':intent['pin_net_intent'][a],'status':'PASS' if a in assigned and b in assigned and assigned[a]==assigned[b] else 'FAIL','basis':'Stored terminal-component associations; global neck result remains separate'} for a,b in intent['pairs']] if check else []
    def state(key,label,image,verdict,checks,ev,objects,pairs=None,control=None,replay=None):
        return {'id':key,'label':label,'layers':{k:geom(g) for k,g in image.items()},'candidate_verdict':verdict or 'UNVERIFIED','checks':checks,'evidence':ev,'objects':objects,'pairs':pairs or [],'control_test':control,'replay':replay or [],'metrics':{}}
    def delta_states(case):
        base=case['states'][0]['layers']
        for state in case['states']:
            state['delta']={}
            for layer,key in state['layers'].items():
                if layer in base:
                    a,b=store[base[layer]],store[key]
                    state['delta'][layer]={'added':geom(b.difference(a)),'removed':geom(a.difference(b))}
        return case
    operation_contract=json.loads(bound(ROOT/'contracts/v2_move_pad.json',v['contract_sha256']).read_text())
    bound(ROOT/operation_contract['policy'],operation_contract['policy_sha256'])
    bound(ROOT/operation_contract['intent'],operation_contract['intent_sha256'])
    if h['baseline_sha256']!=manifest['reports']['completion']['sha256'] or sa['baseline_report_sha256']!=manifest['reports']['completion']['sha256']:raise UnverifiedEvidence('reference revision mismatch')
    planpath=vr/'positive/accepted/operation.json';op=json.loads(planpath.read_text());evidence(planpath,v['output_sha256']['positive/accepted/operation.json'])
    policy=json.loads((ROOT/'assets/starter/reference/policy.json').read_text());evidence(ROOT/'assets/starter/reference/policy.json',operation_contract['policy_sha256'])
    intent=json.loads((ROOT/'assets/starter/reference/intended_connections.json').read_text());evidence(ROOT/'assets/starter/reference/intended_connections.json')
    synthetic={'id':'synthetic','name':'Aperture coupon · automatic V2','story':'Move the copper; keep the opening fixed. A correct pad position still needs preserved connections.','run_id':vr.name,'code_commit':'500d070c17a4e51d944eed90264f6501a5567789','profile_id':v['operation_contract'],'basis':'Fresh KiCad-plotted V2 before / computed candidate / deliberately corrupted export copies','limitations':['One synthetic front-copper coupon; invented policy, not factory approval.','Physical grouping includes P2/T4; they remain protected.','Role/expected-segment outlines are native-source annotations; copper fill is actual Gerber.'],'states':[],'focus':[18.7,18.6,3.2,4.5],'scope':policy['allowed_copper_change_rectangle'],'aggregate':sa['original_overall'],'physical_group':op['connected_context'],'electrical':'Synthetic independent author intent','source_aware':sa['status']}
    before=layers(vr/'before/gerbers');candidate=layers(vr/'positive/accepted/gerbers')
    role_by_pad={'P1':'target','P2':'protected','P3':'protected','P4':'protected'}
    def synth_objects(parsed,native):
        objects=[]
        native_root=sexpdata.loads(Path(native).read_text());pad_ids={str(p[1]):str(one(p,'tstamp',one(p,'uuid',['']))[0]) for fp in children(native_root,'footprint') for p in children(fp,'pad')}
        for pid,(x,y,g) in parsed['F_Cu']['pads'].items():objects.append({'id':pid,'name':pid,'center':[x,y],'role':role_by_pad[pid],'layer':'F.Cu','shape':geom(g),'net':intent['pin_net_intent'][pid],'basis':'Gerber .P terminal mapped to independent synthetic intent','source_identity':{'source_board_sha256':sha(native),'terminal':pid,'native_id':pad_ids[pid[1:]]}})
        for i,g in enumerate(sorted(parsed['F_Mask']['objects'],key=lambda g:(round(g.centroid.x),round(g.centroid.y)))):
            objects.append({'id':f'A{i+1}','name':f'A{i+1}','center':list(g.centroid.coords)[0],'role':'fixed opening','layer':'F.Mask','shape':geom(g),'basis':'Actual Gerber opening annotation, not protective film','net':None})
        return objects+source_objects(native,op)
    negative_path=vr/'negative_controls.json';negative=json.loads(negative_path.read_text());evidence(negative_path,v['output_sha256']['negative_controls.json'])
    entries=[('before','Original · read-only reference',before,{'overall':'BASELINE','checks':[]},None,vr/'before/coupon.kicad_pcb',None)]
    entries.append(('computed','Computed candidate · P1 20.05 mm',candidate,v['native_gerber_validation'],None,vr/'positive/accepted/coupon.kicad_pcb',v['transactions']['positive']['events']))
    for name in ('disconnected_n1','bridge','shifted_aperture','protected_p3'):
        row=next(x for x in negative if x['name']==name);folder=vr/'gerber_faults'/name
        if name=='disconnected_n1':
            folder=vr/'broken_connection/staging/gerbers'
            row={**row,'report':json.loads((vr/'broken_connection/staging/validation.json').read_text()),'status':v['rollback']['status']}
        entries.append((name,{'disconnected_n1':'Open control · required trace removed','bridge':'Bridge control · N1–N2','shifted_aperture':'Fixed-opening control · mask shifted','protected_p3':'Protected-object control · P3 moved'}[name],layers(folder),row['report'],row,vr/'positive/accepted/coupon.kicad_pcb',v['transactions']['broken_connection']['events'] if name=='disconnected_n1' else None))
    for key,label,parsed,report,control,native,events in entries:
        evpath=(vr/'broken_connection/staging/validation.json') if key=='disconnected_n1' else (vr/'result.json' if not control else negative_path);ev=evidence(evpath)
        objects=synth_objects(parsed,native);checks=[]
        for check in report['checks']:
            cid=check['id'];focus=synthetic['focus'];affected=['P1']
            if cid in ('connectivity','trace_width'):affected=['P1','P2',op['dependents'][2]]
            if cid in ('no_short','clearance'):focus=[19,22.8,5.2,3.8];affected=['P1','P3']
            if cid=='fixed_reference':affected=['A1']
            if cid=='scope':affected=['P3'];focus=[18.3,18.3,6.5,9.6]
            checks.append({'id':cid,'label':cid.replace('_',' ').title(),'status':check['status'],'metric':check.get('actual'),'expected':'Frozen synthetic policy · '+cid,'objects':affected,'focus':focus,'evidence':ev,'source_ids':affected})
        st=state(key,label,{k.replace('_','.'):val['geometry'] for k,val in parsed.items()},report['overall'],checks,ev,objects,pairs_for_synthetic(report,objects,intent),{'status':control['status'],'expected':control['expected'],'observed':control['actual']} if control else None,events)
        st['metrics']=dict(next((x['actual'] for x in report['checks'] if x['id']=='exposure'),{}))
        st['metrics']['P1_center_mm']=list(parsed['F_Cu']['pads']['P1'][:2])
        if key in ('computed','disconnected_n1'):
            tx=v['transactions']['positive' if key=='computed' else 'broken_connection']
            st['replay']=[*tx['events'],tx['state']+' (recorded outcome)']
            st['execution']={'state':tx['state'],'source_unchanged':tx['source_unchanged'],'rollback':v['rollback'],'evidence':evidence(vr/'result.json')}
        for layer,rec in parsed.items():evidence(rec['inventory']['path'],rec['inventory']['sha256'])
        synthetic['states'].append(st)
    # Source/public geometry is reused from complete, hash-bound composed WKB layers.
    def public_images(name):
        b=c['boards'][name];images={}
        for layer,record in b['layers'].items():
            path=cr/name/(layer.replace('.','_')+'.wkb');relative=str(path.relative_to(cr));bound(path,c['output_hashes'][relative]);evidence(Path(record['path']),record['sha256'])
            images[layer]=affinity.scale(from_wkb(path.read_bytes()),1,-1,origin=(0,0))
        return images
    hb=c['boards']['HALPI2-HDMI-FPC'];himages=public_images('HALPI2-HDMI-FPC');hev=evidence(ROOT/manifest['reports']['hal']['path']);hmanifest=json.loads((ROOT/'contracts/halpi2_electrical_case_v1.json').read_text());evidence(ROOT/'contracts/halpi2_electrical_case_v1.json',h['manifest_sha256'])
    def public_objects(b):
        result=[]
        for index,t in enumerate(b['source_terminals']):
            x,y=t['center_mm'];uid=t['source_id'];identity={'source_board_sha256':b['source_board_sha256'],'source_id':uid,'pin':t['pin'],'layers':t['layers'],'center_mm':[x,y]}
            key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:20]
            result.append({'id':key,'source_id':uid,'name':(t['ref'] or 'Unnamed')+'.'+t['pin'],'center':[x,-y],'layer':t['layers'][0] if t['layers'] else None,'layers':t['layers'],'net':t['net'],'role':'source terminal','source_identity':identity,'basis':'Native-source terminal at qualified Gerber anchor; marker is an annotation','size_mm':t['size_mm']})
        return result
    ho=public_objects(hb);source_to_id={x['source_id']:x['id'] for x in ho};j22=source_to_id['10380344-ed7c-45ba-80af-33b52ebad3ea:1'];jobj=next(x for x in ho if x['id']==j22)
    for obj in ho:obj['role']='inspected terminal' if obj['id']==j22 else 'source terminal'
    hal={'id':'halpi2','name':'HALPI2 · named electrical case','story':'Inspect J22.1, then its deliberate open: the pad survives, but its 15 required GND relationships fail.','run_id':Path(manifest['reports']['hal']['path']).parent.name,'code_commit':'a5c5af7','profile_id':h['case'],'basis':h['reference_class'],'limitations':['Native-source same-layer intent only; no schematic parity or cross-layer acceptance.','J1.2/J1.5 and J2.2/J2.5 GND paths are outside qualified same-layer continuity.','Unlabelled copper and factory/process approval remain NOT_ESTABLISHED.'],'states':[],'focus':[jobj['center'][0]-2,jobj['center'][1]-1.8,4,3.6],'focus_object':j22,'aggregate':h['original_aggregate'],'source_aware':sa['status'],'electrical':h['status']+' within declared native-source same-layer scope'}
    for key,label in [('positive','Unchanged source export · positive'),('open','Open control · J22.1 isolated'),('bridge','Bridge control · different nets')]:
        images=dict(himages);control=None;failed=[];shorts=[]
        if key=='open':
            rec=h['named_open_control'];file=bound(Path(rec['file']),rec['sha256']);evidence(file,rec['sha256']);images['F.Cu']=affinity.scale(read_image(file)['geometry'],1,-1,origin=(0,0));failed=rec['failed_expected_pairs'];control={'status':rec['status'],'expected':'connections FAIL, pad retained','observed':rec['observed_connections']}
        elif key=='bridge':
            rec=h['bridge_control'];file=bound(Path(rec['file']),rec['sha256']);evidence(file,rec['sha256']);images['F.Cu']=affinity.scale(read_image(file)['geometry'],1,-1,origin=(0,0));shorts=rec['observed']['shorts'];control={'status':rec['status'],'expected':'no_short FAIL','observed':rec['observed']['no_short']}
        pairs=[]
        for layer,positive in h['positives'].items():
            raw=rec['observed']['source_justified_same_layer_pairs'] if key=='bridge' and layer=='F.Cu' else positive['positive']['source_justified_same_layer_pairs']
            for pair in raw:
                bad=any(x['a']==pair['a'] and x['b']==pair['b'] for x in failed)
                pairs.append({'a':source_to_id[pair['a']],'b':source_to_id[pair['b']],'net':pair['source_net'],'layer':layer,'status':'FAIL' if bad else pair['status']})
        connection_status=rec['observed_connections'] if key=='open' else (rec['observed']['connections'] if key=='bridge' else h['positives']['F.Cu']['positive']['connections'])
        short_status=rec['observed']['no_short'] if key=='bridge' else h['positives']['F.Cu']['positive']['no_short']
        added=images['F.Cu'].difference(himages['F.Cu']);removed=himages['F.Cu'].difference(images['F.Cu'])
        checks=[{'id':'connections','label':'Expected same-layer GND pairs','status':connection_status,'metric':{'required_pairs':len(pairs),'failed_pairs':len([x for x in pairs if x['status']=='FAIL'])},'objects':[j22],'source_ids':['J22.1'],'focus':hal['focus'],'evidence':hev,'expected':'All declared 120 GND pairs on each layer remain connected.','highlight':geom(removed) if key=='open' else None},
        {'id':'no_short','label':'Different-net separation','status':short_status,'metric':shorts if shorts else {'source_labelled_terminals':len(ho)},'objects':[],'source_ids':[n for item in shorts for n in item['source_nets']],'focus':bounds(added,1) if key=='bridge' else bounds(images['F.Cu'],1),'evidence':hev,'expected':'No component joins different qualified source nets.','highlight':geom(added) if key=='bridge' else None},
        {'id':'anchors','label':'Named terminal mapping','status':'PASS' if all(h['positives'][l]['anchors']['status']=='PASS' for l in h['positives']) else 'UNVERIFIED','metric':{'mapped_terminals':len(h['terminal_export_mapping']),'open_pad_retained':h['named_open_control']['pad_shape_fully_retained'] if key=='open' else None},'objects':[j22],'source_ids':['J22.1'],'focus':hal['focus'],'evidence':hev,'expected':'All 64 named pads accounted for; open control retains the inspected pad.'}]
        st=state(key,label,images,h['status'] if key=='positive' else control['observed'],checks,hev,ho,pairs,control)
        st['metrics']={'declared_pairs':len(pairs),'mapped_terminals':len(h['terminal_export_mapping']),'J22_failed_pairs':len(failed)};hal['states'].append(st)
    gb=c['boards']['GlowStitch'];gimages=public_images('GlowStitch');go=public_objects(gb);gev=evidence(ROOT/manifest['reports']['completion']['path'])
    glow={'id':'glowstitch','name':'GlowStitch · information boundary','story':'Real copper can be inspected and preserved. Unknown net assignments stay unknown.','run_id':cr.name,'code_commit':'c0f997c','profile_id':sa['profile'],'basis':'Complete composed actual public Gerber exports; no-edit replay','limitations':['All 80 native pads have unknown electrical assignments; unnamed net 0 is not a common net or documented no-connect.','Source-aware profile PASS is separate from electrical acceptance and original aggregate V1.5.','No factory, coverlay process or electrical repair claim.'],'aggregate':sa['original_overall'],'source_aware':sa['status'],'electrical':sa['electrical_acceptance']['GlowStitch'],'states':[],'focus':bounds(gimages['F.Cu'],1)}
    gc=[{'id':'geometry','label':'Nine-layer geometry / preservation','status':gb['geometry_profile'],'metric':{'declared_layers':len(gb['layers']),'native_pads':len(go),'exposure_mm2':gb['nominal_exposure']['geometry']['area_mm2']},'objects':[],'source_ids':[],'focus':glow['focus'],'evidence':gev,'expected':'All declared layers, anchors and no-edit geometry preserved.'},
        {'id':'electrical','label':'Electrical intent is unavailable','status':sa['electrical_acceptance']['GlowStitch'],'metric':{'unknown_assignments':len([x for x in go if not x['net']]),'electrical_acceptance':sa['electrical_acceptance']['GlowStitch'],'source_aware_profile':sa['status'],'original_aggregate':sa['original_overall']},'objects':[],'source_ids':['80 revision-bound composite terminal identities'],'focus':glow['focus'],'evidence':evidence(ROOT/manifest['reports']['source_aware']['path']),'expected':'No electrical PASS without authoritative intent. Unknown is distinct from no-connect.'}]
    glow['states'].append(state('preserved','No-edit source export · geometry only',gimages,gb['geometry_profile'],gc,gev,go))
    cases=[delta_states(x) for x in (synthetic,hal,glow)]
    for case in cases:
        layer=case['states'][0]['layers'].get('Edge.Cuts') or case['states'][0]['layers'].get('Edge.Cuts'.replace('.','_'))
        case['fit']=bounds(store[layer],1) if layer else bounds(store[next(iter(case['states'][0]['layers'].values()))],1)
        case['default_state']='computed' if case['id']=='synthetic' else case['states'][0]['id']
    return {'scene_schema_version':'1.0','integrity':'VERIFIED_AT_GENERATION','units':'mm','display_transform':manifest['display_transform'],'display_simplification_mm':manifest['display_simplification_mm'],'svg_coordinate_rounding_xy_mm':.000005,'measurement_authority':'Stored backend validator results only; display simplification/differences do not change acceptance.','geometry_basis':manifest['geometry_basis'],'cases':cases,'geometry':geometry,'provenance':provenance,'review':'NOT_RUN: CHANNEL_UNAVAILABLE','manufacturing':'NOT_ESTABLISHED'}

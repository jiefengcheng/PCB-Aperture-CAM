"""Deterministic coupon MovePadWithConnections with publish-after-validation.
Inputs are the immutable before source and explicit operation/policy contract.
The supplied candidate fixture is never an executor input.
"""
from pathlib import Path
from decimal import Decimal
import hashlib,json,math,os,re
from .v2_discovery import discover

ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(ok,reason):
    if not ok:raise ValueError(reason)
def dec(v):return Decimal(str(v))

def render(source,edits):
    lines=source.splitlines(keepends=True)
    for uid,fields in edits.items():
        hits=[i for i,l in enumerate(lines) if re.search(r'\((?:tstamp|uuid) '+re.escape(uid)+r'\)',l)]
        require(len(hits)==1,'ambiguous/multiline native edit identity')
        line=lines[hits[0]]
        for key,values in fields.items():
            # Only two-coordinate fields on the qualified single-line fixture.
            pattern=r'\('+key+r'\s+[-+\d.eE]+\s+[-+\d.eE]+\)'
            line,count=re.subn(pattern,'('+key+' '+f'{values[0]:.6f} {values[1]:.6f}'+')',line)
            require(count==1,'missing/ambiguous coordinate field')
        lines[hits[0]]=line
    return ''.join(lines)

def plan(source,contract):
    require(hashlib.sha256(source.encode()).hexdigest()==contract['source_sha256'],'source revision mismatch')
    for key in ('policy','intent'):
        require(sha(ROOT/contract[key])==contract[key+'_sha256'],key+' custody mismatch')
    policy=json.loads((ROOT/contract['policy']).read_text())
    scene=discover(source,contract);objects=scene['records']
    target=objects[contract['target']];opening=objects[contract['aperture']]
    dep=[objects[i] for i in contract['dependents']]
    require(target['kind']=='pad' and target['pin']=='1' and target['net']==1,'incorrect target identity')
    require(opening['layer']=='F.Mask' and len(dep)==3 and all(d['kind']=='segment' and d['net']==target['net'] for d in dep),'incorrect dependency set')
    t1,t2,t3=dep
    require(t1['start']==target['center'] and t1['end']==t2['start'] and t2['end']==t3['start'] and t3['end']==contract['protected_anchor'],'dependent route does not meet source/anchor')
    require(t1['start'][0]==t1['end'][0] and t3['start'][0]==t3['end'][0] and t2['end'][1]>t2['start'][1] and abs(abs(t2['end'][0]-t2['start'][0])-abs(t2['end'][1]-t2['start'][1]))<1e-9,'unsupported dogleg strategy')
    require(target['size']==policy['allowed_pad_size_mm'],'target size outside policy')
    require(all(d['width']>=policy['minimum_trace_width_mm'] for d in dep),'source trace width outside policy')
    margin=dec(policy['minimum_overlap_mm'])+dec(policy['registration_uncertainty_xy_mm'])
    old=list(map(dec,target['center']));selected=[];intervals=[]
    for i in range(2):
        lo,hi=sorted([dec(opening['start'][i]),dec(opening['end'][i])]);center=(lo+hi)/2
        half=dec(target['size'][i])/2;tol=dec(policy['maximum_nominal_center_error_xy_mm'])
        feasible=(max(hi+margin-half,center-tol),min(lo-margin+half,center+tol))
        require(feasible[0]<=feasible[1],'unsatisfiable aperture/registration constraints')
        selected.append(min(max(old[i],feasible[0]),feasible[1]));intervals.append(list(map(float,feasible)))
    x,y=map(float,selected)
    require(math.dist(target['center'],[x,y])<=policy['maximum_pad_move_mm'],'movement budget exceeded')
    require(y==target['center'][1] and x>=t3['end'][0],'outside declared dogleg strategy')
    end1=[x,t1['end'][1]];join=[t3['end'][0],float(dec(end1[1])+abs(dec(x)-dec(t3['end'][0])))]
    require(join[1]<t3['end'][1],'dependent route reverses protected anchor')
    edits={target['id']:{'at':[x-target['footprint'][0],y-target['footprint'][1]]},t1['id']:{'start':[x,y],'end':end1},t2['id']:{'start':end1,'end':join},t3['id']:{'start':join}}
    candidate=render(source,edits);after=discover(candidate,contract)
    bounds=policy['allowed_copper_change_rectangle']
    from shapely.geometry import box
    allowed=box(*bounds).buffer(policy['export_geometry_tolerance_mm'])
    for uid in edits:
        delta=objects[uid]['geometry'].symmetric_difference(after['records'][uid]['geometry'])
        require(delta.difference(allowed).area<=1e-9,'planned copper exceeds permitted region')
    protected=sorted(set(objects)-set(edits));groups=scene['groups']
    group=next(g for g in groups if target['id'] in g)
    require(set(contract['dependents']).issubset(group),'dependent traces not physically connected')
    # The full remainder of the native text is byte-preserved by render.
    obstacles=[uid for uid in protected if objects[uid]['layer']=='F.Cu' and objects[uid].get('net')!=target['net']]
    return candidate,{'operation':contract['id'],'source_sha256':contract['source_sha256'],'computed_center_mm':[x,y],'feasible_center_intervals_mm':intervals,'movement_mm':math.dist(target['center'],[x,y]),'target':[target['id']],'dependents':contract['dependents'],'write_set':list(edits),'protected':protected,'connected_context':group,'read_only_obstacles':obstacles,'edits':edits,'pcb_Z_qualification':scene['qualification'],'candidate_sha256':hashlib.sha256(candidate.encode()).hexdigest()}

def execute(source_path,contract,workspace,exporter,validator,hook=None):
    """New workspace per attempt. Only all-PASS validation publishes accepted/.
    Failed staging is retained for evidence; immutable input and earlier attempts
    are never used as writable files. Hooks allow explicit fault tests only.
    """
    workspace=Path(workspace).resolve()
    require(workspace.is_relative_to(ROOT/'out/v2'),'transaction outside V2 output')
    require(not workspace.exists(),'transaction workspace already exists')
    source_path=Path(source_path);original=source_path.read_bytes();workspace.mkdir(parents=True)
    journal={'state':'PREPARING','events':[],'accepted':None}
    def event(name):
        journal['events'].append(name)
        (workspace/'transaction.json').write_text(json.dumps(journal,indent=2)+'\n')
        if hook:hook(name,workspace)
    try:
        candidate,operation=plan(original.decode(),contract);stage=workspace/'staging';stage.mkdir()
        (stage/'operation.json').write_text(json.dumps(operation,indent=2)+'\n')
        event('PLANNED')
        board=stage/'coupon.kicad_pcb';board.write_text(candidate)
        event('STAGED')
        require(board.read_text()==candidate,'staged candidate changed before export')
        output=exporter(board,stage)
        event('EXPORTED')
        require(sha(board)==operation['candidate_sha256'],'export modified native candidate')
        verdict=validator(output)
        (stage/'validation.json').write_text(json.dumps(verdict,indent=2)+'\n')
        checks=verdict.get('checks',[])
        require(verdict.get('overall')=='PASS' and {c.get('id') for c in checks if c.get('mandatory')}==set(contract['required_validation_checks']) and all(c.get('status')=='PASS' for c in checks if c.get('mandatory')),'independent validation did not pass')
        require(source_path.read_bytes()==original,'immutable source changed')
        require(sha(board)==operation['candidate_sha256'],'candidate changed during validation')
        journal['state']='VALIDATED';event('VALIDATED')
        # Last prepublication custody check also covers fault hooks/concurrent edits.
        require(sha(board)==operation['candidate_sha256'] and source_path.read_bytes()==original,'prepublication custody changed')
        os.replace(stage,workspace/'accepted')
        journal.update(state='COMMITTED',accepted=str(workspace/'accepted/coupon.kicad_pcb'))
    except Exception as exc:
        journal.update(state='REJECTED',reason=type(exc).__name__+': '+str(exc))
    journal['source_unchanged']=source_path.read_bytes()==original
    (workspace/'transaction.json').write_text(json.dumps(journal,indent=2)+'\n')
    return journal

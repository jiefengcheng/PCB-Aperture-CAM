"""Contract-driven local Gerber MovePadWithConnections executor."""
from pathlib import Path
import json,math,shutil
from .client_gerber import AdmissionError,sha,parse,locate,move_bytes,read_region
from gerbonara import graphic_objects as go

def generate(before,mask,contract,staging):
    before=Path(before);mask=Path(mask);staging=Path(staging)
    if sha(before)!=contract['input_sha256'] or sha(mask)!=contract['mask_sha256']:raise AdmissionError('input hash mismatch')
    g=parse(before);pi,pad,li,line=locate(g,contract['terminal'],contract['anchor_mm'])
    if tuple(pad.attrs['.N'])!=tuple(contract['source_net_label']):raise AdmissionError('target label mismatch')
    if abs(line.aperture.diameter-contract['trace_width_mm'])>1e-8:raise AdmissionError('trace width differs from contract')
    m=read_region(mask,contract['allowed_region_mm'])
    # Select the fixed source opening by contract anchor and shape, not nearest arbitrary geometry.
    openings=[o for o in m['objects'] if isinstance(o,go.Flash) and math.dist((o.x,o.y),contract['opening_anchor_mm'])<1e-6]
    if len(openings)!=1:raise AdmissionError('missing/ambiguous fixed opening')
    desired=(openings[0].x,openings[0].y)
    if math.dist((pad.x,pad.y),desired)>contract['max_move_mm']:raise AdmissionError('movement bound exceeded')
    x0,y0,x1,y1=contract['allowed_region_mm']
    if not x0<desired[0]<x1 or not y0<desired[1]<y1:raise AdmissionError('destination outside permitted region')
    staging.mkdir(parents=True,exist_ok=False)
    output=staging/'candidate.gbr';output.write_bytes(move_bytes(before.read_bytes(),pad,line,desired))
    shutil.copyfile(mask,staging/'mask.gbr')
    plan={'operation':'MovePadWithConnections','input_sha256':sha(before),'mask_sha256':sha(mask),'target':{'terminal':contract['terminal'],'ordinal':pi,'from_mm':[pad.x,pad.y],'to_mm':list(desired)},'dependent':{'ordinal':li,'fixed_anchor_mm':contract['anchor_mm'],'width_mm':line.aperture.diameter},'permitted_region_mm':contract['allowed_region_mm'],'protected':'Every unselected source command and all other source files','candidate_sha256':sha(output)}
    (staging/'operation.json').write_text(json.dumps(plan,indent=2)+'\n')
    return output,plan

"""EDIT-style filled-polygon materialization and semantic reopen checks."""
from copy import deepcopy
from decimal import Decimal
import uuid
import sexpdata
from shapely.geometry import Polygon
from src.source_locators import locate
from src.native_inventory import geometry
from src.native_reference import one
from .board_geometry import quantize,fidelity,bridge_contour

S=sexpdata.Symbol


def encode(node):
    if isinstance(node,list):return '('+' '.join(encode(x) for x in node)+')'
    if isinstance(node,S):return str(node)
    if isinstance(node,str):return sexpdata.dumps(node)
    if type(node) is int:return str(node)
    if type(node) is float:return format(Decimal(str(node)),'f')
    raise ValueError('UNSUPPORTED_NATIVE_ATOM:'+repr(node))


def board_bytes(root):
    return ('(kicad_pcb\n'+'\n'.join('  '+encode(x) for x in root[1:])+'\n)\n').encode()


def edit_template(edit):
    root=sexpdata.loads(edit.decode())
    for node in root[1:]:
        if isinstance(node,list) and str(node[0])=='gr_poly' and str(one(node,'layer',[''])[0])=='F.Cu' and str(one(node,'fill',[''])[0]) in ('yes','solid'):
            return deepcopy(node)
    raise ValueError('EDIT_FILLED_COPPER_TEMPLATE_MISSING')


def polygon_node(shape,template,source_id,sha):
    q,metrics=quantize(shape)
    node=deepcopy(template)
    node[:]=[x for x in node if not isinstance(x,list) or str(x[0]) not in ('pts','uuid','tstamp')]
    node.insert(1,[S('pts'),*[[S('xy'),round(x,6),round(y,6)] for x,y in bridge_contour(q)]])
    for i,x in enumerate(node):
        if isinstance(x,list) and str(x[0])=='stroke':node[i]=[S('stroke'),[S('width'),0],[S('type'),S('solid')]]
    uid=str(uuid.uuid5(uuid.NAMESPACE_URL,'pcb-board-t01-writeback:'+source_id+':'+sha))
    node.append([S('uuid'),uid])
    return node,metrics,uid


def write_board(raw,edit,decisions,targets):
    root=sexpdata.loads(raw.decode());spans=locate(raw);parent=spans[0].start
    top=[s for s in spans if s.parent_start==parent]
    if len(root)-1!=len(top):raise ValueError('NATIVE_TOP_LEVEL_MAPPING_FAILED')
    positions={s.identity:i+1 for i,s in enumerate(top)}
    template=edit_template(edit);records=[]
    for d in decisions:
        growing=d['decision'] in ('GROW_COMPANION','ROUND_GROW_PRIORITY')
        for alias in d['aliases']:
            index=positions[alias];original=root[index]
            if str(original[0])!='gr_circle' or str(one(original,'layer',[''])[0])!='F.Cu':raise ValueError('SOURCE_TARGET_ROLE_CHANGED')
            metric=None;uid=None
            if growing:
                replacement,metric,uid=polygon_node(targets[d['source_id']],template,alias,d['candidate_ref']['sha256'])
                root[index]=replacement
            records.append(dict(key=d['key'],source_id=d['source_id'],alias=alias,index=index,growing=growing,uuid=uid,quantization=metric))
    return board_bytes(root),records


def verify_board(raw,candidate,records,decisions,targets):
    before=sexpdata.loads(raw.decode());after=sexpdata.loads(candidate.decode())
    if len(before)!=len(after) or str(after[0])!='kicad_pcb':raise ValueError('NATIVE_OBJECT_COUNT_OR_ROOT_CHANGED')
    changed={r['index'] for r in records if r['growing']}
    for i,(left,right) in enumerate(zip(before,after)):
        if i not in changed and left!=right:raise ValueError('PROTECTED_NATIVE_OBJECT_CHANGED:'+str(i))
    byid={d['source_id']:d for d in decisions};rows=[]
    for r in records:
        node=after[r['index']];kind=str(node[0])
        if kind!=('gr_poly' if r['growing'] else 'gr_circle'):raise ValueError('TARGET_NATIVE_KIND_CHANGED:'+r['key'])
        if str(one(node,'layer',[''])[0])!='F.Cu':raise ValueError('TARGET_NATIVE_LAYER_CHANGED')
        g=geometry(node,kind);expected=targets[r['source_id']]
        result=fidelity(expected,g) if r['growing'] else fidelity(expected,g,native_circle=True)
        rows.append(dict(key=r['key'],source_id=r['source_id'],alias=r['alias'],growing=r['growing'],**result))
    return dict(passed=True,source_occurrences=len(rows),canonical_sites=len({r['source_id'] for r in rows}),modified_occurrences=len(changed),protected_top_level_nodes=len(before)-1-len(changed),preservation='All non-target native nodes semantically equal; byte identity is not required',targets=rows)

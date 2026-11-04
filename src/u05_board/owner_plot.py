"""Fresh isolated native stroke plotting, then exact bulk-plot atom membership."""
import json
from pathlib import Path
import sexpdata
from shapely import from_wkb,STRtree
from src.stage_abi.store import canonical,digest
from src.pcb_data_abi import gerber,board_native as native
from src.pcb_data_abi.service import CLI,CLI_SHA,fresh
from .stroke_owner import primitive_match,stroke_fidelity,STROKE_GEOMETRY_BOUND_MM

def plot_atom(obj):return json.loads(json.dumps(gerber.atom(obj),allow_nan=False))

def source_body(tree,records):
    metadata={'version','generator','generator_version','general','paper','layers','setup','net','net_class','embedded_fonts'}
    prefix=[n for n in tree[1:] if isinstance(n,list) and str(n[0]) in metadata]
    return native.board_bytes([tree[0],*prefix,*[r['node'] for _,r in sorted(records.items())]])

def check_role(parsed):
    if parsed.file_attrs.get('.FileFunction')!=('Copper','L1','Top') or parsed.file_attrs.get('.FilePolarity')!=('Positive',):raise ValueError('U05_OWNER_SOURCE_PLOT_ROLE_CHANGED')

def sources(service):
    tree=sexpdata.loads(service.raw.decode());records={}
    for row in service.rows.values():
        md=row['metadata']
        if row['kind']!='trace':continue
        for sid,kind in md['native_part_kinds'].items():
            if kind not in ('segment','gr_line','arc','gr_arc'):continue
            source=service.rows.get(sid);index=source['metadata']['native_node_indices'][0] if source else md['native_node_indices'][sorted(md['native_part_refs']).index(sid)]
            node=tree[index]
            if str(node[0])!=kind:raise ValueError('U05_OWNER_SOURCE_KIND_CHANGED')
            records[sid]=dict(node_index=index,node_sha256=digest(native.encode(node).encode()),geometry_ref=md['native_part_refs'][sid],node=node)
    return tree,records

def create(service):
    tree,records=sources(service);folder=service.out/'owner_source_plot';folder.mkdir();body=source_body(tree,records);board=folder/'board.kicad_pcb';fresh(board,body);plots=folder/'gerbers';plots.mkdir()
    service.command([CLI,'pcb','export','gerbers','--layers','F.Cu','--precision','6','--no-protel-ext','-o',str(plots)+'/',board],'owner_source_export')
    if board.read_bytes()!=body:raise ValueError('U05_OWNER_SOURCE_CHANGED_BY_EXPORT')
    parsed=gerber.parse(plots/'board-F_Cu.gbr');check_role(parsed);geoms=[gerber.native_geometry(o) for o in parsed.objects];spatial=STRtree(geoms);used=set();bindings={}
    if len(parsed.objects)!=len(records):raise ValueError('U05_OWNER_SOURCE_PLOT_ATOM_COVERAGE')
    for sid,r in sorted(records.items()):
        shape=from_wkb(service.store.get(r['geometry_ref'],kind='geometry'));matches=[]
        for i in sorted(map(int,spatial.query(shape.envelope.buffer(STROKE_GEOMETRY_BOUND_MM)))):
            if i in used or not primitive_match(r['node'],parsed.objects[i],require_center=False):continue
            try:proof=stroke_fidelity(shape,geoms[i])
            except ValueError:continue
            matches.append((i,proof))
        if not matches:raise ValueError('U05_ISOLATED_SOURCE_STROKE_BINDING_FAILED:'+sid)
        i,proof=matches[0];used.add(i);bindings[sid]=dict(native_node_index=r['node_index'],native_node_sha256=r['node_sha256'],geometry_ref=r['geometry_ref'],isolated_plot_index=i,exact_plot_atom=plot_atom(parsed.objects[i]),geometry=proof)
    if used!=set(range(len(parsed.objects))):raise ValueError('U05_OWNER_SOURCE_UNBOUND_ATOM')
    value=dict(schema='u05-owner-source-plot/1',native_U04_sha256=digest(service.raw),cli_sha256=CLI_SHA,source_nodes=len(records),all_source_occurrences_bound=True,bindings=bindings,files={str(p.relative_to(service.out)):digest(p.read_bytes()) for p in folder.rglob('*') if p.is_file()})
    for suffix in ('.command.json','.stdout.txt','.stderr.txt'):
        p=service.out/('owner_source_export'+suffix);value['files'][p.name]=digest(p.read_bytes())
    fresh(folder/'RECEIPT.json',canonical(value));return dict(receipt=str(folder/'RECEIPT.json'),sha256=digest((folder/'RECEIPT.json').read_bytes()),source_nodes=len(records))

def binding(service):
    exported=json.loads((service.out/'pcb_gerber_export.json').read_bytes());bound=exported['owner_source_plot'];path=Path(bound['receipt'])
    if digest(path.read_bytes())!=bound['sha256']:raise ValueError('U05_OWNER_SOURCE_PLOT_RECEIPT_CHANGED')
    value=json.loads(path.read_bytes())
    if value['native_U04_sha256']!=digest(service.raw) or value['cli_sha256']!=CLI_SHA:raise ValueError('U05_OWNER_SOURCE_PLOT_INPUT_CHANGED')
    for name,h in value['files'].items():
        if digest((service.out/name).read_bytes())!=h:raise ValueError('U05_OWNER_SOURCE_PLOT_EVIDENCE_CHANGED')
    # Every occurrence's native node and source geometry remain bound at reuse.
    if not hasattr(service,'_owner_plot_sources'):
        tree,expected=sources(service);service._owner_plot_sources=expected;service._owner_source_body=source_body(tree,expected)
    expected=service._owner_plot_sources
    if (service.out/'owner_source_plot/board.kicad_pcb').read_bytes()!=service._owner_source_body:raise ValueError('U05_OWNER_SOURCE_NATIVE_RECONSTRUCTION_FAILED')
    command=json.loads((service.out/'owner_source_export.command.json').read_bytes());argv=list(map(str,[CLI,'pcb','export','gerbers','--layers','F.Cu','--precision','6','--no-protel-ext','-o',str(service.out/'owner_source_plot/gerbers')+'/',service.out/'owner_source_plot/board.kicad_pcb']))
    if command['exit_status']!=0 or command['cli_sha256']!=CLI_SHA or command['argv']!=argv:raise ValueError('U05_OWNER_SOURCE_NATIVE_COMMAND_CHANGED')
    parsed=gerber.parse(service.out/'owner_source_plot/gerbers/board-F_Cu.gbr');check_role(parsed);used=set()
    if value['source_nodes']!=len(expected) or len(parsed.objects)!=len(expected):raise ValueError('U05_OWNER_SOURCE_PLOT_ATOM_COVERAGE')
    if sorted(value['bindings'])!=sorted(expected):raise ValueError('U05_OWNER_SOURCE_PLOT_INVENTORY_CHANGED')
    for sid,r in expected.items():
        b=value['bindings'][sid]
        if b['native_node_index']!=r['node_index'] or b['native_node_sha256']!=r['node_sha256'] or b['geometry_ref']!=r['geometry_ref']:raise ValueError('U05_OWNER_SOURCE_PLOT_BINDING_CHANGED')
        i=b['isolated_plot_index']
        if i in used or not 0<=i<len(parsed.objects) or canonical(plot_atom(parsed.objects[i]))!=canonical(b['exact_plot_atom']) or not primitive_match(r['node'],parsed.objects[i],require_center=False):raise ValueError('U05_OWNER_SOURCE_ATOM_RECONSTRUCTION_FAILED')
        used.add(i);shape=from_wkb(service.store.get(r['geometry_ref'],kind='geometry'))
        if stroke_fidelity(shape,gerber.native_geometry(parsed.objects[i]))!=b['geometry']:raise ValueError('U05_OWNER_SOURCE_GEOMETRY_RECONSTRUCTION_FAILED')
    return value

"""U03 crop T03: same retained-path predicates, crop-selected fresh T01 sites."""
from pathlib import Path
from shapely import from_wkb,to_wkb,STRtree
from src.stage_abi.store import canonical,digest
from src.t01_crop.paging import read_pages
from src.crop_balanced_t01 import WorkingScene,CropSettings
from src.u02_board.adapter import RetainPathsAdapter,pair_check,TRACE_KINDS
from .crop_t01 import context

class CropRetainPathsAdapter(RetainPathsAdapter):
    def assess(self):
        original=self.store.get_json(self.receipt['scene_ref'],kind='scene')
        policy=self.store.get_json(self.cap['policy_ref'],kind='policy')
        b,raw,rows,shapes,sites=context(self.store,original,policy)
        if policy['settings']['hard_gap']!=self.policy['hard_gap_mm'] or policy['settings']['area_epsilon']!=self.policy['area_epsilon_mm2'] or policy['settings']['qsegs']!=self.policy['quad_segs']:raise ValueError('U02_POLICY_DRIFT')
        current={r['source_id']:r for r in self.scene['objects']};old={r['source_id']:r for r in original['objects']}
        if set(current)!=set(old) or len(current)!=len(self.scene['objects']) or self.scene['source_sha256']!=b['source_sha256'] or self.scene['lineage'][-1]['stage']!='t01' or self.scene['lineage'][-1]['plan_ref']!=self.cap['plan_ref']:raise ValueError('U02_PREDECESSOR_COVERAGE_CHANGED')
        expected={sid:dict(row,geometry_ref=self.candidate['replacements'].get(sid,row['geometry_ref'])) for sid,row in old.items()}
        if current!=expected:raise ValueError('U02_EXACT_T01_PREDECESSOR_REQUIRED')
        ws=WorkingScene(raw,rows,shapes,sites,CropSettings(**policy['settings']))
        plan=self.store.get_json(self.cap['plan_ref'],kind='plan');ports=plan['details']['allocation']['ports']
        port_rows,index=read_pages(self.store,ports['index_ref'],binding=dict(source_sha256=b['source_sha256'],site_ids_sha256=digest(canonical(sorted(s['source_id'] for s in sites))),viewport_mm=b['viewport_mm']),kind='t01-board-ports',identity=lambda r:r['source_id'])
        stored={r['source_id']:{sid:self.store.get(ref,kind='t01-port-geometry') for sid,ref in r['ports'].items()} for r in port_rows}
        regenerated={sid:{oid:to_wkb(g,byte_order=1) for oid,g in zones.items()} for sid,zones in ws.ports.items()}
        if stored!=regenerated:raise ValueError('U02_SOURCE_PORT_RECONSTRUCTION_MISMATCH')
        traces=[(r,g) for r,g in zip(rows,shapes) if r['kind'] in TRACE_KINDS]
        if not traces:raise ValueError('U02_NATIVE_TRACE_INVENTORY_EMPTY')
        records=[]
        for row,g in traces:
            sid=row['id'];start,end=row['source_span'];native=raw[start:end]
            if row['trace_width_mm'] is None or row['trace_width_mm']<=0:raise ValueError('U02_TRACE_WIDTH_UNRESOLVED:'+sid)
            if current[sid]['geometry_ref']!=old[sid]['geometry_ref'] or digest(self.store.get(current[sid]['geometry_ref'],kind='geometry'))!=row['geometry_sha256']:raise ValueError('U02_TRACE_CHANGED:'+sid)
            records.append(dict(source_id=sid,native_kind=row['kind'],source_span=[start,end],native_bytes_sha256=digest(native),geometry_sha256=row['geometry_sha256'],original_width_mm=row['trace_width_mm'],disposition='RETAIN_ORIGINAL',pairs=[]))
        tree=STRtree([g for _,g in traces]);byid={r['source_id']:r for r in records}
        for site in sites:
            target=from_wkb(self.store.get(current[site['source_id']]['geometry_ref'],kind='geometry'))
            for i in sorted(map(int,tree.query(target.buffer(self.policy['hard_gap_mm']+.000001)))):
                row,g=traces[i];sid=row['id'];port=ws.ports[site['source_id']].get(sid)
                q=pair_check(site['core'],target,g,port,self.policy)
                byid[sid]['pairs'].append(dict(site_source_id=site['source_id'],**q))
        coverage=dict(source_objects=len(rows),site_occurrences=sum(len(s['aliases']) for s in sites),canonical_sites=len(sites),source_pages=(len(rows)+99)//100,port_pages=len(index['pages']),source_sha256=b['source_sha256'])
        return records,coverage


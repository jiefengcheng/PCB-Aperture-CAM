"""Explicit C03 unchanged-route proof with original generic failures retained."""
from shapely import to_wkb
from src.c03_input_family import retention_proof, selected, FAMILY, specification
from src.c03_round_adapter import context
from src.stage_abi.store import canonical, digest
from src.t01_crop.paging import read_pages,store_pages
from src.u02_board.adapter import RetainPathsAdapter
from src.u03_board.selection import window
from tools.t01_operator_host import fresh


class C03RetainPathsAdapter(RetainPathsAdapter):
    def __init__(self, root):
        if not selected(root):
            raise ValueError('C03_EXPLICIT_JOB_SELECTION_REQUIRED')
        super().__init__(root)
        _, _, sha = specification()
        self.binding.update(input_contact_family=FAMILY, input_contract_sha256=sha)

    def inspect(self):
        self.out.mkdir(exist_ok=False)
        records,coverage=self.assess()
        reference=store_pages(self.store,records,binding=self.binding,kind='u02-traces')
        saved,index=read_pages(self.store,reference,binding=self.binding,kind='u02-traces',identity=lambda r:r['source_id'])
        if saved!=records:raise ValueError('U02_TRACE_PAGINATION_CHANGED')
        # Keep complete ledgers in immutable evidence. The mailbox carries a
        # hash-bound summary, preserving its original 64 KiB request limit.
        facts=dict(passed=True,trace_occurrences=len(records),trace_pages=len(index['pages']),
            affected_pairs=sum(len(r['pairs']) for r in records),
            movement_objectives=sum(any(not p['passed'] for p in r['pairs']) for r in records),
            complete_source_coverage=True,original_widths_retained=True,
            **{k:coverage[k] for k in ('source_objects','site_occurrences','canonical_sites',
               'source_pages','port_pages','source_sha256','input_contact_family',
               'input_contract_sha256','full_visible_surface_check_sha256')},
            complete_coverage_sha256=digest(canonical(coverage)),
            retained_generic_failure_pairs=len(coverage['retained_generic_source_port_failures']),
            original_full_coverage_pass=coverage['original_obligations']['original_full_coverage_pass'],
            blocked_original_positive=coverage['original_obligations']['blocked_original_positive'])
        result=dict(binding=self.binding,trace_inventory_ref=reference,coverage=coverage,facts=facts)
        fresh(self.out/'t03_inspect.json',result)
        return result

    def assess(self):
        original = self.store.get_json(self.receipt['scene_ref'], kind='scene')
        policy = self.store.get_json(self.cap['policy_ref'], kind='policy')
        binding, raw, rows, shapes, sites = context(self.store, original, policy)
        if (policy['settings']['hard_gap'] != self.policy['hard_gap_mm'] or
                policy['settings']['area_epsilon'] != self.policy['area_epsilon_mm2'] or
                policy['settings']['qsegs'] != self.policy['quad_segs']):
            raise ValueError('U02_POLICY_DRIFT')
        old = {r['source_id']:r for r in original['objects']}
        current = {r['source_id']:r for r in self.scene['objects']}
        if (len(current) != len(self.scene['objects']) or
                self.scene['source_sha256'] != binding['source_sha256'] or
                self.scene['lineage'][-1]['stage'] != 't01' or
                self.scene['lineage'][-1]['plan_ref'] != self.cap['plan_ref']):
            raise ValueError('U02_PREDECESSOR_COVERAGE_CHANGED')
        expected = {sid:dict(r, geometry_ref=self.candidate['replacements'].get(sid,r['geometry_ref']))
                    for sid,r in old.items()}
        if current != expected:
            raise ValueError('U02_EXACT_T01_PREDECESSOR_REQUIRED')
        original_blobs = {sid:self.store.get(r['original_ref'],kind='geometry') for sid,r in old.items()}
        current_blobs = {sid:self.store.get(r['geometry_ref'],kind='geometry') for sid,r in current.items()}
        proof = retention_proof(raw,self.store.get_json(binding['manifest_ref'],kind='native-manifest'),
                                original_blobs,current_blobs,sites,window(binding['u03_selection']))
        plan = self.store.get_json(self.cap['plan_ref'],kind='plan')
        ports = plan['details']['allocation']['ports']
        stored,index = read_pages(self.store,ports['index_ref'],binding=dict(
            source_sha256=binding['source_sha256'],
            site_ids_sha256=digest(canonical(sorted(s['source_id'] for s in sites))),
            viewport_mm=binding['viewport_mm']),kind='t01-board-ports',identity=lambda r:r['source_id'])
        actual = {r['source_id']:{sid:self.store.get(ref,kind='t01-port-geometry').hex()
                               for sid,ref in r['ports'].items()} for r in stored}
        if actual != proof['ports']:
            raise ValueError('U02_SOURCE_PORT_RECONSTRUCTION_MISMATCH')
        coverage = dict(source_objects=len(rows),site_occurrences=sum(len(s['aliases']) for s in sites),
            canonical_sites=len(sites),source_pages=(len(rows)+99)//100,port_pages=len(index['pages']),
            source_sha256=binding['source_sha256'],input_contact_family=FAMILY,
            input_contract_sha256=proof['contract_sha256'],
            full_visible_surface_check_sha256=digest(canonical(proof['complete_visible_surface'])),
            retained_generic_source_port_failures=proof['retained_generic_source_port_failures'],
            original_obligations=proof['original_obligations'])
        return proof['trace_records'],coverage

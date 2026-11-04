"""U04 preserves reviewed original-source roles while reusing U03 width gates."""
from src.u03_board.adapter import *
from src.u03_board.adapter import WidthGates as BaseWidthGates
from src.u04_board.roles import qualify,CONTRACT

class WidthGates(BaseWidthGates):
    def __init__(self,root):
        super().__init__(root)
        self.binding['reviewed_source_roles_sha256']=digest(CONTRACT.read_bytes())

    def inspect(self):
        self.out.mkdir()
        report=qualify(self.raw,self.manifest['objects'],self.original,self.current,selection=for_root(self.root))
        paths=[dict(record_id=str(i),**r) for i,r in enumerate(report['paths'])]
        relations=[dict(record_id=str(i),**r) for i,r in enumerate([*report['relations'],*report['blocked_relations']])]
        refs={};counts={}
        for field,kind,rows in [('source','u03-width-sources',report['native_rows']),('path','u03-width-paths',paths),('group','u03-width-groups',report['groups']),('relation','u03-width-relations',relations)]:
            ref=put_pages(self.store,rows,binding=self.binding,kind=kind);refs[field+'_pages_ref']=ref
            counts[field+'_pages']=(len(rows)+99)//100
        return self.save('t04_inspect',dict(binding=self.binding,report_ref=self.store.put_json('u03-admission',report),
            path_records=paths,relation_records=relations,**refs,
            facts=dict(passed=True,trace_occurrences=report['trace_occurrences'],source_objects=report['source_objects'],
                       paths=len(paths),admitted_paths=len(report['admitted_paths']),groups=len(report['groups']),unsupported=len(report['unsupported']),
                       classifications=report['classifications'],complete_source_coverage=True,**counts)))

    def verify(self):
        saved,report=self.inspection();actual=qualify(self.raw,self.manifest['objects'],self.original,self.current,selection=for_root(self.root))
        if actual!=report:raise ValueError('U03_WIDTH_FRESH_ADMISSION_RECONSTRUCTION_FAILED')
        p=read(self.out/'t04_plan.json');run=read(self.out/'t04_run.json')
        from src.u03_board.solver import validate_ledger
        validate_ledger(self.store,run['result']['candidate'])
        proof=self.store.put_json('proof-scope',dict(scope='complete-source-nominal-envelope-and-upper-proofs'))
        result=self.call('verify',dict(candidate_ref=run['result']['candidate_ref'],verifier_ref=read(self.out/'t04_admit.json')['registry']['profiles'][PROFILE]['verifier_ref'],proof_scope_ref=proof),
            plan_ref=p['plan_ref'],authorization_ref=p['authorization_ref'],idempotency_key='fresh-u03-width-verification')
        v=result['result']['verification']
        if result['reused'] or v['geometric_status']!='PASS' or not all(r['proved'] for r in v['check']['maximum_proofs']):raise ValueError('U03_WIDTH_VERIFICATION_FAILED')
        return self.save('t04_verify',dict(result=result['result'],binding=self.binding,
            facts=dict(run['facts'],passed=True,fresh_reconstruction=True,nominal_pass=True,envelope_pass=True,
                       complete_source_coverage=True,coordinatewise_maximum=True,owner='PENDING_USER')))


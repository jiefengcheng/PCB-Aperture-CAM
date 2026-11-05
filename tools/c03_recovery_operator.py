"""C03 delivery keeps original coverage and generic failures explicit."""
from tools.u04_board_auto_operator import MachineOperator
from tools.t01_operator_host import read,fresh
from src.stage_abi.store import digest


class C03MachineOperator(MachineOperator):
    def delivery(self):
        result=super().delivery();root=self.client.root
        cap=read(sorted(root.glob('capsule_*.json'))[-1])
        from src.stage_abi.store import ArtifactStore
        store=ArtifactStore(root/'runtime')
        t01=store.get_json(read(root/'RECEIPT.json')['candidate_ref'],kind='candidate')
        coverage=t01['original_coverage']
        inspection=read(root/'u02_t03/t03_inspect.json')['coverage']
        receipt=dict(schema='c03-recovery-native-family-receipt/1',status='PASS_BOUNDED_C03_NATIVE_FAMILY',
            underlying_u04_receipt_sha256=digest((root/'U04_RECEIPT.json').read_bytes()),
            input_contact_family=inspection['input_contact_family'],
            original_round_coverage=coverage,
            blocked_original_obligations=['T01:C028','T02:R304','T02:R305'],
            retained_generic_failure_pairs=len(inspection['retained_generic_source_port_failures']),
            source_scope='Fresh native qualification of explicitly supplied retained original-source snapshot',
            full_original_recovery='NOT_ESTABLISHED',owner='PENDING_USER',
            independent='NOT_RUN: CHANNEL_UNAVAILABLE',electrical_manufacturing='NOT_ESTABLISHED')
        path=root/'C03_RECOVERY_RECEIPT.json';fresh(path,receipt)
        text=(f"Bounded C03 native family: {len(self.steps)} native gates and deterministic machine audits passed; zero human/agent observations.\n\n"
            f"Round treatment: {t01['counts']['ROUND_CLASS_GROWN']} original positives constructed; C028 remains blocked in the original 121-positive denominator. R304/R305 also remain blocked. The safe boundary is unchanged. Full original recovery remains NOT_ESTABLISHED.\n\n"
            f"All {len(inspection['retained_generic_source_port_failures'])} generic source-port failures are retained as failures; generic U02 is unchanged. This is qualification of the separate exact C03 family. Native write/reread, nine-layer export/reparse and corruption checks passed.\n\n"
            f"[KiCad]({result['kicad']}) · [F.Cu Gerber]({result['gerber']}) · [C03 receipt]({path}) · [Underlying gate evidence]({root/'U04_EXPORT_CHECKPOINT.json'})\n\n"
            "Input: retained original-source snapshot, freshly qualified through native intake. Rendering NOT_REQUESTED. Owner PENDING_USER; independent NOT_RUN: CHANNEL_UNAVAILABLE; electrical/manufacturing NOT_ESTABLISHED. No acceptance promotion.")
        report=root/'C03_RECOVERY_REPORT.md';report.write_text(text)
        for p in (path,report):
            result['files'].append(dict(path=str(p),sha256=digest(p.read_bytes()),bytes=p.stat().st_size,format=p.suffix))
        return dict(result,report=str(report),ready_markdown=text,report_text=text,c03_receipt=str(path),full_original_recovery='NOT_ESTABLISHED')

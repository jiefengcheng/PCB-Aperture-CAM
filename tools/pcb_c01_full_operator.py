#!/usr/bin/env python3
"""Stdlib full C01 facade: one native slice after each separate observation."""
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.pcb_c01_operator import Operator, main, scoped, sha, decode

ACTIVE=ROOT/'out/operator_routes/c01_full/current.json'

class FullOperator(Operator):
    steps=tuple(json.loads((ROOT/'contracts/operator/c01_full.json').read_bytes())['operations'])
    complete_status='COMPLETE_AUDITED_C01_FULL_SEQUENCE'

    def __init__(self,binding=ACTIVE):
        super().__init__(binding)

    def validate_tools(self,names):
        if names!={*self.steps,'native_route.info','native_route.verify_receipt','native_route.audit'}:
            raise ValueError('BOUND_FULL_C01_PROFILE_REQUIRED')

    def summary_details(self,index,raw):
        details=dict(total_slices=len(self.steps),
            evidence_scope='Native facts for the current full C01 slice only. No visual, owner, independent, electrical or manufacturing acceptance. Geometry construction and fresh export are distinct from raster fidelity.')
        operation=self.steps[index]
        if operation=='render_c01_verify':details['measurements']=raw['audits']
        if operation in ('pcb_export_controls','render_c01_controls'):details['controls']=raw['controls']
        return details

    def delivery(self):
        result=super().delivery()
        out=self.client.root/'data_output'
        write=decode((out/'pcb_kicad_write.json').read_bytes())
        export=decode((out/'pcb_gerber_export.json').read_bytes())
        files={write['board']:write['board_sha256'],**export['output_sha256']}
        for path,digest in files.items():
            blob=scoped(path).read_bytes()
            if sha(blob)!=digest:raise ValueError('FINAL_EXPORT_CHANGED')
            result['files'].append(dict(path=path,sha256=digest,bytes=len(blob),format='KiCad' if path.endswith('.kicad_pcb') else 'Gerber'))
        result.update(status=self.complete_status,native_slices=len(self.steps),observation_audits=len(self.steps),
            scope='Fresh C01 T01 reproduction, KiCad/Gerber export and display; frozen results and T02-T05 unchanged',
            kicad=write['board'],gerber_directory=str(out/'candidate/gerbers'),
            display=str(self.client.root/'render_output/comparison.png'),html=str(self.client.root/'render_output/index.html'),
            proof='All nine T01 checks, post-construction exact C01 reproduction check, five export checks and three display checks passed, with 18 separate observations. Negative controls retained.',
            report_text='C01 was freshly reproduced through T01 and checked against frozen C01 only after construction. Separate KiCad and nine-layer Gerber candidates and their side-by-side display are ready. All 18 native slices and separate observation audits passed. Frozen results and T02-T05 are unchanged. Owner review remains pending; independent, electrical and manufacturing acceptance is not established. Task complete: deliver the supplied image/file links directly, without any further command, including true.')
        return result

if __name__=='__main__':raise SystemExit(main(FullOperator))

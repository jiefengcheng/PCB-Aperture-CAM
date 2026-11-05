"""C03 adds a dark-copper requirement to all inherited export checks."""
from pathlib import Path
from src.c03_input_family import selected
from src.pcb_data_abi import gerber
from src.pcb_data_abi.service import fresh
from src.u04_board.export import U04DataService
from tools.t01_operator_host import read


def require_positive_copper(*plots):
    if any(not obj.polarity_dark for plot in plots for obj in plot.objects):
        raise ValueError('C03_FCU_CLEAR_POLARITY_UNSUPPORTED')


class C03DataService(U04DataService):
    def __init__(self,host):
        super().__init__(host)
        if not selected(self.previous):raise ValueError('C03_EXPLICIT_JOB_SELECTION_REQUIRED')

    def plot_check(self,candidate_fcu=None):
        exported=read(self.out/'pcb_gerber_export.json')['exports']
        require_positive_copper(gerber.parse(exported['before']['F.Cu']),
            gerber.parse(candidate_fcu or exported['candidate']['F.Cu']))
        measured,geometries,parsed=super().plot_check(candidate_fcu)
        measured['c03_positive_copper_required']=True
        return measured,geometries,parsed

    def finish(self,name,value):
        if name=='pcb_export_controls':
            source=Path(read(self.out/'pcb_gerber_export.json')['exports']['candidate']['F.Cu'])
            blob=source.read_bytes()
            if b'%LPD*%' not in blob:raise ValueError('C03_DARK_CONTROL_SOURCE_TOKEN_MISSING')
            path=self.out/'controls/clear_polarity.gbr'
            fresh(path,blob.replace(b'%LPD*%',b'%LPC*%',1))
            try:self.plot_check(path)
            except ValueError as error:
                if not str(error).startswith('C03_FCU_CLEAR_POLARITY_UNSUPPORTED'):raise
                control=dict(name='clear_polarity',expected='C03_FCU_CLEAR_POLARITY_UNSUPPORTED',
                    error=str(error),status='PASS_EXPECTED_REJECTION')
            else:raise ValueError('C03_CLEAR_POLARITY_CONTROL_NOT_REJECTED')
            value=dict(value,controls=[*value['controls'],control],
                facts=dict(value['facts'],deliberate_controls=len(value['controls'])+1))
        return super().finish(name,value)


def data_service(root,host):
    return C03DataService(host) if selected(root) else U04DataService(host)

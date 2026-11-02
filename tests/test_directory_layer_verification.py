"""Every supplied raw Gerber must match fresh native source plotting; extras cannot disappear."""
from pathlib import Path
import pytest
from src.pcb_data_abi.directory_scope import DirectoryScopeService
from src.pcb_data_abi.board_scope import BoardScopeService


def body(role,coordinate='1000000'):
    return f'''%FSLAX46Y46*%\n%MOMM*%\n%TF.FileFunction,{role}*%\n%TF.FilePolarity,Positive*%\n%TF.SameCoordinates,Original*%\n%ADD10C,0.1*%\nD10*\nG36*\nX0Y0D02*\nX{coordinate}Y0D01*\nX{coordinate}Y1000000D01*\nX0Y1000000D01*\nX0Y0D01*\nG37*\nM02*\n'''


@pytest.mark.parametrize('bad',[False,True])
def test_additional_layer_is_parsed_and_compared_in_source_gate(tmp_path,monkeypatch,bad):
    s=DirectoryScopeService.__new__(DirectoryScopeService);s.out=tmp_path/'native';s.out.mkdir();s.inputs=dict(kicad=tmp_path/'board.kicad_pcb');fcu=tmp_path/'fcu.gbr';back=tmp_path/'back.gbr';fcu.write_text(body('Copper,L1,Top'));back.write_text(body('Copper,L2,Bot','900000'if bad else'1000000'));s.paths=dict(kicad=s.inputs['kicad'],**{'F.Cu':fcu,'B.Cu':back})
    monkeypatch.setattr(BoardScopeService,'verify_inputs',lambda self:dict(facts=dict(passed=True,source_objects=1),generated_source_gerber=str(fcu)))
    calls=[]
    def native(argv,stem):
        calls.append(argv);folder=s.out/'additional_source_layers';(folder/'arbitrary.gbr').write_text(body('Copper,L2,Bot'))
    s.command=native
    if bad:
        with pytest.raises(ValueError,match='KICAD_GERBER_MISMATCH:B.Cu'):s.verify_inputs()
        assert not(s.out/'directory_inputs_verified.json').exists()
    else:
        result=s.verify_inputs();assert result['facts']['provided_gerber_files']==2 and result['facts']['all_supplied_layers_verified']
    assert len(calls)==1 and 'gerbers'in calls[0]and all('png'not in str(arg)and 'svg'not in str(arg)for arg in calls[0])


def test_native_preferences_are_written_beside_work_copy_not_raw_snapshot(tmp_path,monkeypatch):
    from src.pcb_data_abi.roi import ROIService
    from src.pcb_data_abi.service import CLI
    s=DirectoryScopeService.__new__(DirectoryScopeService);s.out=tmp_path/'native';s.out.mkdir();raw=tmp_path/'raw/explicit.kicad_pcb';raw.parent.mkdir();raw.write_bytes(b'original KiCad');s.inputs=dict(kicad=raw)
    seen=[]
    def native(self,argv,stem):
        seen.append(argv);p=Path(argv[-1]);p.with_suffix('.kicad_prl').write_text('KiCad preference side effect');return 'native export done'
    monkeypatch.setattr(ROIService,'command',native)
    assert s.command([CLI,'pcb','export','gerbers','--layers','F.Cu',raw],'export')=='native export done'
    assert seen[0][-1]==s.out/'native_source_work/board.kicad_pcb'and raw.read_bytes()==b'original KiCad'
    assert not raw.with_suffix('.kicad_prl').exists()and seen[0][-1].with_suffix('.kicad_prl').exists()

"""Board Gerber verification must exercise and protect every non-copper layer."""
import json
from types import SimpleNamespace
import pytest
from src.pcb_data_abi import board_export as module
from src.pcb_data_abi.service import LAYERS

@pytest.mark.parametrize('corrupt',[False,True])
def test_board_plot_check_verifies_all_eight_protected_layers(tmp_path,monkeypatch,corrupt):
    service=module.BoardDataService.__new__(module.BoardDataService);service.out=tmp_path;service.decisions=[];service.targets={};service.receipt=dict(scene_ref={});service.store=SimpleNamespace(get_json=lambda *a,**k:dict(objects=[]))
    paths={side:{layer:str(tmp_path/(side+'-'+layer+'.gbr'))for layer in LAYERS}for side in('before','candidate')};(tmp_path/'pcb_gerber_export.json').write_text(json.dumps(dict(exports=paths)))
    called=[]
    def parse(path):
        called.append(path);role=('Copper','L1','Top')if path.endswith('F.Cu.gbr')else('Protected',)
        if corrupt and path==paths['candidate'][LAYERS[-1]]:role=('Altered',)
        return SimpleNamespace(objects=[],file_attrs={'.FileFunction':role,'.FilePolarity':('Positive',)})
    monkeypatch.setattr(module.gerber,'parse',parse)
    if corrupt:
        with pytest.raises(ValueError,match='PROTECTED_LAYER_PLOT_CHANGED'):service.plot_check()
    else:
        result,_,_=service.plot_check();assert result['protected_layers_equal']==LAYERS[1:]and result['protected_fcu_atoms_equal']
    assert len(called)==2*len(LAYERS) and set(called)=={p for items in paths.values()for p in items.values()}

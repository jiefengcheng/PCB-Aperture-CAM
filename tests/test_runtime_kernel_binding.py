from pathlib import Path
import pytest
from src.runtime_kernel_binding import matches

def test_only_bound_original_and_prepared_revisions_are_admitted():
    import json
    root=Path(__file__).resolve().parents[1]
    value=json.loads((root/'contracts/runtime_preparation/kernel_binding.json').read_bytes())
    for name,row in value['kernels'].items():
        assert matches(root,name,row['original_sha256'])
        assert not matches(root,name,'0'*64)

def test_modified_binding_cannot_authorize_source(tmp_path):
    (tmp_path/'src').mkdir();(tmp_path/'src/kernel.py').write_bytes(b'changed')
    folder=tmp_path/'contracts/runtime_preparation';folder.mkdir(parents=True);(folder/'kernel_binding.json').write_bytes(b'{}')
    with pytest.raises(ValueError,match='PREPARED_KERNEL_BINDING_CHANGED'):matches(tmp_path,'src/kernel.py','0'*64)

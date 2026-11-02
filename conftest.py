"""All repository pytest artifacts and temporary files belong on LaCie."""
import uuid
import pytest
from tools.pcb_workspace import configure,WORK

@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    configure()
    (WORK/'test_runs').mkdir(exist_ok=True)
    if config.option.basetemp:
        from pathlib import Path
        if not Path(config.option.basetemp).absolute().is_relative_to(WORK):
            raise pytest.UsageError('TEST_BASETEMP_MUST_BE_ON_LACIE')
    else:config.option.basetemp=str(WORK/'test_runs'/uuid.uuid4().hex)
    config._inicache['cache_dir']=str(WORK/'cache/pytest')

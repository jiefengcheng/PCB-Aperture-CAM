import pytest
from src import component_clearance as cc
@pytest.fixture(autouse=True)
def reset_component_context():
 old=cc.ACTIVE;cc.ACTIVE=None
 yield
 cc.ACTIVE=old

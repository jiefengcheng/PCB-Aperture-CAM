import pytest
from src import component_clearance as cc,t04_width_fence as fence
@pytest.fixture(autouse=True)
def reset_component_context():
 old=cc.ACTIVE;old_fence=fence.ACTIVE;cc.ACTIVE=None;fence.ACTIVE=None
 yield
 cc.ACTIVE=old;fence.ACTIVE=old_fence

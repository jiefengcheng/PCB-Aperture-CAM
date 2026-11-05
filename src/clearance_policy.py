"""Pinned production clearance defaults, independent of recognition tolerances.

Historical 0.020 mm contracts are evidence, not an alternate production mode.
Original source contacts retain their established, source-bound authority.
"""
import hashlib,json
from pathlib import Path
PATH=Path(__file__).resolve().parents[1]/'contracts/clearance/production.json'
SHA256='cab61452f4f1f99c99d2e1959b9de50c84569944728a4685d101810b78d67ac1'
def specification():
    raw=PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SHA256:
        raise ValueError('PRODUCTION_CLEARANCE_CONTRACT_CHANGED')
    return json.loads(raw)
def marker():return dict(schema='pcb-production-clearance/1',sha256=SHA256,hard_gap_mm=HARD_GAP_MM)
_SPEC=specification()
HARD_GAP_MM=_SPEC['hard_gap_mm']
CONSTRUCTION_GAP_MM=_SPEC['construction_gap_mm']
CONTACT_BUFFER_MM=_SPEC['original_contact_buffer_mm']
LEGACY_CONSTRUCTION_MM=_SPEC['t01_construction_gap_mm']
BARRIER_GAP_MM=_SPEC['spindle_barrier_gap_mm']
def weakened_english(raw):
    """Keep the negative compile control real after a numeric policy revision."""
    token=b'hard gap 0.040 mm'
    if raw.count(token)!=1:raise ValueError('NEGATIVE_ENGLISH_CONTROL_NOT_MUTATED')
    return raw.replace(token,b'hard gap 0.001 mm')

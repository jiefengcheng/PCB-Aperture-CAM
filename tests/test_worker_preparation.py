from dataclasses import replace
import pytest,sexpdata
from src.u05_board.worker_preparation import ParsePreparation,evaluation_preparation,native_loads,ACTIVE

TEXT='(kicad_pcb (version 20241229) (generator "unit") (x -0.0) (flag t) (name "µ"))'

def test_parse_hit_returns_exact_typed_fresh_tree_and_mutations_cannot_leak():
    c=ParsePreparation('worker-one',minimum_source_bytes=0)
    first=c.loads(TEXT);expected=sexpdata.loads(TEXT);first.append('mutated')
    second=c.loads(TEXT);assert second==expected and second is not first
    assert sexpdata.dumps(second)==sexpdata.dumps(expected)
    second[1].append('mutated-again');assert c.loads(TEXT)==expected
    assert c.stats['hits']==2

def test_every_source_byte_and_parse_options_remain_bound():
    c=ParsePreparation('one',minimum_source_bytes=0)
    assert c.loads(TEXT)==c.loads(TEXT+' ')
    assert c.stats['misses']==2 and c.stats['hits']==0
    assert c.loads('(t)',true='t')==sexpdata.loads('(t)',true='t')
    assert c.stats['bypassed_options']==1

def test_corrupt_internal_blob_rejects_before_unpickle():
    c=ParsePreparation('one',minimum_source_bytes=0);c.loads(TEXT)
    k=next(iter(c.values));c.values[k]=replace(c.values[k],blob=b'not a pickle')
    with pytest.raises(ValueError,match='PREPARATION_CORRUPTED'):c.loads(TEXT)

def test_corrupt_identity_rejects_at_final_verification_boundary():
    with pytest.raises(ValueError,match='PREPARATION_CORRUPTED'):
        with evaluation_preparation('one',minimum_source_bytes=0) as c:
            native_loads(TEXT);k=next(iter(c.values));c.values[k]=replace(c.values[k],source_sha256='0'*64)
    assert ACTIVE.get() is None and not c.values

def test_evaluations_have_fresh_caches_and_exception_release():
    for _ in range(2):
        with evaluation_preparation('same-attempt',minimum_source_bytes=0) as c:
            native_loads(TEXT);assert c.stats['misses']==1 and c.stats['hits']==0
        assert not c.values and not c.weight
    with pytest.raises(RuntimeError):
        with evaluation_preparation('failure',minimum_source_bytes=0) as c:
            native_loads(TEXT);raise RuntimeError('retained failure')
    assert ACTIVE.get() is None and not c.values

def test_nested_evaluation_rejects():
    with evaluation_preparation('one'):
        with pytest.raises(ValueError,match='NESTED_EVALUATION'):
            with evaluation_preparation('two'):pass

@pytest.mark.parametrize('limit,entries',[(0,0),(1024,1),(4096,2)])
def test_budget_eviction_disabled_cache_preserve_ast(limit,entries):
    c=ParsePreparation('one',limit=limit,entries=entries,minimum_source_bytes=0)
    for i in range(30):
        text=TEXT.replace('unit','unit'+str(i))
        assert c.loads(text)==sexpdata.loads(text)
        assert c.weight<=limit and len(c.values)<=entries
    if limit==0:assert not c.values

@pytest.mark.parametrize('bad',[-1,1.5,True,None])
def test_invalid_budget_rejects(bad):
    with pytest.raises(ValueError,match='PREPARATION_BUDGET'):ParsePreparation('one',limit=bad)

def test_malformed_source_retains_parser_rejection_and_no_entry():
    c=ParsePreparation('one',minimum_source_bytes=0)
    with pytest.raises(Exception):c.loads('(unterminated')
    assert not c.values

def test_no_context_falls_through_to_original_parser():
    assert native_loads(TEXT)==sexpdata.loads(TEXT)

def test_audit_predicate_body_and_both_process_evaluations_are_unchanged():
    import ast
    from pathlib import Path
    import json,hashlib
    root=Path(__file__).resolve().parents[1]
    pin=json.loads((root/'contracts/runtime_preparation/original_u05_audit.json').read_bytes())
    b=ast.parse((root/'src/u05_board/audit.py').read_text())
    changed=next(n for n in b.body if isinstance(n,ast.FunctionDef) and n.name=='_evaluate')
    assert hashlib.sha256(('\n'.join(ast.dump(n) for n in changed.body)).encode()).hexdigest()==pin['audit_body_ast_sha256']
    assert hashlib.sha256((root/'tools/pcb_u05_board_run.py').read_bytes()).hexdigest()==pin['runner_sha256']



def test_internal_pickler_memos_do_not_keep_caller_asts_alive():
    import weakref
    c=ParsePreparation('one',minimum_source_bytes=0)
    for _ in range(2):
        tree=c.loads(TEXT);ref=weakref.ref(tree[0]);del tree
        assert ref() is None

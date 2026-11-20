"""Public-only outer reader. The coordinator supplies trust through an FD."""
import base64,cProfile,json,os,pstats,sys,time
from pathlib import Path
from src.stage_abi.store import canonical
from src.t05_outer_acceptance import consume,file_bytes
from src.t05_outer_crypto import sha


def main():
    began=time.perf_counter();case=Path(sys.argv[1]);fd=int(sys.argv[2]);mode=sys.argv[3]
    with os.fdopen(fd,'rb')as stream:raw=stream.read(8193)
    if len(raw)>8192:raise ValueError('OUTER_PUBLIC_AUTHORITY_TOO_LARGE')
    authority=json.loads(raw);expected_raw=file_bytes(case/'EXPECTED.json')
    if sha(expected_raw)!=authority['expected_sha256']:raise ValueError('OUTER_COORDINATOR_EXPECTED_CHANGED')
    expected=json.loads(expected_raw);public=base64.b64decode(authority['public_anchor'],validate=True)
    if 'T05_OUTER_PRIVATE_FD'in os.environ:raise ValueError('OUTER_READER_RECEIVED_PRIVATE_CAPABILITY')
    package=json.loads(file_bytes(case/'OUTER_CERTIFICATE.json'))
    profile=cProfile.Profile();profile.enable()
    proof=consume(expected['run'],package,public,expected)
    profile.disable();profile.dump_stats(str(case/('CONSUMER_'+mode+'.prof')))
    # Structural proof of the actual profiled reader: no whole-stage/route
    # execution, owner blending, composition or physical rechecking occurred.
    forbidden={'compute','stage','build_source','_operands','_blend_addition','needs','outcomes','composed','_local_obstacles','spindle_addition','_check','union_all'}
    calls=[dict(file=f,line=line,name=name,calls=stats[1])for(f,line,name),stats in pstats.Stats(profile).stats.items()if name in forbidden and stats[1]]
    if calls:raise ValueError('OUTER_READER_RECONSTRUCTED:'+json.dumps(calls))
    proof.update(mode=mode,pid=os.getpid(),fresh_process_seconds=time.perf_counter()-began,
        forbidden_call_records=calls,authority_received_via='COORDINATOR_ANONYMOUS_FD_PUBLIC_ONLY')
    (case/('CONSUMER_'+mode+'.json')).write_bytes(canonical(proof))
    print(json.dumps(proof),flush=True)


if __name__=='__main__':main()

"""Content-bound, durable full-member parallel catalogue.

Source membership is independent of mutable cohorts, growth caps and budgets.
The old relationship catalogue is an input, not replaced or edited in place.
"""
import gzip,json,hashlib
from pathlib import Path
import shapely
from src.stage_abi.store import canonical,digest
from .group_membership import catalogue


def source_catalogue(directory,store,scene,rows,admission,roles,rule,loader):
    """Reuse the existing relationship reader/builder across job directories."""
    base=Path(__file__).resolve().parent
    dependencies=[base/n for n in('limiting_growth_v2.py','source_roles.py','_parallel_catalogue.py','_curve_catalogue.py')]
    key=dict(schema='t04-durable-source-relationships/1',scene_sha256=digest(canonical(scene)),
             role_table_sha256=rule['role_table_sha256'],
             implementation_sha256=digest(b''.join(p.read_bytes()for p in dependencies)),
             shapely_version=shapely.__version__,geos_version=shapely.geos_version_string)
    from src.cleanup_runtime import workspace_root
    directory=Path(directory)
    work=workspace_root()
    if not directory.resolve().is_relative_to(work) or directory.resolve()==work:
        raise ValueError('T04_DURABLE_ARTIFACT_REQUIRES_LACIE')
    root=directory/digest(canonical(key));hit=(root/'BINDING.json').exists()
    seed=Path(rule['group_cache']);imported=False
    if not root.exists()and(seed/'BINDING.json').exists():
        straight,curves,binding=loader(store,scene,rows,admission,roles,rule)
        root.mkdir(parents=True,exist_ok=False)
        for name in('GROUPS.json.gz','CURVE_GROUPS.json.gz'):
            raw=(seed/name).read_bytes()
            if binding['files'][name]!=digest(raw):raise ValueError('T04_GROUP_SEED_BYTES_CHANGED')
            (root/name).write_bytes(raw)
        (root/'BINDING.json').write_bytes(canonical(binding));imported=True
    else:
        directory.mkdir(parents=True,exist_ok=True)
        straight,curves,binding=loader(store,scene,rows,admission,roles,dict(rule,group_cache=str(root)))
    return straight,curves,binding,dict(cache_hit=hit,imported_seed=imported,directory=str(root.absolute()))


def retain(directory,key,name,build):
    """Publish a binding last; an incomplete or altered artifact is an error."""
    from src.cleanup_runtime import workspace_root
    directory=Path(directory)
    work=workspace_root()
    if not directory.resolve().is_relative_to(work) or directory.resolve()==work:
        raise ValueError('T04_DURABLE_ARTIFACT_REQUIRES_LACIE')
    root=directory/digest(canonical(key));header=root/'BINDING.json'
    hit=header.exists()
    if not hit:
        root.mkdir(parents=True,exist_ok=False)
        raw=gzip.compress(canonical(build()),mtime=0)
        (root/name).write_bytes(raw)
        header.write_bytes(canonical(dict(schema='t04-durable-source-artifact/1',key=key,
                                         files={name:digest(raw)})))
    binding=json.loads(header.read_bytes())
    if binding.get('schema')!='t04-durable-source-artifact/1'or binding.get('key')!=key:
        raise ValueError('T04_DURABLE_ARTIFACT_BINDING_CHANGED')
    raw=(root/name).read_bytes()
    if binding.get('files',{}).get(name)!=digest(raw):
        raise ValueError('T04_DURABLE_ARTIFACT_BYTES_CHANGED')
    value=json.loads(gzip.decompress(raw))
    return value,dict(binding=binding,binding_sha256=digest(header.read_bytes()),
                      directory=str(root.absolute())),hit


def prepare(directory,straight,curves,source_binding,*,noise_fraction=.01,minimum_shared_mm=.05):
    base=Path(__file__).resolve().parents[1]
    dependencies=[Path(__file__),Path(__file__).with_name('group_membership.py'),
                  base/'parallel_trace_relations.py',base/'primary_parallel_cohorts.py']
    signature=hashlib.sha256(b''.join(p.read_bytes()for p in dependencies)).hexdigest()
    key=dict(schema='t04-durable-full-member-catalogue/1',source_binding=source_binding,
             straight_sha256=digest(canonical(straight)),curve_sha256=digest(canonical(curves)),
             algorithm_sha256=signature,noise_fraction=noise_fraction,minimum_shared_mm=minimum_shared_mm,
             shapely_version=shapely.__version__,geos_version=shapely.geos_version_string)
    return retain(directory,key,'CATALOGUE.json.gz',lambda:catalogue(straight,curves,
                  noise_fraction=noise_fraction,minimum_shared_mm=minimum_shared_mm))

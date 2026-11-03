"""Verified image-file crop; complete features change, full source stays context."""
from collections import Counter
from pathlib import Path
from shapely import from_wkb
from shapely.geometry import box
from src.stage_abi.store import canonical, digest
from src.native_inventory import ERROR_MM
from tools.t01_operator_host import ROOT, read

def validate(value, source_sha256=None):
    from src.stage_abi.contracts import finite_json
    import math
    keys={'schema','crop_path','crop_sha256','source_sha256','bounds_mm','edge_uncertainty_mm','location_status','location_path','location_sha256','verification_path','verification_sha256'}
    if type(value) is not dict or set(value)!=keys or value['schema']!='pcb-u03-image-crop/1':
        raise ValueError('U03_CROP_SELECTION_INVALID')
    finite_json(value)
    if source_sha256 is not None and value['source_sha256']!=source_sha256:raise ValueError('U03_CROP_SOURCE_MISMATCH')
    b=value['bounds_mm'];e=value['edge_uncertainty_mm']
    if type(b) is not list or len(b)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in b) or type(e) not in (int,float) or e<0 or b[0]+e>=b[2]-e or b[1]+e>=b[3]-e:
        raise ValueError('U03_CROP_BOUNDS_INVALID')
    if value['location_status']!='PASS_NATIVE_ROI_LOCATION':raise ValueError('U03_CROP_LOCATION_NOT_VERIFIED')
    for field in ('crop','location','verification'):
        path=Path(value[field+'_path'])
        if not path.is_absolute() or not path.is_relative_to(ROOT/'out/lacie_work') or path.is_symlink() or digest(path.read_bytes())!=value[field+'_sha256']:
            raise ValueError('U03_CROP_EVIDENCE_CHANGED:'+field)
    location=read(Path(value['location_path']));verified=read(Path(value['verification_path']))
    witness=Path(value['verification_path']).with_name('crop_landmark_witness.json')
    if digest(witness.read_bytes())!=verified['landmark_witness_sha256']:raise ValueError('U03_CROP_LANDMARK_WITNESS_CHANGED')
    if (location['source_sha256']!=value['source_sha256'] or location['crop_sha256']!=value['crop_sha256'] or
        verified['bounds_mm']!=b or verified['uncertainty_mm']!=e or verified['location_sha256']!=value['location_sha256'] or verified['facts']['location_verified'] is not True):
        raise ValueError('U03_CROP_SELECTION_CHANGED')
    return value


def for_root(root):
    path=Path(root)/'U03_SELECTION.json'
    return validate(read(path)) if path.exists() else None


def retain_paths(root):
    if for_root(root) is not None:
        from .crop_t03 import CropRetainPathsAdapter
        return CropRetainPathsAdapter(root)
    from src.u02_board.adapter import RetainPathsAdapter
    return RetainPathsAdapter(root)


def window(value):
    validate(value)
    a,b,c,d=value['bounds_mm']; e=value['edge_uncertainty_mm']
    return box(a+e,b+e,c-e,d-e)


def select_sites(sites, selection):
    region=window(selection); selected=[]; records=[]
    for site in sites:
        x0,y0,x1,y1=site['core'].bounds; pad=.5*site['radius']+ERROR_MM
        cap=box(x0-pad,y0-pad,x1+pad,y1+pad)
        status='SELECT_COMPLETE_GROWTH_ENVELOPE' if region.covers(cap) else 'KEEP_CROP_BOUNDARY' if site['core'].intersects(box(*selection['bounds_mm'])) else 'KEEP_OUTSIDE_CROP'
        records.append(dict(source_id=site['source_id'], aliases=site['aliases'], disposition=status))
        if status=='SELECT_COMPLETE_GROWTH_ENVELOPE':selected.append(site)
    if not selected:raise ValueError('U03_CROP_NO_COMPLETE_CIRCLE_FEATURES')
    return selected, records


def restrict_width(report, blobs, selection):
    validate(selection, report['source_sha256']); region=window(selection)
    widths={r['source_id']:r['width_mm'] for r in report['native_rows']}
    eligible=set(); bypath={}; reasons={}
    for row in report['paths']:
        path=row.get('path'); members=path['source_ids'] if path else row['source_ids']
        shapes=[from_wkb(blobs[s]) for s in members]
        envelopes=[box(g.bounds[0]-.25*widths[s]-ERROR_MM,g.bounds[1]-.25*widths[s]-ERROR_MM,
                       g.bounds[2]+.25*widths[s]+ERROR_MM,g.bounds[3]+.25*widths[s]+ERROR_MM)
                   for s,g in zip(members,shapes)]
        inside=all(region.covers(g) for g in envelopes)
        intersects=any(g.intersects(box(*selection['bounds_mm'])) for g in shapes)
        if path:bypath['route:'+path['path_id']]=row
        if inside:
            if row['disposition']=='ADMIT_COMPLETE_NATIVE_ROUTE':eligible.add('route:'+path['path_id'])
        else:
            row['disposition']='KEEP_CROP_BOUNDARY' if intersects else 'KEEP_OUTSIDE_CROP'
            row['reason']='Complete native path/envelope does not fit the selected window; no trimming'
    # A crop cannot silently split a source-proven parallel width group.
    groups=[]
    for group in report['groups']:
        members=set(group['members'])
        if members<=eligible:groups.append(group)
        else:
            for sid in members&eligible:
                bypath[sid].update(disposition='KEEP_CROP_GROUP_BOUNDARY',reason='Complete parallel group crosses crop selection')
                reasons[sid]=True
    eligible-=reasons.keys()
    admitted=[p for p in report['admitted_paths'] if 'route:'+p['path_id'] in eligible]
    owner={s for p in admitted for s in p['source_ids']}
    report.update(admitted_paths=admitted, groups=groups,
                  unsupported=[r for r in report['paths'] if r['disposition']=='UNSUPPORTED'],
                  classifications=dict(Counter(r['disposition'] for r in report['paths'])),
                  protected_source_ids=sorted(set(blobs)-owner), crop_selection=selection,
                  scope='Verified image crop selects complete native paths and complete parallel groups; every F.Cu source remains clearance context; no clipping or rerouting')
    return report

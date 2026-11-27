"""Two separate saved viewer workspaces for sealed cleanup and T04 outputs.

No treatment, search preparation or clearance API is invoked by this operation.
Native display acknowledgement remains pending until the actual app reports it.
"""
import json
from pathlib import Path

from shapely import from_wkb
from src.copper_phase_seal import verify
from src.large_copper_runner import workspace_path,publish_saved,read_file
from src.copper_pipeline import status
from .publisher import encode,atomic_write,bounds,path_data
from . import live,t04_workspace


def link_workspaces(job,saved):
    """Publish saved-display links only, after authenticating the phase seals."""
    from src.copper_phase_seal import file_sha
    entries={name:dict(path=str(workspace_path(path)),snapshotSHA256=saved['snapshot_sha256'][name],
        presentationSHA256=file_sha(Path(path)/'presentations'/(saved['snapshot_sha256'][name]+'.json')))
        for name,path in saved['workspaces'].items()}
    result=json.loads(read_file(job/'RESULT.json'))
    value=dict(schema=1,sourceSHA256=result['source_sha256'],
        pipelineResultSHA256=file_sha(job/'RESULT.json'),workspaces=entries)
    for entry in entries.values():
        path=Path(entry['path'])/'phase-navigation.json'
        if not path.exists()or read_file(path)!=encode(value):atomic_write(path,encode(value))


def prepare(job,*,output=None):
    job=workspace_path(job);pipeline=status(job)
    if pipeline['status']!='COMPLETED':raise ValueError('COMPLETED_COPPER_PIPELINE_REQUIRED')
    parent_ref=pipeline['outputs']['large_copper'];child_ref=pipeline['outputs']['t04']
    parent=verify(**parent_ref,phase='large_copper');child=verify(**child_ref,phase='t04')
    destination=job if output is None else workspace_path(output)
    if output is not None and destination.exists():raise ValueError('FRESH_DISPLAY_DERIVATIVE_DIRECTORY_REQUIRED')
    receipt=destination/'VIEWERS.json'
    if receipt.exists():
        saved=json.loads(receipt.read_bytes())
        if saved['outputs']!=pipeline['outputs']:raise ValueError('PIPELINE_VIEWER_INPUT_CHANGED')
        for name in('large_copper','t04'):
            from .publisher import read_current
            manifest,_=read_current(Path(saved['workspaces'][name]))
            if manifest['sha256']!=saved['snapshot_sha256'][name]:raise ValueError('PIPELINE_VIEWER_REVISION_CHANGED')
        link_workspaces(job,saved)
        return saved
    if (destination/'VIEWERS_FAILED.json').exists():raise ValueError('PIPELINE_VIEWER_FAILURE_RETAINED')
    if output is not None:destination.mkdir(parents=True,exist_ok=False)
    try:
        # The cleanup view remains owned by its producer, with only bulk
        # copper objects and saved trimming places in its grey presentation.
        cleanup_display=publish_saved(parent['job'])
        source_root=Path(parent['job']);view_root=Path(child['job'])if output is None else destination/'t04'
        if output is not None:view_root.mkdir()
        target=view_root/'viewer_live'
        read=live.artifact_reader(source_root);binding=json.loads((source_root/'source.json').read_bytes())
        scene=json.loads(read(binding['scene_ref']));layer='Client selected artwork (stack NOT_ESTABLISHED)';objects=[]
        for row in scene['objects']:
            g,_=live.display(from_wkb(read(row['geometry_ref'])))
            objects.append(dict(id=row['source_id'],sourceID=row['source_id'],layer=layer,kind=row['kind'],
                path=path_data(g),bounds=bounds(g),attributes={}))
        area=live.area_bounds(objects)
        template=dict(schema=1,job='sealed-t04-template',revision='source',parentRevision=None,
            slice='Original source catalogue',status='Preview',bounds=area,affected=area,objects=objects,
            sources=[dict(name='Source artwork',sha256=parent['source_sha256'],layer=layer)],evidence=[],limitations=[])
        template_path=view_root/'viewer-source-template.json';atomic_write(template_path,encode(template))
        report=Path(child['job'])/'RESULT.json';result=json.loads(report.read_bytes())
        live.initialize(target,template=template_path,legacy=source_root,construction=result['stage']['path'],
            thread='sealed-copper-pipeline:'+job.name,context='original',initial_report=report)
        t04_display=t04_workspace.publish(target,create=True)
        # Both phase seals are still the exact inputs after display preparation.
        verify(**parent_ref,phase='large_copper');verify(**child_ref,phase='t04')
        from .publisher import read_current
        t04_manifest,_=read_current(target/'session')
        value=dict(status='SAVED_SEPARATE_WORKSPACES_PREPARED',outputs=pipeline['outputs'],
            pipeline_job=str(job),separate_display_derivative=output is not None,
            workspaces=dict(large_copper=cleanup_display['workspace'],t04=str(target/'session')),
            snapshot_sha256=dict(large_copper=cleanup_display['snapshot_sha256'],t04=t04_manifest['sha256']),
            t04_presentation=t04_display,geometry_treatment_executed=False,
            native_display='PENDING_NATIVE_ACK',copper_color='GREY',acceptance_changed=False)
        if Path(value['workspaces']['large_copper']).resolve()==Path(value['workspaces']['t04']).resolve():
            raise ValueError('PIPELINE_VIEWER_WORKSPACES_MUST_DIFFER')
        atomic_write(receipt,encode(value));link_workspaces(job,value);return value
    except BaseException as exc:
        atomic_write(destination/'VIEWERS_FAILED.json',encode(dict(status='FAILED_RETAINED',error=repr(exc),
            remaining='NOT_RUN',engineering_outputs_unchanged=True)))
        raise

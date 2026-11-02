"""Stdlib whole-board input/job preparation over the existing native launcher."""
from datetime import datetime,timezone
from pathlib import Path
import uuid
from tools import t01_crop_jobs as jobs
from tools.t01_route_client import decode,encode,publish

def inputs(kicad=None,gerber=None,*,attachments=None):
    defaults=decode((jobs.ROOT/'contracts/operator/t01_project.json').read_bytes())['inputs'];rows={};blobs={}
    for name,supplied in [('kicad',kicad),('gerber',gerber)]:
        if name in(attachments or {}):
            if supplied is not None:raise ValueError('ONE_INPUT_REPRESENTATION_REQUIRED:'+name)
            from tools.t01_crop_attachments import ingest
            row,blob=ingest(attachments[name],jobs.ROOT,jobs.attachment)
        else:row,blob=jobs.attachment(supplied if supplied is not None else str(jobs.ROOT/defaults[name]['path']))
        if supplied is None and name not in(attachments or {})and row['sha256']!=defaults[name]['sha256']:raise ValueError('PROJECT_INPUT_CHANGED:'+name)
        rows[name]=row;blobs[name]=blob
    return rows,blobs

def allocate(rows,blobs):
    version=jobs.implementation();key=jobs.admit(rows,version)
    job=jobs.output(jobs.MANAGED/'jobs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex));job.mkdir(parents=True)
    staged=job/'inputs';staged.mkdir();args={name:str(staged/(name+suffix))for name,suffix in [('kicad','.kicad_pcb'),('gerber','.gbr')]}
    row=dict(schema='pcb-crop-job/1',task_scope='full-board',job=str(job),input_sha256=key,implementation_sha256=version,inputs=rows,staged=args)
    publish(job/'job.json',encode(row))
    try:
        for name,path in args.items():
            publish(Path(path),blobs[name])
            if jobs.digest(Path(path).read_bytes())!=rows[name]['sha256']:raise ValueError('STAGED_ATTACHMENT_CHANGED')
    except Exception as error:jobs.halt(job,error);raise
    jobs.replace(jobs.MANAGED/'current.json',row);return job,row

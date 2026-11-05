"""File-only U05 continuation protocol. Audit authority stays in the native runner."""
import time,uuid,signal,subprocess
from pathlib import Path
from tools import t01_crop_jobs as jobs
from tools.t01_route_client import decode,encode,publish,safe_id

CAPABILITY='native-u05/1'

def output(path):
    path=jobs.output(path)
    if not path.is_relative_to(jobs.WORK):raise ValueError('U05_LACIE_OUTPUT_REQUIRED')
    return path

def request(value,launcher_id):
    allowed={'action','launcher_id','u04_job'}
    if 'reference' in value:allowed.add('reference')
    if set(value)!=allowed or value['action']!='u05_continuation' or value['launcher_id']!=launcher_id:raise ValueError('U05_LAUNCH_REQUEST_INVALID_OR_STALE')
    for key in ('u04_job','reference'):
        if key not in value:continue
        path=value[key]
        if type(path)is not str or len(path)>8192 or not Path(path).is_absolute() or '..' in Path(path).parts:raise ValueError('U05_EXPLICIT_ABSOLUTE_PATH_REQUIRED')
    return value

def delivery(job):
    job=output(job);receipt=decode((job/'U05_RECEIPT.json').read_bytes());checkpoint=job/'U05_CHECKPOINT.json'
    if receipt['status']!='PASS_U05_RETAINED_CONTINUATION_EXPORT' or receipt['job']!=str(job) or receipt['checkpoint_sha256']!=jobs.digest(checkpoint.read_bytes()):raise ValueError('U05_COMPLETE_CHECKPOINT_REQUIRED')
    cp=decode(checkpoint.read_bytes())
    from tools.t01_crop_jobs import ROOT
    operations=decode((ROOT/'contracts/operator/u05_board.json').read_bytes())['operations']
    if cp['operations']!=operations or [r['operation'] for r in cp['accepted']]!=operations or receipt['new_native_gates']!=len(operations) or receipt['machine_audits']!=len(operations) or receipt['human_or_agent_observations']!=0:raise ValueError('U05_COMPLETE_AUDITS_REQUIRED')
    expected=set(cp['files'])|{'U05_CHECKPOINT.json','U05_RECEIPT.json','U05_REPORT.md'}
    if {str(p.relative_to(job)) for p in job.rglob('*') if p.is_file()}!=expected:raise ValueError('U05_COMPLETE_FILE_SET_CHANGED')
    for name,h in cp['files'].items():
        p=output(job/name)
        if not p.is_relative_to(job) or jobs.digest(p.read_bytes())!=h:raise ValueError('U05_COMPLETE_ARTIFACT_CHANGED:'+name)
    for index,row in enumerate(cp['accepted'],1):
        folder=job/'audits'/f'{index:03d}';proof=folder/'proof.json'
        if row['proof']!=str(proof.relative_to(job/'audits')) or jobs.digest(proof.read_bytes())!=row['proof_sha256'] or decode(proof.read_bytes())['status']!='PASS':raise ValueError('U05_COMPLETE_PROOF_CHANGED')
        evaluations=decode((folder/'evaluations.json').read_bytes())
        workers=evaluations['workers']
        if len(workers)!=2 or len({r['pid'] for r in workers})!=2 or any(r['exit_code']!=0 for r in workers):raise ValueError('U05_TWO_FRESH_EVALUATIONS_REQUIRED')
    report=job/'U05_REPORT.md'
    return dict(status='COMPLETE_MACHINE_AUDITED_U05_EXPORT',next_action='REPORT_AND_STOP',job=str(job),ready_markdown=report.read_text(),receipt_sha256=jobs.digest((job/'U05_RECEIPT.json').read_bytes()),report_sha256=jobs.digest(report.read_bytes()),checkpoint_sha256=jobs.digest(checkpoint.read_bytes()),rendering='NOT_REQUESTED',owner='PENDING_USER')

class Continuations:
    def __init__(self,root,registry,launcher_id):
        self.root=root;self.registry=registry;self.id=launcher_id;self.children={}
        self.state=jobs.WORK/'operator_routes/u05_board/managed' if registry==jobs.LAUNCHER else registry.parent/'u05_managed'
    def start(self,rid,call,value):
        request(value,self.id)
        argv=[str(self.root/'.venv/bin/python'),'-B',str(self.root/'tools/pcb_u05_board_run.py'),'--u04-job',value['u04_job'],'--state-dir',str(output(self.state))]
        if 'reference' in value:argv+=['--reference',value['reference']]
        with (call/'stdout').open('xb') as stdout,(call/'stderr').open('xb') as stderr:
            process=subprocess.Popen(argv,cwd=self.root,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,start_new_session=True,close_fds=True)
        self.children[rid]=process
        publish(call/'launch.json',encode(dict(pid=process.pid,argv=argv,launcher_id=self.id)))
        jobs.replace(call/'status.json',dict(status='NATIVE_WORK_IN_PROGRESS',launcher_id=self.id,request_id=rid,updated_at=time.time()))
    def tick(self):
        for rid,process in list(self.children.items()):
            call=self.registry/'calls'/rid;code=process.poll()
            if code is None:
                jobs.replace(call/'status.json',dict(status='NATIVE_WORK_IN_PROGRESS',launcher_id=self.id,request_id=rid,updated_at=time.time()));continue
            try:
                events=[]
                for line in (call/'stdout').read_text().splitlines():
                    try:row=decode(line)
                    except ValueError:continue
                    if type(row)is dict:events.append(row)
                if code!=0:
                    failure=next((r for r in reversed(events) if r.get('status')=='HALTED'),{})
                    result=dict(status='HALTED',error=failure.get('error','U05_NATIVE_RUNNER_FAILED'),job=failure.get('job'),returncode=code,next_action='REPORT_AND_STOP; retained failure; no automatic retry')
                else:
                    complete=[r for r in events if r.get('status')=='COMPLETE_MACHINE_AUDITED_U05_EXPORT']
                    if len(complete)!=1:raise ValueError('U05_RUNNER_COMPLETE_EVENT_REQUIRED')
                    job=output(complete[0]['job'])
                    if job.parent!=self.state/'jobs':raise ValueError('U05_RUNNER_JOB_NAMESPACE_CHANGED')
                    result=delivery(job)
            except Exception as error:result=dict(status='HALTED',error=str(error),returncode=code,next_action='REPORT_AND_STOP; retained evidence; no automatic retry')
            result.update(launcher_id=self.id,request_id=rid,request_sha256=jobs.digest((call/'request.json').read_bytes()),stdout_sha256=jobs.digest((call/'stdout').read_bytes()),stderr_sha256=jobs.digest((call/'stderr').read_bytes()))
            publish(call/'response.json',encode(result));publish(self.registry/'replies'/(rid+'.json'),encode(result));del self.children[rid]
    def close(self):
        for process in self.children.values():
            if process.poll()is None:
                process.send_signal(signal.SIGINT)
                try:process.wait(timeout=30)
                except subprocess.TimeoutExpired:process.kill();process.wait()
        self.tick()

def start(u04_job,reference=None):
    host=jobs.launcher_ready()
    if host.get('u05_board')!=CAPABILITY:raise ValueError('NATIVE_LAUNCHER_UPDATE_REQUIRED: close its Terminal and reopen tools/Start_T01_Native_Launcher.command once; no U05 job started')
    value=dict(action='u05_continuation',launcher_id=host['launcher_id'],u04_job=str(u04_job))
    if reference is not None:value['reference']=str(reference)
    request(value,host['launcher_id']);rid='u05-'+uuid.uuid4().hex
    publish(output(jobs.LAUNCHER/'inbox'/(rid+'.json')),encode(value))
    return dict(status='NATIVE_WORK_IN_PROGRESS',request_id=rid,launcher_id=host['launcher_id'],next_action='status --request-id '+rid,rendering='NOT_REQUESTED',audit_mode='TWO_FRESH_MACHINE_EVALUATIONS_PER_GATE',human_or_agent_observations=0)

def status(rid):
    safe_id(rid);call=output(jobs.LAUNCHER/'calls'/rid);submitted=output(jobs.LAUNCHER/'inbox'/(rid+'.json'));value=decode(submitted.read_bytes());request(value,value['launcher_id']);reply=output(jobs.LAUNCHER/'replies'/(rid+'.json'))
    if reply.exists():
        result=decode(reply.read_bytes())
        if result.get('request_id')!=rid or result.get('launcher_id')!=value['launcher_id'] or result.get('request_sha256')!=jobs.digest(submitted.read_bytes()):raise ValueError('U05_LAUNCH_RESPONSE_CHANGED')
        if (call/'request.json').read_bytes()!=submitted.read_bytes():raise ValueError('U05_LAUNCH_REQUEST_CHANGED')
        for name in ('stdout','stderr'):
            if jobs.digest((call/name).read_bytes())!=result[name+'_sha256']:raise ValueError('U05_RUNNER_LOG_CHANGED')
        if result['status']=='COMPLETE_MACHINE_AUDITED_U05_EXPORT':
            current=delivery(result['job'])
            if any(current[k]!=result[k] for k in current):raise ValueError('U05_DELIVERY_CHANGED')
        return result
    host=jobs.launcher_ready()
    if host['launcher_id']!=value['launcher_id']:raise ValueError('U05_LAUNCHER_CHANGED: retained request; no restart')
    return dict(status='NATIVE_WORK_IN_PROGRESS',request_id=rid,next_action='status --request-id '+rid,rendering='NOT_REQUESTED')

"""Qualification semantics derived from retained reports, independently of UI.

Persistence accepts findings without repairing them. Retrieval rejects missing,
downgraded or misleading projections of those findings. It does not reparse PCB
sources or pretend that a report hash proves independent engineering intent.
"""
import json
from .revision_catalog import CatalogError,canonical,digest


def require(condition,reason):
    if not condition:raise CatalogError(reason)


def source_revisions(artifacts,roles):
    return {role:{k:artifacts[role][k] for k in ('revision','source_sha256')} for role in roles}


def native_qualification(profile,profile_hash,artifacts):
    roles=['native','copper','mask']
    return {'code':'BOUNDED_NATIVE_PROFILE','status':'QUALIFIED_IN_SCOPE','artifact_roles':roles,
            'source_revisions':source_revisions(artifacts,roles),'scope':profile['coverage'],
            'source_location':'Selected native byte spans; Gerber complete-prefix dependencies',
            'severity':'info','geometry':'AVAILABLE_IN_SCOPE','profile':'native-bottom-rect-context/1','retained_payloads':[profile_hash]}


def l2_qualification(report,report_binding,report_hash,artifacts):
    require(report.get('schema')=='l2gnd-native-gerber-discrepancy-v1','INVALID_L2_REPORT_SCHEMA')
    for field,role in [('native_board_sha256','native'),('client_sha256','l2_source'),('native_plot_sha256','l2_replot')]:
        require(report.get(field)==artifacts[role]['source_sha256'],'MIXED_L2_QUALIFICATION_INPUTS')
    binding=artifacts['l2_report']
    require(report_binding=={'path':binding['path'],'sha256':binding['source_sha256']} and report_hash==binding['source_sha256'],'L2_REPORT_BINDING_MISMATCH')
    require(report.get('symmetric_difference_area_mm2',0)>0 and report.get('source_only_flash_count',0)>0,'L2_MISMATCH_NOT_RETAINED')
    require(len(report.get('source_only_flashes',[]))==report['source_only_flash_count'] and len(report.get('native_only_flashes',[]))==report['native_only_flash_count'],'L2_REPORT_COUNT_MISMATCH')
    require(len(report.get('roi_mm',[]))==4,'L2_REPORT_REGION_MISSING')
    roles=['native','l2_source','l2_replot']
    return {'code':'L2GND_ROI_MISMATCH','status':'MISMATCH','artifact_roles':roles,'source_revisions':source_revisions(artifacts,roles),
            'scope':'Historical L2GND region only; REPLAY','source_location':'/symmetric_difference_area_mm2',
            'severity':'warning','geometry':'NOT_MATERIALIZED_IN_THIS_SLICE','report':report_binding,'report_artifact_revision':binding['revision'],
            'measurements':{k:report[k] for k in ('roi_mm','symmetric_difference_area_mm2','source_only_flash_count','native_only_flash_count')},
            'retained_payloads':[report_hash]}


def top_qualification(execution,execution_hash,artifacts,source):
    require(execution_hash==artifacts['top_report']['source_sha256']==digest(canonical(execution)),'TOP_EXECUTION_REPORT_REBOUND')
    require(execution.get('status')=='NOT_ESTABLISHED' and execution.get('geometry')=='UNAVAILABLE','TOP_UNSUPPORTED_SEMANTICS_CHANGED')
    require(execution.get('source_sha256')==artifacts['top']['source_sha256']==digest(source),'TOP_QUALIFICATION_SOURCE_MISMATCH')
    span=execution.get('source_span');require(isinstance(span,list) and len(span)==2,'TOP_WARNING_LOCATOR_MISSING')
    a,b=span;require(isinstance(a,int) and isinstance(b,int) and 0<=a<b<=len(source),'TOP_WARNING_LOCATOR_INVALID')
    require(execution.get('trigger')==source[a:b].decode('ascii'),'TOP_WARNING_TRIGGER_MISMATCH')
    require(execution.get('message') and 'zero-size aperture' in execution['message'] and ('artifact:'+digest(source)+':') in execution['message'],'TOP_WARNING_MESSAGE_MISSING')
    line=source[:a].count(b'\n')+1
    prefix='artifact:'+digest(source)+':'+str(line)
    require(any(execution['message'].startswith(prefix+separator) for separator in (' ',':')),'TOP_WARNING_LINE_MISMATCH')
    require(execution.get('warning_policy')=='First strict rejection retained; no claim of complete warning inventory','TOP_WARNING_COVERAGE_CHANGED')
    require(execution.get('parser')=='Gerbonara 1.6.3 + strict CompletionParser','TOP_PARSER_PROFILE_CHANGED')
    roles=['top']
    return {'code':'TOP_PARSE_UNSUPPORTED','status':'NOT_ESTABLISHED','artifact_roles':roles,
            'source_revisions':source_revisions(artifacts,roles),'scope':'Top artwork strict parse stops at first warning; original bytes retained',
            'source_location':span,'severity':'warning','geometry':'UNAVAILABLE','execution':execution,
            'report_artifact_revision':artifacts['top_report']['revision'],'retained_payloads':[execution_hash]}


def validate_qualifications(catalog,envelope,qualifications):
    require(isinstance(qualifications,list) and len(qualifications)==3,'MISSING_QUALIFICATION')
    by_code={q.get('code'):q for q in qualifications}
    require(set(by_code)=={'BOUNDED_NATIVE_PROFILE','L2GND_ROI_MISMATCH','TOP_PARSE_UNSUPPORTED'},'MISSING_QUALIFICATION')
    artifacts=envelope['artifacts'];required={'native','copper','mask','top','l2_source','l2_replot','l2_report','top_report'}
    require(required<=artifacts.keys(),'MISSING_QUALIFICATION_ARTIFACT')
    for role in ('top','l2_source','l2_replot','l2_report','top_report'):
        require(not catalog.snapshot(artifacts[role]['revision'])['objects'],'QUALIFICATION_ONLY_GEOMETRY_PROMOTED')
    for role,kind,inputs in [('l2_report','retained-l2-comparison-report/1',('native','l2_source','l2_replot')),
                             ('top_report','strict-parser-execution-report/1',('top',))]:
        config=catalog.snapshot(artifacts[role]['revision'])['config']
        require(config=={'profile_sha256':envelope['profile_sha256'],'kind':kind,'report_path':artifacts[role]['path'],
                         'input_revisions':{k:artifacts[k]['revision'] for k in inputs}},'QUALIFICATION_REPORT_PROVENANCE_MISMATCH')
    def retained(code):
        q=by_code[code];keys=q.get('retained_payloads')
        require(isinstance(keys,list) and len(keys)==1,'QUALIFICATION_REPORT_MISSING')
        return q,keys[0],json.loads(catalog.read_payload(keys[0]))
    n=by_code['BOUNDED_NATIVE_PROFILE'];expected_native=native_qualification(envelope['profile'],envelope['profile_sha256'],artifacts)
    require(n==expected_native,'NATIVE_QUALIFICATION_SEMANTICS_MISMATCH')
    catalog.read_payload(envelope['profile_sha256'])
    l2,key,report=retained('L2GND_ROI_MISMATCH')
    require(l2==l2_qualification(report,l2.get('report',{}),key,artifacts),'L2_QUALIFICATION_SEMANTICS_MISMATCH')
    top,key,execution=retained('TOP_PARSE_UNSUPPORTED')
    require(top==top_qualification(execution,key,artifacts,catalog.read_payload(artifacts['top']['source_sha256'])),'TOP_QUALIFICATION_SEMANTICS_MISMATCH')

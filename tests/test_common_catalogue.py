"""Failure-oriented tests for bounded adapters and persisted context retrieval."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from shapely import affinity,from_wkb,to_wkb
from src.catalogue_native import extract_native,net_annotation
from src.catalogue_gerber import extract_copper,extract_opening,parse_source,feature_record
from src.common_catalogue import (retrieve,verify_bundle,finalize_bundle,relationships,
    stable_relationships,match_witness,validate_positive,publish,SCHEMA)
from src.revision_catalog import RevisionCatalog,CatalogError,canonical,digest
from src.source_locators import locate,LocatorError
from src.catalog_selection import region_query
from src.catalogue_qualifications import native_qualification,l2_qualification,top_qualification
import sexpdata
ROOT=Path(__file__).resolve().parents[1]

NATIVE=b'''(kicad_pcb (setup (pad_to_mask_clearance 0))
 (footprint "R" (layer "B.Cu") (at 10 10 180) (uuid "fp") (property "Reference" "R140")
  (pad "1" smd rect (at -0.47 0 270) (size .62 .58) (layers "B.Cu" "B.Mask") (net "EN7") (uuid "p1"))
  (pad "2" smd rect (at 0.47 0 270) (size .62 .58) (layers "B.Cu" "B.Mask") (net "P3V3") (uuid "p2")))
 (segment (start 10.47 10) (end 10.47 10.67) (width .2) (layer "B.Cu") (net "EN7") (uuid "trace")))'''
HEAD=b'%FSLAX46Y46*%\n%MOMM*%\n'
COPPER=HEAD+b'''%TF.FileFunction,Copper,L2,Bot*%
%TF.FilePolarity,Positive*%
%ADD10R,0.58X0.62*%
%ADD11C,0.2*%
D10*
%TO.P,R140,1*%
%TO.N,EN7*%
X10470000Y-10000000D03*
%TD*%
%TO.P,R140,2*%
%TO.N,P3V3*%
X9530000Y-10000000D03*
%TD*%
%TO.N,EN7*%
D11*
X10470000Y-10000000D02*
X10470000Y-10670000D01*
M02*'''
MASK=HEAD+b'''%TF.FileFunction,Soldermask,Bot*%
%TF.FilePolarity,Negative*%
%ADD10R,0.58X0.62*%
D10*
%TO.C,R140*%
X10470000Y-10000000D03*
M02*'''


def fixture(path):
    n=extract_native(NATIVE,'R140','trace');c=extract_copper(COPPER);m=extract_opening(MASK,[10.47,10]);parts={'native':n,'copper':c,'mask':m}
    profile={'roles':['R140.1','connected_trace','R140.2','mask_opening'],'component':'R140','trace_uuid':'trace',
             'region_mm':[9,9,11,11],'match_tolerance_mm':.001,'nearby_distance_mm':.5,'coverage':'test selected records'}
    ph=digest(canonical(profile));artifacts={};links={};roles={};impl={'test_fixture':'bound'}
    with RevisionCatalog(path/'store') as cat:
        cat.put_payload(canonical(profile))
        for name,raw in [('native',NATIVE),('copper',COPPER),('mask',MASK)]:
            for key,value in parts[name]['payloads'].items():cat.put_payload(value)
            revision=cat.import_revision(raw,parts[name]['objects'],[],{'profile_sha256':ph})
            artifacts[name]={'revision':revision,'source_sha256':digest(raw)}
        for role in profile['roles']:
            name='mask' if role=='mask_opening' else 'copper';a=next(r for r in n['objects'] if r['id']==n['roles'][role]);b=next(r for r in parts[name]['objects'] if r['id']==parts[name]['roles'][role])
            roles[role]={'native':a['id'],'plotted':b['id']}
            links[role]={**roles[role],'native_revision':artifacts['native']['revision'],'plotted_revision':artifacts[name]['revision'],
                         'type':'opening_for' if role=='mask_opening' else 'geometry_equivalent','witness':match_witness(cat,a,b,.001)}
        token=b'X143260289Y-159004960D01*';top_source=token+b'\n'+token
        for name,raw in [('top',top_source),('l2_source',b'source L2'),('l2_replot',b'replot L2')]:
            revision=cat.import_revision(raw,[],[],{'profile_sha256':ph})
            artifacts[name]={'revision':revision,'source_sha256':digest(raw)}
        report={'schema':'l2gnd-native-gerber-discrepancy-v1','native_board_sha256':digest(NATIVE),
                'client_sha256':artifacts['l2_source']['source_sha256'],'native_plot_sha256':artifacts['l2_replot']['source_sha256'],
                'symmetric_difference_area_mm2':1,'source_only_flash_count':1,'native_only_flash_count':0,
                'source_only_flashes':[{'center_mm':[1,2]}],'native_only_flashes':[],'roi_mm':[0,0,2,3]}
        report_hash=cat.put_payload(canonical(report))
        top_execution={'source_sha256':digest(top_source),'status':'NOT_ESTABLISHED','geometry':'UNAVAILABLE',
                       'message':'artifact:'+digest(top_source)+':1: zero-size aperture',
                       'source_span':[0,len(token)],'trigger':token.decode(),
                       'parser':'Gerbonara 1.6.3 + strict CompletionParser',
                       'warning_policy':'First strict rejection retained; no claim of complete warning inventory'}
        for name,raw,report_path,kind,inputs in [
            ('l2_report',canonical(report),'test.json','retained-l2-comparison-report/1',('native','l2_source','l2_replot')),
            ('top_report',canonical(top_execution),'generated/strict-top-failure.json','strict-parser-execution-report/1',('top',))]:
            revision=cat.import_revision(raw,[],[],{'profile_sha256':ph,'report_path':report_path,'kind':kind,
                                                  'input_revisions':{k:artifacts[k]['revision'] for k in inputs}})
            artifacts[name]={'revision':revision,'source_sha256':digest(raw),'path':report_path}
        qs=[native_qualification(profile,ph,artifacts),l2_qualification(report,{'path':'test.json','sha256':report_hash},report_hash,artifacts),
            top_qualification(top_execution,cat.put_payload(canonical(top_execution)),artifacts,top_source)]
        rel=relationships(cat,artifacts['native']['revision'],n['objects'],n['roles'],.5)
        envelope={'schema':SCHEMA,'dataset_id':'test','profile':profile,'profile_sha256':ph,'artifacts':artifacts,'roles':roles,
                  'mask_expectation':n['mask_expectation'],'implementation':impl,
                  'links':cat.put_payload(canonical(links)),'qualifications':cat.put_payload(canonical(qs)),
                  'relationships':cat.put_payload(canonical(stable_relationships(rel)))}
    revision=finalize_bundle(path,envelope,impl)
    return revision,envelope


class AdapterTests(unittest.TestCase):
    def test_bounded_locators_keep_original_bytes_and_reject_partial_syntax(self):
        full=locate(NATIVE);bounded=locate(NATIVE,max_depth=2)
        self.assertEqual([s for s in full if s.parent_start in (None,0)],bounded)
        with self.assertRaises(LocatorError):locate(NATIVE+b'(',max_depth=2)
        with self.assertRaises(LocatorError):locate(NATIVE,max_depth=True)

    def test_modern_numeric_and_unassigned_net_annotations(self):
        for text,expected in [('(pad (net "EN7"))',(None,'EN7','SOURCE_NAMED_NET')),
                              ('(pad (net 7 "EN7"))',(7,'EN7','SOURCE_NUMERIC_NET')),
                              ('(pad (net 7))',(7,'EN7','SOURCE_NUMERIC_NET')),
                              ('(pad (net 0 ""))',(0,None,'SOURCE_NUMERIC_NET'))]:
            self.assertEqual(net_annotation(sexpdata.loads(text),{7:'EN7'}),expected)

    def test_backside_geometry_and_no_implicit_mask_geometry(self):
        n=extract_native(NATIVE,'R140','trace');rows=n['objects'];pad=next(r for r in rows if r['pin']=='1')
        self.assertAlmostEqual(pad['position_mm'][0],10.47);self.assertEqual(pad['geometry_layers'],['B.Cu'])
        self.assertEqual(n['mask_expectation']['resolved_margin_mm'],0)
        with tempfile.TemporaryDirectory(dir=ROOT/'out') as tmp,RevisionCatalog(tmp) as cat:
            for key,value in n['payloads'].items():cat.put_payload(value)
            rev=cat.import_revision(NATIVE,rows,[],{})
            result=region_query(cat,rev,[9,9,11,11],'B.Mask')
            self.assertEqual(result['records'],[]);self.assertEqual(result['unsupported_counts']['LAYER_GEOMETRY_UNAVAILABLE'],2)
        bad=extract_native(NATIVE.replace(b'10 10 180',b'10 10 90'),'R140','trace')
        self.assertIsNone(next(r for r in bad['objects'] if r['pin']=='1')['geometry_sha256'])
        self.assertIsNone(extract_native(NATIVE.replace(b'pad_to_mask_clearance 0',b'pad_to_mask_clearance .1'),'R140','trace')['mask_expectation'])

    def test_gerber_trigger_and_inherited_state_are_bound(self):
        c=extract_copper(COPPER)
        for row in c['objects']:
            a,b=row['source_span'];self.assertIn(COPPER[a:b][-1:],(b'*',b'%'))
            self.assertEqual(row['state_dependencies']['prefix_sha256'],digest(COPPER[:b]))
        line=next(r for r in c['objects'] if r['kind']=='gerber_line')
        self.assertEqual(line['endpoints_mm'],[[10.47,10.0],[10.47,10.67]])
        m=extract_opening(MASK,[10.47,10]);self.assertIsNone(m['objects'][0]['pin'])
        repeated=MASK.replace(b'M02*',b'X10470000Y-10000000D03*\nM02*')
        g,p=parse_source(repeated);r1,_=feature_record(repeated,g,p,0,'B.Mask');r2,_=feature_record(repeated,g,p,1,'B.Mask')
        self.assertNotEqual(r1['id'],r2['id'])
        with self.assertRaisesRegex(CatalogError,'AMBIGUOUS'):extract_opening(repeated,[10.47,10])
        with self.assertRaisesRegex(CatalogError,'POLARITY'):extract_opening(MASK.replace(b'Negative',b'Positive'),[10.47,10])
        with self.assertRaises(Exception):parse_source(COPPER.replace(b'0.2*%',b'0*%'))
        with self.assertRaisesRegex(CatalogError,'AMBIGUOUS'):extract_copper(COPPER.replace(b'M02*',b'D10*\n%TO.P,R140,1*%\nX10470000Y-10000000D03*\nM02*'))


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'out');self.path=Path(self.tmp.name);self.revision,self.envelope=fixture(self.path)
    def tearDown(self):self.tmp.cleanup()
    def reseal(self,envelope):
        (self.path/'receipt.json').unlink()
        self.revision=finalize_bundle(self.path,envelope,envelope['implementation'])
    def test_reopen_export_identity_readonly_and_caller_mutation(self):
        result=retrieve(self.path,self.revision);validate_positive(result)
        self.assertEqual(len(result['roles']),4);self.assertEqual(result['selections']['native']['dependency_ids'],[result['parent_dependency']['id']])
        digest_before=result['result_sha256'];result['roles'][0]['native']['net_name']='MUTATED'
        self.assertEqual(retrieve(self.path,self.revision)['result_sha256'],digest_before)
        with RevisionCatalog(self.path/'store',read_only=True) as cat:
            with self.assertRaisesRegex(CatalogError,'READ_ONLY'):cat.put_payload(b'x')
            with self.assertRaisesRegex(CatalogError,'READ_ONLY'):cat.import_revision(b'x',[],[],{})
    def test_failed_empty_and_missing_receipts_reject(self):
        (self.path/'receipt.json').write_text('{"schema":"pcb-common-context/1","status":"FAIL","outputs":{}}')
        with self.assertRaisesRegex(CatalogError,'INVALID_CONTEXT_RECEIPT'):retrieve(self.path,self.revision)
    def test_changed_cas_and_truncated_inventory_reject(self):
        with RevisionCatalog(self.path/'store',read_only=True) as cat:
            key=cat.snapshot(self.envelope['artifacts']['native']['revision'])['source_sha256']
        (self.path/'store/payloads'/key).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'STALE'):retrieve(self.path,self.revision)
    def test_mixed_revision_missing_role_qualification_and_stale_links(self):
        for mutation,reason in [
            (lambda e:e['roles'].pop('connected_trace'),'OMITTED'),
            (lambda e:e['artifacts']['native'].update(source_sha256='0'*64),'MIXED_ARTIFACT'),
            (lambda e:e.pop('qualifications'),'MISSING_QUALIFICATIONS'),
            (lambda e:e['roles']['R140.1'].update(plotted=e['roles']['R140.2']['plotted']),'CORRESPONDENCE_ENDPOINT'),
        ]:
            with self.subTest(reason=reason):
                e=copy.deepcopy(self.envelope);mutation(e);self.reseal(e)
                with self.assertRaisesRegex(CatalogError,reason):retrieve(self.path,self.revision)
        self.reseal(self.envelope)
        with self.assertRaisesRegex(CatalogError,'STALE_MIXED_DATASET'):retrieve(self.path,'0'*64)
    def test_same_net_disconnection_neighbor_merge_and_wrong_transform(self):
        partial=copy.deepcopy(retrieve(self.path,self.revision));partial['roles'].pop()
        with self.assertRaisesRegex(CatalogError,'INCOMPLETE'):validate_positive(partial)
        with RevisionCatalog(self.path/'store') as cat:
            n=cat.snapshot(self.envelope['artifacts']['native']['revision']);rows=n['objects'];roles={k:v['native'] for k,v in self.envelope['roles'].items()}
            for role,offset in [('connected_trace',2),('R140.2',.94)]:
                changed=copy.deepcopy(rows);row=next(r for r in changed if r['id']==roles[role]);shape=affinity.translate(from_wkb(cat.read_payload(row['geometry_sha256'])),xoff=offset)
                row.update(geometry_sha256=cat.put_payload(to_wkb(shape)),bounds_mm=list(shape.bounds),net_name='EN7')
                with self.assertRaisesRegex(CatalogError,'CONTACT|GROUP'):relationships(cat,n['source_sha256'],changed,roles,.5)
            a=next(r for r in rows if r['id']==roles['R140.1']);b=copy.deepcopy(a)
            shape=affinity.translate(from_wkb(cat.read_payload(b['geometry_sha256'])),xoff=.01)
            b.update(geometry_sha256=cat.put_payload(to_wkb(shape)),bounds_mm=list(shape.bounds))
            self.assertEqual(match_witness(cat,a,b,.001)['status'],'MISMATCH')
    def test_qualification_semantics_survive_coherent_rehash(self):
        mutations=[
            ('status',lambda q:q[1].update(status='PASS')),
            ('severity',lambda q:q[1].update(severity='info')),
            ('missing measurements',lambda q:q[1].pop('measurements')),
            ('changed measurement',lambda q:q[1]['measurements'].update(source_only_flash_count=0)),
            ('missing report',lambda q:q[1].pop('report')),
            ('changed report path',lambda q:q[1]['report'].update(path='out/fake/report.json')),
            ('changed source binding',lambda q:q[1]['source_revisions']['l2_source'].update(source_sha256='0'*64)),
            ('changed owner',lambda q:q[1].update(artifact_roles=['native'])),
            ('top geometry promotion',lambda q:q[2].update(geometry='AVAILABLE')),
            ('top message lost',lambda q:q[2]['execution'].update(message='')),
            ('top locator changed',lambda q:q[2].update(source_location=[0,1])),
            ('native profile promoted',lambda q:q[0].update(scope='Whole board')),
            ('duplicate qualification',lambda q:q.append(copy.deepcopy(q[1]))),
        ]
        for name,mutation in mutations:
            with self.subTest(name=name):
                e=copy.deepcopy(self.envelope)
                with RevisionCatalog(self.path/'store') as cat:
                    quals=json.loads(cat.read_payload(e['qualifications']));mutation(quals)
                    e['qualifications']=cat.put_payload(canonical(quals))
                self.reseal(e)
                with self.assertRaises((CatalogError,KeyError)):retrieve(self.path,self.revision)
    def test_coherent_warning_report_rebind_is_not_a_new_locator(self):
        e=copy.deepcopy(self.envelope)
        with RevisionCatalog(self.path/'store') as cat:
            qs=json.loads(cat.read_payload(e['qualifications']));q=qs[2]
            source=cat.read_payload(e['artifacts']['top']['source_sha256']);trigger=q['execution']['trigger'].encode()
            offset=source.find(trigger,1);self.assertGreater(offset,0)
            q['execution']['source_span']=[offset,offset+len(trigger)]
            q['source_location']=q['execution']['source_span']
            q['execution']['message']='artifact:'+digest(source)+':2: zero-size aperture'
            q['retained_payloads']=[cat.put_payload(canonical(q['execution']))]
            e['qualifications']=cat.put_payload(canonical(qs))
        self.reseal(e)
        with self.assertRaisesRegex(CatalogError,'TOP_EXECUTION_REPORT_REBOUND'):retrieve(self.path,self.revision)
    def test_partial_publication_keeps_previous_pointer(self):
        # The writer is mocked only to use this small qualified bundle. The real
        # publication/staging/verification/atomic-pointer path executes.
        import src.common_catalogue as module
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'out') as tmp:
            root=Path(tmp);out=root/'out/published';out.mkdir(parents=True);(out/'current.json').write_text('PREVIOUS')
            def build(_,stage,impl):
                _,e=fixture(stage);(stage/'receipt.json').unlink();e['implementation']=impl;return e
            with patch.object(module,'CORE_SOURCES',()),patch('src.catalogue_build.build',side_effect=build):
                # Keep a nonempty implementation binding for the receipt contract.
                with patch.object(module,'CORE_SOURCES',('source',)):
                    (root/'source').write_text('fixed')
                    with self.assertRaisesRegex(CatalogError,'INJECTED_PARTIAL'):publish(root,out,fail_before_publish=True)
            self.assertEqual((out/'current.json').read_text(),'PREVIOUS');self.assertFalse(list(out.glob('.staging-*')))


if __name__=='__main__':unittest.main()

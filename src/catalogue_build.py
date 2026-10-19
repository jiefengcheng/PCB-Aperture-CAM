"""Source-aware writer for the one declared context profile; no editing."""
import importlib.metadata
import json
from pathlib import Path

from gerbonara.rs274x import GerberFile
from shapely import affinity,from_wkb
from shapely.geometry import box
import shapely
from .catalogue_native import extract_native,PROFILE as NATIVE_PROFILE
from .catalogue_gerber import extract_copper,extract_opening,ProvenanceParser,PROFILE as GERBER_PROFILE
from .common_catalogue import SCHEMA,PROFILE_PATH,require,match_witness,relationships,stable_relationships
from .revision_catalog import RevisionCatalog,canonical,digest
from .ingestion_files import local,sha,verify
from .directory_intake import package_inventory,PROFILES
from .gerber_image import object_geometry,ordered
from .validator import Unsupported
from .catalogue_qualifications import native_qualification,l2_qualification,top_qualification


def build(root,stage,implementation):
    recipe=json.loads((root/PROFILE_PATH).read_text());recipe_hash=digest(canonical(recipe))
    profiles=json.loads((root/PROFILES).read_text())
    package=next(p for p in profiles['packages'] if p['dataset']['id']==recipe['dataset_id'])
    _,inventory=package_inventory(root,root/package['package_root'],package['seal']['sha256'])
    dataset=package['dataset'];verify(root,dataset['sources']+dataset['evidence'])
    def binding(suffix,kind='sources'):
        rows=[r for r in dataset[kind] if r['path'].endswith(suffix)]
        require(len(rows)==1,'AMBIGUOUS_SOURCE_BINDING: '+suffix);return rows[0]
    bindings={
        'native':binding('/raw/kicad/vme-wren.kicad_pcb'),
        'copper':binding('/raw/gerber/vme-wren-Bottom Layer.gbr'),
        'mask':binding('/raw/gerber/vme-wren-Bottom Solder.gbr'),
        'top':binding('/raw/gerber/vme-wren-Top Layer.gbr'),
        'l2_source':binding('/raw/gerber/vme-wren-L2GND.gbr'),
        'l2_replot':binding('/gerbers/vme-wren-L2GND.gbr'),
    }
    sources={k:local(root,v['path']).read_bytes() for k,v in bindings.items()}
    native=extract_native(sources['native'],recipe['component'],recipe['trace_uuid'])
    require(native['mask_expectation'] is not None,'MASK_EXPECTATION_OUTSIDE_PROFILE')
    copper=extract_copper(sources['copper'])
    target=next(r for r in native['objects'] if r['id']==native['roles']['R140.1'])
    mask=extract_opening(sources['mask'],target['position_mm'])
    extracted={'native':native,'copper':copper,'mask':mask}
    with RevisionCatalog(stage/'store') as catalog:
        artifacts={}
        # Enforce actual final plotted image coverage. A later clear operation
        # must not let an erased feature masquerade as materialized copper.
        for name in ('copper','mask'):
            data=extracted[name];roi=box(*recipe['region_mm'])
            items=[]
            for obj in data['parsed'].objects:
                shape=affinity.scale(object_geometry(obj),1,-1,origin=(0,0))
                if shape.intersects(roi):items.append((shape.intersection(roi),obj.polarity_dark))
            image=ordered(items)
            for row in data['objects']:
                shape=from_wkb(data['payloads'][row['geometry_sha256']])
                require(roi.covers(shape),'SELECTED_FEATURE_OUTSIDE_DECLARED_REGION')
                require(shape.difference(image).area<1e-12,'SELECTED_FEATURE_ERASED_IN_FINAL_IMAGE')
        for name,source in sources.items():
            data=extracted.get(name,{'objects':[],'payloads':{}})
            for key,payload in data['payloads'].items():require(catalog.put_payload(payload)==key,'GEOMETRY_HASH_MISMATCH')
            for row in data['objects']:
                row['qualification_refs']=['BOUNDED_NATIVE_PROFILE'] if name=='native' else []
                row['match_refs']=[role for role,oid in data['roles'].items() if oid==row['id']]
            revision=catalog.import_revision(source,data['objects'],[],{
                'profile_sha256':recipe_hash,'extractor':NATIVE_PROFILE if name=='native' else GERBER_PROFILE if name in extracted else 'qualification-only/no-geometry',
                'frame':recipe['coordinate_frame'],'geometry_versions':{'shapely':shapely.__version__,'geos':shapely.geos_version_string},
                'coverage':recipe['coverage'] if name in extracted else 'Retained input of qualification; no extracted objects'})
            artifacts[name]={**bindings[name],'source_sha256':digest(source),'revision':revision,'objects':len(data['objects'])}
        links={};roles={}
        for role in recipe['roles']:
            name='mask' if role=='mask_opening' else 'copper'
            a=next(r for r in native['objects'] if r['id']==native['roles'][role])
            b=next(r for r in extracted[name]['objects'] if r['id']==extracted[name]['roles'][role])
            witness=match_witness(catalog,a,b,recipe['match_tolerance_mm'])
            roles[role]={'native':a['id'],'plotted':b['id']}
            links[role]={'type':'opening_for' if role=='mask_opening' else 'geometry_equivalent',
                         **roles[role],'native_revision':artifacts['native']['revision'],'plotted_revision':artifacts[name]['revision'],
                         'transform':'Gerber (x,y) -> board (x,-y); no fitted alignment',
                         'cardinality':'unique in complete parsed source within declared source predicate',
                         'witness':witness,'basis':native['mask_expectation'] if role=='mask_opening' else 'Source annotation/trace endpoint discovery plus nominal geometry'}
        rel=relationships(catalog,artifacts['native']['revision'],native['objects'],native['roles'],recipe['nearby_distance_mm'])
        # Preserve strict parse failure as data, without deriving usable geometry.
        g=GerberFile();parser=ProvenanceParser(g)
        try:
            parser.parse(sources['top'].decode('ascii'),filename='artifact:'+digest(sources['top']))
        except (Unsupported,ValueError,SyntaxError) as error:
            top_failure={'status':'NOT_ESTABLISHED','message':str(error),'source_span':parser.current_span,
                         'source_sha256':digest(sources['top']),'trigger':sources['top'][slice(*parser.current_span)].decode('ascii'),
                         'geometry':'UNAVAILABLE','parser':'Gerbonara '+importlib.metadata.version('gerbonara')+' + strict CompletionParser',
                         'warning_policy':'First strict rejection retained; no claim of complete warning inventory'}
        else:raise ValueError('EXPECTED_TOP_UNSUPPORTED_NOT_REPRODUCED')
        report_binding=binding('/l2gnd_discrepancy.json','evidence');report_raw=local(root,report_binding['path']).read_bytes();report=json.loads(report_raw)
        require(report['native_board_sha256']==digest(sources['native']) and report['client_sha256']==digest(sources['l2_source'])
                and report['native_plot_sha256']==digest(sources['l2_replot']),'MIXED_L2_QUALIFICATION_INPUTS')
        require(report['symmetric_difference_area_mm2']>0,'L2_MISMATCH_NOT_RETAINED')
        # Reports have their own immutable artifact revisions. A qualification
        # projection cannot author its own replacement path or warning payload.
        for name,raw,path,config in [
            ('l2_report',report_raw,report_binding['path'],{'kind':'retained-l2-comparison-report/1',
             'input_revisions':{k:artifacts[k]['revision'] for k in ('native','l2_source','l2_replot')}}),
            ('top_report',canonical(top_failure),'generated/strict-top-failure.json',{'kind':'strict-parser-execution-report/1',
             'input_revisions':{'top':artifacts['top']['revision']}}),
        ]:
            revision=catalog.import_revision(raw,[],[],{'profile_sha256':recipe_hash,'report_path':path,**config})
            artifacts[name]={'revision':revision,'source_sha256':digest(raw),'path':path,'objects':0}
        qualifications=[native_qualification(recipe,recipe_hash,artifacts),
                        l2_qualification(report,report_binding,catalog.put_payload(report_raw),artifacts),
                        top_qualification(top_failure,catalog.put_payload(canonical(top_failure)),artifacts,sources['top'])]
        require(catalog.put_payload(canonical(recipe))==recipe_hash,'PROFILE_HASH_MISMATCH')
        envelope={'schema':SCHEMA,'dataset_id':recipe['dataset_id'],'profile':recipe,'profile_sha256':recipe_hash,
                  'artifacts':artifacts,'roles':roles,'mask_expectation':native['mask_expectation'],
                  'links':catalog.put_payload(canonical(links)),'qualifications':catalog.put_payload(canonical(qualifications)),
                  'relationships':catalog.put_payload(canonical(stable_relationships(rel))),
                  'implementation':implementation,'runtime':{'gerbonara':importlib.metadata.version('gerbonara'),'shapely':shapely.__version__,'geos':shapely.geos_version_string},
                  'source_recipe':{'path':PROFILES,'sha256':sha(root/PROFILES),'seal':package['seal']},
                  'coverage':recipe['coverage'],'native_graph':'SHADOW_ONLY; not used for acceptance'}
    # Sources are checked again after materialization, before publication.
    verify(root,list(bindings.values())+[report_binding,package['seal']])
    return envelope

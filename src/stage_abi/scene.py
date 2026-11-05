"""Scene records and finite-copper projections, independent of UI labels."""
from shapely import from_wkb,to_wkb
from shapely.ops import unary_union
from shapely.geometry import box
from .contracts import closed,ref,fail

SCENE_FIELDS={'source_sha256','frame','units','layer','viewport_mm','objects','findings','lineage','acceptance'}
OBJECT_FIELDS={'source_id','kind','original_ref','geometry_ref','metadata'}

def validate_scene(store,reference):
 scene=store.get_json(reference,kind='scene');closed(scene,SCENE_FIELDS,'scene')
 if scene['units']!='mm' or scene['layer']!='F.Cu' or type(scene['frame']) is not str or not scene['frame']:fail('SCENE_SEMANTICS_UNSUPPORTED','explicit mm/F.Cu frame required')
 h=scene['source_sha256']
 if type(h) is not str or len(h)!=64 or any(c not in '0123456789abcdef' for c in h):fail('SOURCE_BINDING_INVALID','source_sha256')
 view=scene['viewport_mm']
 if type(view) is not list or len(view)!=4 or any(type(x) not in (int,float) for x in view) or view[2]<=view[0] or view[3]<=view[1]:fail('VIEWPORT_INVALID','viewport_mm')
 if type(scene['objects']) is not list or not scene['objects'] or type(scene['findings']) is not list or type(scene['lineage']) is not list:fail('SCENE_RECORDS_INVALID','objects/findings/lineage')
 ids=set()
 for row in scene['objects']:
  closed(row,OBJECT_FIELDS,'source object');sid=row['source_id']
  if type(sid) is not str or not sid or len(sid)>512 or sid in ids:fail('SOURCE_IDENTITIES_INVALID','source_id')
  ids.add(sid)
  if type(row['kind']) is not str or type(row['metadata']) is not dict:fail('SCENE_RECORDS_INVALID','kind/metadata')
  for name in ['original_ref','geometry_ref']:ref(row[name],name)
 for row in scene['findings']:
  if type(row) is not dict or type(row.get('finding_id')) is not str:fail('FINDING_IDENTITIES_INVALID','finding_id')
 if len({r['finding_id'] for r in scene['findings']})!=len(scene['findings']):fail('FINDING_IDENTITIES_INVALID','duplicates')
 return scene

def geometry(store,reference):
 try:
  from .preparation import decode_geometry
  g=decode_geometry(store.get(reference,kind='geometry'))
 except (ValueError,TypeError) as error:fail('GEOMETRY_INVALID',str(error))
 if g.is_empty or not g.is_valid or g.geom_type not in ('Polygon','MultiPolygon'):fail('GEOMETRY_INVALID','finite valid filled copper required')
 return g

def composed(store,scene):
 return unary_union([geometry(store,r['geometry_ref']) for r in scene['objects']]).intersection(box(*scene['viewport_mm']))

def compatible(left,right):
 if any(left[k]!=right[k] for k in ['source_sha256','frame','units','layer']):fail('SCENE_COMPARISON_INCOMPATIBLE','source/frame/units/layer')

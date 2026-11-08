"""Narrow proof that only connected T01's positive checking operand changed."""
import ast,hashlib
BEFORE='470a231322d2175baa3b1c33ea0a53975ccb17babb94f5d8c104719e3557deec'
AFTER='7fc8270082093bf76540825138e3f452da284eb326b955faae3f9fa44c914b64'


def known(before,after):return(before,after)==(BEFORE,AFTER)


def prove(before,after):
 if not known(hashlib.sha256(before.encode()).hexdigest(),hashlib.sha256(after.encode()).hexdigest()):raise ValueError('T01_POSITIVE_DELTA_REVISION_CHANGED')
 tree=ast.parse(after);helpers=[node for node in tree.body if isinstance(node,ast.FunctionDef)and node.name=='t01_land_checker']
 expected=ast.parse('''def t01_land_checker(lands,fixed):
 """Use exact positive proposals, not numerical spurs on re-unioned old copper."""
 checker=p.PreparedLandScene(lands,fixed)
 checker.owner_added_material=checker._source_width_added_material
 return checker
''').body[0]
 dump=lambda node:ast.dump(node,include_attributes=False)
 if len(helpers)!=1 or dump(helpers[0])!=dump(expected):raise ValueError('T01_POSITIVE_DELTA_FACTORY_CHANGED')
 tree.body.remove(helpers[0]);found=0
 for function in tree.body:
  if not isinstance(function,ast.FunctionDef)or function.name!='run_t01':continue
  for node in ast.walk(function):
   if isinstance(node,ast.Call)and dump(node)==dump(ast.parse('t01_land_checker(lands,fixed)',mode='eval').body):
    node.func=ast.Attribute(value=ast.Name(id='p',ctx=ast.Load()),attr='PreparedLandScene',ctx=ast.Load());found+=1
 if found!=1 or dump(tree)!=dump(ast.parse(before)):raise ValueError('T01_POSITIVE_DELTA_SCOPE_CHANGED')
 return dict(status='EXACT_CONNECTED_T01_POSITIVE_OPERAND_ONLY',legacy_branch_unchanged=True,all_other_stage_code_unchanged=True,geometry_proposals_unchanged=True,scope='Only the final connected T01 owner-check operand uses the already-qualified exact per-proposal difference identity. No geometry, source core, cap, threshold, budget, pin/channel predicate or legacy execution changes.')

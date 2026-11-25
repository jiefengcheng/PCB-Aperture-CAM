"""Physical copper accounting for nearby, already prepared bridge dependencies.

Credits belong to this revision and worker only. No saved measurement grants an
acceptance. A trim can use a neighboring bridge's measured gain, never a remote
board change. Geometry, source floors and every conformance check remain separate.
"""
import math


class NeighborhoodBudget:
    def __init__(self,plans,local,*,diameter_mm=.35):
        if type(diameter_mm)not in(int,float)or not math.isfinite(diameter_mm)or diameter_mm<=0:
            raise ValueError('POSITIVE_BRIDGE_BUDGET_NEIGHBORHOOD_REQUIRED')
        self.diameter=diameter_mm;self.groups=[];self.members={}
        for i,plan in enumerate(plans):
            point=plan['record']['point_mm'];source=plan['record']['primary_source_id']
            selected=None
            for group in self.groups:
                if not all(math.dist(point,plans[j]['record']['point_mm'])<=diameter_mm for j in group['members']):continue
                if not any(source==plans[j]['record']['primary_source_id']or
                    source in local.get(j,{}).get('neighbors',())or
                    plans[j]['record']['primary_source_id']in local.get(i,{}).get('neighbors',())for j in group['members']):continue
                selected=group;break
            if selected is None:
                selected=dict(id=len(self.groups),members=[],credit_mm2=0.,commits=[]);self.groups.append(selected)
            selected['members'].append(i);self.members[i]=selected

    def allows(self,index,net):
        if type(net)not in(int,float)or not math.isfinite(net):raise ValueError('FINITE_PHYSICAL_COPPER_DELTA_REQUIRED')
        return self.members[index]['credit_mm2']+net>=-1e-12

    def commit(self,index,net):
        group=self.members[index];before=group['credit_mm2']
        if not self.allows(index,net):raise ValueError('T04_LOCAL_BRIDGE_BUDGET_OVERDRAWN')
        group['credit_mm2']+=net;group['commits'].append(dict(plan=index,net_mm2=net))
        return dict(group=group['id'],before_mm2=before,after_mm2=group['credit_mm2'])

    def receipt(self):
        return dict(schema='t04-local-bridge-copper-budgets/1',maximum_group_diameter_mm=self.diameter,
            scope='NEARBY_PREPARED_DEPENDENCIES; NO_REMOTE_CREDIT; EXACT_PHYSICAL_DELTAS',
            groups=self.groups,passed=all(g['credit_mm2']>=-1e-12 for g in self.groups))

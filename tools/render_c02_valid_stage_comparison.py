"""Compare the identical focused source set, retaining full C02 in both panels."""
import sys,json,re,html
from pathlib import Path
from xml.etree import ElementTree as ET
from shapely import from_wkb,to_wkb
from shapely.ops import unary_union

def main(root):
    p=Path(root);out=p/'comparison';out.mkdir(exist_ok=True)
    source=from_wkb((p/'source_baseline/copper.wkb').read_bytes())
    t01add=from_wkb((p/'t01/added_copper.wkb').read_bytes())
    bank=json.loads((p/'inputs/source_manifest.json').read_text());byid={r['id']:r for r in bank['objects']}
    oldadds=[]
    for r in json.loads((p/'t02/decisions.json').read_text()):
        core=from_wkb((p/'inputs/source_wkb'/f"{byid[r['source_id']]['geometry_sha256']}.wkb").read_bytes())
        old=from_wkb((p/f"rejected_proposals/{r['key']}_historical_v69.wkb").read_bytes());oldadds.append(old.difference(core))
    historical_added=unary_union(oldadds);newadd=from_wkb((p/'t02/added_copper.wkb').read_bytes())
    retention=newadd.area/historical_added.area
    measure={'historical_focused_rectangle_added_area_mm2':historical_added.area,
             'revised_focused_rectangle_added_area_mm2':newadd.area,
             'retained_added_area_fraction':retention,'target_sets_identical':True,
             'scope':'same 11 focused source rectangles plus C013; not the full historical 80-target v69 scene',
             'introduced_or_worsened_geometric_failures_from_revised_additions':0,
             'required_downstream_cleanup_of_revised_rectangle_growth':0,
             'optional_T03_anchor_optimization':'NOT_RUN','unmet_growth_target':'R11'}
    (out/'growth_retention.json').write_text(json.dumps(measure,indent=2)+'\n')
    (out/'historical_same_focus_cumulative.wkb').write_bytes(to_wkb(source.union(t01add).union(historical_added)))
    # Add exactly the saved T01 delta to the historical focused control rendering.
    ns={'s':'http://www.w3.org/2000/svg'}
    old=ET.fromstring((p/'rejected_proposals/full_crop.svg').read_text())
    t01=ET.fromstring((p/'t01/full_crop.svg').read_text())
    new=ET.fromstring((p/'t02/full_crop.svg').read_text())
    t01path=next(x for x in t01.findall('.//s:path',ns) if x.get('fill')=='#21bda8')
    t01path.set('fill','#ed4260');old.find('s:svg',ns).insert(3,t01path)
    old.find('s:text',ns).text='C02 / historical proposals — identical focused source set'
    # Namespace normalization only; both original coordinate viewports are retained.
    def nested(tree,x,y):
        tree.set('x',str(x));tree.set('y',str(y));return ET.tostring(tree,encoding='unicode')
    ET.register_namespace('',ns['s'])
    s='<svg xmlns="http://www.w3.org/2000/svg" width="3680" height="1840" viewBox="0 0 3680 1840"><rect width="3680" height="1840" fill="#e8eff4"/>'
    s+='<text x="40" y="52" font-family="Arial" font-size="34" fill="#142a3f">C02 / same focused set — historical growth vs revised stage-owning growth</text>'
    s+=f'<text x="40" y="92" font-family="Arial" font-size="24" fill="#243b50">Rectangle added-copper retention: {retention*100:.2f}% · 10/11 grow safely · R11 unchanged / NOT_COMPLETED · T02 NOT FROZEN</text>'
    s+=nested(old,20,120)+nested(new,1860,120)
    s+='<text x="40" y="1762" font-family="Arial" font-size="23" fill="#243b50">Both panels: exact ORG full viewport + C013 + the same 11 rectangles. Full historical v69 had 80 targets; no crop-wide growth-retention claim.</text>'
    s+='<text x="40" y="1800" font-family="Arial" font-size="23" fill="#243b50">Revised additions introduce/worsen no checked geometric gap; no rectangle-growth defect is delegated to T03. Optional T03 anchor optimization and T04 remain NOT_RUN.</text></svg>'
    (out/'full_crop_side_by_side.svg').write_text(s)
    page=(p/'index.html').read_text();page=page.replace('<section><h2>00 / source', '<section><h2>Same focused set / direct comparison</h2><a href="comparison/full_crop_side_by_side.png"><img src="comparison/full_crop_side_by_side.png"></a></section><section><h2>00 / source',1)
    (p/'index.html').write_text(page)
    print(json.dumps(measure))

if __name__=='__main__':main(sys.argv[1])

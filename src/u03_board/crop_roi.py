"""Existing PCB data-ABI image locator, with retained masks and no board renders."""
import io
from pathlib import Path
import numpy as np
from PIL import Image
from shapely import STRtree
from shapely.geometry import box
from shapely.ops import unary_union
from src.pcb_data_abi import roi
from src.pcb_data_abi.input_directory import regular_bytes
from src.stage_abi.store import canonical,digest
from tools.t01_operator_host import read,fresh
from .crop_match import fit_panel,round_peak_records
from .crop_landmarks import observable,PEAK_FLOOR_PX

OPERATIONS=('pcb_crop_locate','pcb_crop_verify')


def read_crop(path):
    path=Path(path)
    if not path.is_absolute() or '..' in path.parts:raise ValueError('U03_ABSOLUTE_CROP_PATH_REQUIRED')
    blob=regular_bytes(path)
    try:
        image=Image.open(io.BytesIO(blob));image.load()
        if max(image.size)>5000 or image.width*image.height>16_000_000:raise ValueError('PCB_ROI_IMAGE_BUDGET')
    except (OSError,ValueError) as error:raise ValueError('U03_CROP_IMAGE_UNSUPPORTED:'+str(error)) from error
    return dict(provided_path=str(path),sha256=digest(blob),bytes=len(blob),format=image.format),blob


class CropLocation:
    def __init__(self,root):
        self.root=Path(root);self.out=self.root/'data_board'
        self.crop=read(self.root.parent/'job.json')['crop'];self.path=Path(self.crop['path'])
        if digest(self.path.read_bytes())!=self.crop['sha256']:raise ValueError('U03_CROP_INPUT_CHANGED')
        host=roi.ROIService.__new__(roi.ROIService);host.out=self.out
        self.manifest,self.shapes=host.load_source()
        self.source_sha256=self.manifest['source_sha256']
        with Image.open(self.path) as image:
            image.load();self.panels=roi.image_panels(image)

    def mask(self,best):
        panel=self.panels[best['panel']]
        if panel['pixel_bounds']!=best['pixel_bounds']:raise ValueError('U03_CROP_PANEL_CHANGED')
        return roi.orient(panel['mask'],best['k'],best['mirror'])

    def geometry(self,bounds):
        return unary_union([self.shapes[int(i)] for i in STRtree(self.shapes).query(box(*bounds))])

    def locate(self):
        shapes=self.shapes;bounds=[min(g.bounds[0] for g in shapes),min(g.bounds[1] for g in shapes),max(g.bounds[2] for g in shapes),max(g.bounds[3] for g in shapes)]
        features=roi.circle_features(self.manifest,shapes);rows=[]
        feature_records=[]
        for index,panel in enumerate(self.panels):
            feature_records.append(dict(panel=index,method='visible-round-peak-hypotheses/1',features=round_peak_records(panel['mask'])))
            for row in fit_panel(panel['mask'],shapes,bounds,features):rows.append(dict(row,panel=index,pixel_bounds=panel['pixel_bounds']))
        matches=roi.distinct(rows,6)
        fresh(self.out/'crop_location_hypotheses.json',dict(candidates=matches,policy=roi.POLICY,hypothesis_features=feature_records))
        roi.assess(matches);best=matches[0];mask=self.mask(best)
        stream=io.BytesIO();np.save(stream,mask,allow_pickle=False);blob=stream.getvalue()
        with (self.out/'crop_mask.npy').open('xb') as target:target.write(blob)
        result=dict(facts=dict(passed=True,located=True,unique_in_supported_search=True,construction_status='NOT_RUN'),
                    source_sha256=self.source_sha256,crop_sha256=self.crop['sha256'],best=best,candidates=matches,policy=roi.POLICY,
                    mask_sha256=digest(blob),uncertainty_mm=.005+roi.POLICY['boundary_uncertainty_pixels']*max((best['bounds_mm'][2]-best['bounds_mm'][0])/mask.shape[1],(best['bounds_mm'][3]-best['bounds_mm'][1])/mask.shape[0]),
                    scope='Image locates source window only; complete native source supplies all copper; no candidate rendering')
        fresh(self.out/'crop_location.json',result);return result

    def measured(self):
        location=read(self.out/'crop_location.json')
        if location['source_sha256']!=self.source_sha256 or location['crop_sha256']!=self.crop['sha256'] or location['policy']!=roi.POLICY:
            raise ValueError('U03_CROP_LOCATION_BINDING_CHANGED')
        best=location['best'];mask=self.mask(best);blob=(self.out/'crop_mask.npy').read_bytes()
        if digest(blob)!=location['mask_sha256'] or not np.array_equal(np.load(io.BytesIO(blob),allow_pickle=False),mask):raise ValueError('U03_CROP_MASK_CHANGED')
        metrics=roi.pixel_metrics(mask,self.geometry(best['bounds_mm']),best['bounds_mm'])
        if metrics!=best['boundary_metrics'] or best!=location['candidates'][0]:raise ValueError('U03_CROP_LOCATION_METRICS_CHANGED')
        roi.assess(location['candidates'])
        return location,mask

    def verify(self):
        location,mask=self.measured();best=location['best'];bounds=best['bounds_mm']
        features=roi.circle_features(self.manifest,self.shapes)
        sites,census=observable(features,self.manifest,self.shapes,bounds,mask.shape)
        landmarks=roi.landmark_check(mask,bounds,sites)
        witness=dict(schema='u03-source-landmark-observability/1',source_circle_features=len(features),
                     existing_peak_floor_px=PEAK_FLOOR_PX,census=census,landmarks=landmarks,
                     matched=sum(r['matched'] for r in landmarks),required=len(landmarks),
                     source_coverage='Every original source remains in the native-mask, T01 and clearance geometry inventories')
        fresh(self.out/'crop_landmark_witness.json',witness)
        roi.assess(location['candidates'],landmarks)
        controls=self.controls(location,mask)
        result=dict(facts=dict(passed=True,location_verified=True,matched_landmarks=sum(r['matched'] for r in landmarks),deliberate_controls=3,construction_status='NOT_RUN'),
                    bounds_mm=bounds,uncertainty_mm=location['uncertainty_mm'],landmarks=landmarks,controls=controls,
                    location_sha256=digest((self.out/'crop_location.json').read_bytes()),
                    landmark_witness_sha256=digest((self.out/'crop_landmark_witness.json').read_bytes()))
        fresh(self.out/'crop_verified.json',result)
        selection=dict(schema='pcb-u03-image-crop/1',crop_path=str(self.path),crop_sha256=self.crop['sha256'],source_sha256=self.source_sha256,
                       bounds_mm=bounds,edge_uncertainty_mm=result['uncertainty_mm'],location_status='PASS_NATIVE_ROI_LOCATION',
                       location_path=str(self.out/'crop_location.json'),location_sha256=result['location_sha256'],
                       verification_path=str(self.out/'crop_verified.json'),verification_sha256=digest((self.out/'crop_verified.json').read_bytes()))
        fresh(self.root/'U03_SELECTION.json',selection);return result

    def controls(self,location,mask):
        best=location['best'];bounds=best['bounds_mm'];geometry=self.geometry(bounds);controls=[]
        def reject(name,changed):
            try:roi.assess(changed)
            except ValueError as error:controls.append(dict(name=name,error=str(error),status='PASS_EXPECTED_REJECTION'))
            else:raise ValueError('U03_CROP_CONTROL_NOT_REJECTED:'+name)
        shifted=[bounds[0]+.1,bounds[1],bounds[2]+.1,bounds[3]]
        q=roi.pixel_metrics(mask,geometry,shifted);reject('wrong_location_100um',[dict(best,iou=q['iou'],boundary_metrics=q)])
        altered=mask.copy();x,y,r=roi.peaks(mask)[0];yy,xx=np.ogrid[:mask.shape[0],:mask.shape[1]];altered[(xx-x)**2+(yy-y)**2<(r*.85)**2]=False
        q=roi.pixel_metrics(altered,geometry,bounds);reject('missing_interior_copper',[dict(best,iou=q['iou'],boundary_metrics=q)])
        reject('ambiguous_locations',[best,dict(best)])
        return controls

    def audit(self,operation):
        location,mask=self.measured()
        if operation=='pcb_crop_verify':
            value=read(self.out/'crop_verified.json');best=location['best']
            features=roi.circle_features(self.manifest,self.shapes)
            sites,census=observable(features,self.manifest,self.shapes,best['bounds_mm'],mask.shape)
            actual=roi.landmark_check(mask,best['bounds_mm'],sites)
            roi.assess(location['candidates'],actual)
            witness=read(self.out/'crop_landmark_witness.json')
            if witness['census']!=census or witness['landmarks']!=actual or witness['source_circle_features']!=len(features) or witness['existing_peak_floor_px']!=PEAK_FLOOR_PX or digest((self.out/'crop_landmark_witness.json').read_bytes())!=value['landmark_witness_sha256']:
                raise ValueError('U03_CROP_LANDMARK_OBSERVABILITY_CHANGED')
            if actual!=value['landmarks'] or value['location_sha256']!=digest((self.out/'crop_location.json').read_bytes()):raise ValueError('U03_CROP_LANDMARK_EVIDENCE_CHANGED')
            if value['controls']!=self.controls(location,mask):raise ValueError('U03_CROP_CONTROLS_REQUIRED')
        return dict(passed=True,source_sha256=self.source_sha256,crop_sha256=self.crop['sha256'],metrics_recomputed=True,mask_reconstructed_from_actual_input=True)

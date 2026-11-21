"""Check drawing geometry; not a navigation-safety or camera-calibration test."""
import json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[1]

def segment_hits_box(a,b,low,high):
    t0,t1=0.,1.
    for k in range(len(low)):
        d=b[k]-a[k]
        if abs(d)<1e-12:
            if a[k]<low[k] or a[k]>high[k]:return False
            continue
        u,v=sorted(((low[k]-a[k])/d,(high[k]-a[k])/d))
        t0=max(t0,u);t1=min(t1,v)
        if t0>t1:return False
    return True

def main():
    metadata=json.loads((R/'assets/diagram-robot/anchors.json').read_text())
    target=np.array([1.4,-.8,1.2])
    bases={'clearance':np.array([.9,.4,0]),'blocked':np.array([2.4,1.3,0]),'selected':np.array([.2,1.5,0])}
    boxes=[(np.array([1.85,.25,0]),np.array([2.20,.41,1.15])),(np.array([1.35,.48,0]),np.array([1.60,.68,.30]))]
    for name,m in metadata.items():
        base=bases[name];wanted=target[:2]-base[:2];wanted/=np.linalg.norm(wanted)
        assert np.allclose(m['forward_xy'],wanted,atol=1e-10),name
        assert max(abs(v) for v in m['foot_bottoms_m'])<1e-6,name
        low,high=np.asarray(m['mesh_bounds_m'])+base
        assert low[2]>-.001,name # Visual tessellation within 1 mm of collision feet.
        for a,b in boxes:
            assert np.any(high<a) or np.any(low>b),(name,'mesh bounding box intersects obstacle')
        basis=np.asarray(m['projection_basis_px']).T
        anchor=np.array(m['origin_px'])+basis@np.array(m['camera_local_m'])
        assert np.allclose(anchor,m['camera_px'],atol=1e-8),name
    a,b=boxes[1];base=bases['clearance']
    gap=np.linalg.norm(np.maximum(np.maximum(a[:2]-base[:2],base[:2]-b[:2]),0))
    assert gap<.55 # Conservative clearance rejection, despite no physical intersection.
    for name,wanted in [('blocked',True),('selected',False)]:
        base=bases[name];cam=base+metadata[name]['camera_local_m']
        assert any(segment_hits_box(base[:2],target[:2],a[:2],b[:2]) for a,b in boxes)==wanted
        assert any(segment_hits_box(cam,target,a,b) for a,b in boxes)==wanted
    c=bases['selected']+metadata['selected']['camera_local_m']
    elevation=np.degrees(np.arctan2(target[2]-c[2],np.linalg.norm(target[:2]-c[:2])))
    assert 0<elevation<30 # Drawing composition only; no calibrated hardware FOV claim.
    print(f'PASS: headings, four feet, common projection, mesh separation, clearance and sight segments; illustrative elevation {elevation:.2f} deg')
if __name__=='__main__':main()

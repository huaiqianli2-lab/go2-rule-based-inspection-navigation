"""Render transparent, grounded Go2 meshes for the explanatory diagrams.

Requires an existing MuJoCo Menagerie Go2 XML with its mesh assets, MuJoCo,
VTK and Pillow. Uses mj_forward only; this is an illustrative static stance.
"""
import os
os.environ['VTK_DEFAULT_OPENGL_WINDOW']='vtkEGLRenderWindow'
os.environ['VTK_SMP_MAX_THREADS']='1'
import mujoco as mj,numpy as np,vtk,json,sys
from vtk.util.numpy_support import numpy_to_vtk,numpy_to_vtkIdTypeArray,vtk_to_numpy
from PIL import Image
from pathlib import Path
import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--model',required=True,type=Path)
parser.add_argument('--output',required=True,type=Path)
args=parser.parse_args()
model=mj.MjModel.from_xml_path(str(args.model))
data=mj.MjData(model)
renderer=vtk.vtkRenderer();renderer.SetBackground(1,1,1);renderer.SetBackgroundAlpha(0)
window=vtk.vtkRenderWindow();window.SetOffScreenRendering(1);window.SetAlphaBitPlanes(1);window.SetMultiSamples(0);window.SetSize(600,600);window.AddRenderer(renderer)
actors=[]
for geom in range(model.ngeom):
 if model.geom_bodyid[geom]==0 or model.geom_group[geom]!=2 or model.geom_type[geom]!=mj.mjtGeom.mjGEOM_MESH:continue
 mesh=model.geom_dataid[geom];start=model.mesh_vertadr[mesh];n=model.mesh_vertnum[mesh]
 points=vtk.vtkPoints();points.SetData(numpy_to_vtk(model.mesh_vert[start:start+n].copy(),deep=True))
 start=model.mesh_faceadr[mesh];n=model.mesh_facenum[mesh];faces=model.mesh_face[start:start+n].copy()
 cells=vtk.vtkCellArray();cells.ImportLegacyFormat(numpy_to_vtkIdTypeArray(np.c_[np.full(n,3),faces].astype(np.int64).ravel(),deep=True))
 poly=vtk.vtkPolyData();poly.SetPoints(points);poly.SetPolys(cells)
 normals=vtk.vtkPolyDataNormals();normals.SetInputData(poly);normals.SetFeatureAngle(60)
 mapper=vtk.vtkPolyDataMapper();mapper.SetInputConnection(normals.GetOutputPort())
 a=vtk.vtkActor();a.SetMapper(mapper)
 # Neutral silver body retains the Go2 mesh geometry and visible limb detail.
 a.GetProperty().SetColor(.55,.62,.70);a.GetProperty().SetAmbient(.3);a.GetProperty().SetDiffuse(.7)
 mat=vtk.vtkMatrix4x4();a.SetUserMatrix(mat);renderer.AddActor(a);actors.append((geom,mat))
cam=renderer.GetActiveCamera();cam.SetPosition(-2,-2,1.72);cam.SetFocalPoint(0,0,0);cam.SetViewUp(0,0,1);cam.ParallelProjectionOn();cam.SetParallelScale(.65)
out=args.output;out.mkdir(parents=True,exist_ok=True)
meta={}
for name,xy in {'selected':(115,5),'blocked':(-17,-119),'clearance':(75,-122)}.items():
 yaw=np.arctan2(xy[1],xy[0]);mj.mj_resetDataKeyframe(model,data,0)
 data.qpos[3:7]=[np.cos(yaw/2),0,0,np.sin(yaw/2)];mj.mj_forward(model,data)
 # Ground the lowest foot collision sphere without physics integration.
 lows=[data.geom_xpos[g,2]-model.geom_size[g,0] for g in range(model.ngeom) if model.geom_type[g]==mj.mjtGeom.mjGEOM_SPHERE]
 data.qpos[2]-=min(lows);mj.mj_forward(model,data)
 for g,mat in actors:
  rot=data.geom_xmat[g].reshape(3,3)
  for i in range(3):
   for j in range(3):mat.SetElement(i,j,float(rot[i,j]))
   mat.SetElement(i,3,float(data.geom_xpos[g,i]))
 window.Render();capture=vtk.vtkWindowToImageFilter();capture.SetInput(window);capture.SetInputBufferTypeToRGBA();capture.ReadFrontBufferOff();capture.Update()
 arr=vtk_to_numpy(capture.GetOutput().GetPointData().GetScalars()).reshape(600,600,4)[::-1]
 Image.fromarray(arr).save(out/(name+'.png'))
 def project(pt):
  renderer.SetWorldPoint(*pt,1);renderer.WorldToDisplay();v=renderer.GetDisplayPoint();return [v[0],600-v[1]]
 origin=project([0,0,0]);front=[.30*np.cos(yaw),.30*np.sin(yaw),float(data.qpos[2])+.03]
 meta[name]={'origin_px':origin,'camera_px':project(front),'camera_local_m':front,'yaw_rad':float(yaw),'pixels_per_m':600/1.3,'camera_note':'Illustrative front-camera anchor, not calibrated extrinsics'}
(out/'anchors.json').write_text(json.dumps(meta,indent=2))
print(json.dumps(meta))

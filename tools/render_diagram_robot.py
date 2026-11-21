"""Render transparent, grounded Go2 meshes for the explanatory diagrams.

Requires an existing MuJoCo Menagerie Go2 XML with mesh assets, MuJoCo,
VTK and Pillow. Uses mj_forward only; this is an illustrative static stance.
"""

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("VTK_DEFAULT_OPENGL_WINDOW", "vtkEGLRenderWindow")
os.environ.setdefault("VTK_SMP_MAX_THREADS", "1")

import mujoco as mj
import numpy as np
from PIL import Image
import vtk
from vtk.util.numpy_support import (
    numpy_to_vtk,
    numpy_to_vtkIdTypeArray,
    vtk_to_numpy,
)


def render(model_path, output):
    model = mj.MjModel.from_xml_path(str(model_path))
    data = mj.MjData(model)
    renderer = vtk.vtkRenderer()
    renderer.SetBackground(1, 1, 1)
    renderer.SetBackgroundAlpha(0)
    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.SetAlphaBitPlanes(1)
    window.SetMultiSamples(0)
    window.SetSize(600, 600)
    window.AddRenderer(renderer)
    actors = []
    for geom in range(model.ngeom):
        if (model.geom_bodyid[geom] == 0 or model.geom_group[geom] != 2
                or model.geom_type[geom] != mj.mjtGeom.mjGEOM_MESH):
            continue
        mesh = model.geom_dataid[geom]
        start, count = model.mesh_vertadr[mesh], model.mesh_vertnum[mesh]
        points = vtk.vtkPoints()
        points.SetData(numpy_to_vtk(model.mesh_vert[start:start+count].copy(), deep=True))
        start, count = model.mesh_faceadr[mesh], model.mesh_facenum[mesh]
        faces = model.mesh_face[start:start+count].copy()
        cells = vtk.vtkCellArray()
        packed = np.c_[np.full(count, 3), faces].astype(np.int64).ravel()
        cells.ImportLegacyFormat(numpy_to_vtkIdTypeArray(packed, deep=True))
        poly = vtk.vtkPolyData()
        poly.SetPoints(points)
        poly.SetPolys(cells)
        normals = vtk.vtkPolyDataNormals()
        normals.SetInputData(poly)
        normals.SetFeatureAngle(60)
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(normals.GetOutputPort())
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(0.55, 0.62, 0.70)
        actor.GetProperty().SetAmbient(0.3)
        actor.GetProperty().SetDiffuse(0.7)
        matrix = vtk.vtkMatrix4x4()
        actor.SetUserMatrix(matrix)
        renderer.AddActor(actor)
        actors.append((geom, matrix))
    camera = renderer.GetActiveCamera()
    camera.SetPosition(-2, -2, 1.72)
    camera.SetFocalPoint(0, 0, 0)
    camera.SetViewUp(0, 0, 1)
    camera.ParallelProjectionOn()
    camera.SetParallelScale(0.65)
    output.mkdir(parents=True, exist_ok=True)
    metadata = {}
    try:
        for name, direction in {"selected": (115, 5), "blocked": (-17, -119),
                                "clearance": (75, -122)}.items():
            yaw = np.arctan2(direction[1], direction[0])
            mj.mj_resetDataKeyframe(model, data, 0)
            data.qpos[3:7] = [np.cos(yaw/2), 0, 0, np.sin(yaw/2)]
            mj.mj_forward(model, data)
            # In this Go2 model the sphere collision geoms are its four feet.
            feet = [data.geom_xpos[g, 2] - model.geom_size[g, 0]
                    for g in range(model.ngeom)
                    if model.geom_type[g] == mj.mjtGeom.mjGEOM_SPHERE]
            if len(feet) != 4:
                raise ValueError("Expected four spherical Go2 foot collision geoms")
            data.qpos[2] -= min(feet)
            mj.mj_forward(model, data)
            for geom, matrix in actors:
                rotation = data.geom_xmat[geom].reshape(3, 3)
                for i in range(3):
                    for j in range(3):
                        matrix.SetElement(i, j, float(rotation[i, j]))
                    matrix.SetElement(i, 3, float(data.geom_xpos[geom, i]))
            window.Render()
            capture = vtk.vtkWindowToImageFilter()
            capture.SetInput(window)
            capture.SetInputBufferTypeToRGBA()
            capture.ReadFrontBufferOff()
            capture.Update()
            pixels = vtk_to_numpy(capture.GetOutput().GetPointData().GetScalars())
            Image.fromarray(pixels.reshape(600, 600, 4)[::-1]).save(output / f"{name}.png")

            def project(point):
                renderer.SetWorldPoint(*point, 1)
                renderer.WorldToDisplay()
                value = renderer.GetDisplayPoint()
                return [value[0], 600-value[1]]

            front = [0.30*np.cos(yaw), 0.30*np.sin(yaw), float(data.qpos[2])+0.03]
            metadata[name] = {
                "origin_px": project([0, 0, 0]),
                "camera_px": project(front),
                "camera_local_m": front,
                "yaw_rad": float(yaw),
                "pixels_per_m": 600/1.3,
                "camera_note": "Illustrative front-camera anchor, not calibrated extrinsics",
            }
    finally:
        window.Finalize()
    (output / "anchors.json").write_text(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    render(args.model, args.output)

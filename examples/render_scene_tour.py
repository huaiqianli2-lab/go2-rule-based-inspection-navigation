"""Render height-colored orbits from the original project SLAM inputs."""

from pathlib import Path
import os, json, math, subprocess, argparse
os.environ['MUJOCO_GL'] = 'egl'
import mujoco as mj
import numpy as np
from OpenGL import GL
from PIL import Image, ImageDraw, ImageFont
parser = argparse.ArgumentParser(description='Orbit height-colored measured SLAM scenes.')
parser.add_argument('--inputs', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--ffmpeg', type=Path, required=True)
args = parser.parse_args()
src = args.inputs
out = args.output
out.mkdir(parents=True, exist_ok=True)

def read(path):
    with open(path, 'rb') as f:
        while f.readline().strip() != b'DATA binary':
            pass
        a = np.fromfile(f, dtype='<f4').reshape(-1, 3)
    return a[np.isfinite(a).all(axis=1)]

def unit(x):
    return x / np.linalg.norm(x)

def view(eye, target):
    f = unit(target - eye)
    s = unit(np.cross(f, [0, 0, 1]))
    u = np.cross(s, f)
    a = np.eye(4)
    a[:3, :3] = [s, u, -f]
    a[:3, 3] = -a[:3, :3] @ eye
    return a
ctx = mj.GLContext(1600, 1100)
ctx.make_current()
fbo = GL.glGenFramebuffers(1)
GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, fbo)
for (attachment, fmt) in [(GL.GL_COLOR_ATTACHMENT0, GL.GL_RGB8), (GL.GL_DEPTH_ATTACHMENT, GL.GL_DEPTH_COMPONENT24)]:
    rb = GL.glGenRenderbuffers(1)
    GL.glBindRenderbuffer(GL.GL_RENDERBUFFER, rb)
    GL.glRenderbufferStorage(GL.GL_RENDERBUFFER, fmt, 1600, 1100)
    GL.glFramebufferRenderbuffer(GL.GL_FRAMEBUFFER, attachment, GL.GL_RENDERBUFFER, rb)
GL.glDrawBuffer(GL.GL_COLOR_ATTACHMENT0)
GL.glReadBuffer(GL.GL_COLOR_ATTACHMENT0)
for (scene, idx, tid) in [('indoor', '002', '081'), ('outdoor', '005', '082')]:
    task = json.loads((src / f'{tid}_exp4_task.json').read_text())
    route = np.array(task['planned_path'])[:, :2]
    cloud = read(src / f'{idx}_reloc_map.pcd')
    low = route.min(0) - 4
    high = route.max(0) + 4
    cloud = cloud[((cloud[:, :2] > low) & (cloud[:, :2] < high)).all(1)]
    zlim = np.percentile(cloud[:, 2], [5, 95])
    if scene == 'indoor':
        cloud = cloud[cloud[:, 2] < zlim[0] + 1.9]
    bins = np.floor(cloud / 0.18).astype(np.int32)
    (_, inv, counts) = np.unique(bins, axis=0, return_inverse=True, return_counts=True)
    cloud = cloud[counts[inv] >= 2]
    cloud = cloud[(cloud[:, 2] >= zlim[0] - 0.4) & (cloud[:, 2] <= zlim[1] + 0.5)]
    zlim = np.percentile(cloud[:, 2], [2, 98])
    pos = np.clip((cloud[:, 2] - zlim[0]) / (zlim[1] - zlim[0]), 0, 1)
    palette = np.array([[0.15, 0.35, 0.85], [0.1, 0.75, 0.85], [0.35, 0.84, 0.57], [0.99, 0.81, 0.3], [0.96, 0.36, 0.22]])
    colors = np.array([np.interp(pos, np.linspace(0, 1, 5), c) for c in palette.T]).T.astype('float32')
    xyz = np.ascontiguousarray(cloud.astype('float32'))
    center = np.r_[(low + high) / 2, np.percentile(cloud[:, 2], 15)]
    extent = np.max(high - low)
    ff = args.ffmpeg
    output = out / f'{scene}-scene-tour.mp4'
    proc = subprocess.Popen([str(ff), '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '1600x1100', '-r', '15', '-i', '-', '-an', '-c:v', 'libx264', '-threads', '3', '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(output)], stdin=subprocess.PIPE)
    for frame in range(120):
        angle = 35
        rotation = math.radians(-18 + 36 * frame / 119)
        GL.glViewport(0, 0, 1600, 1100)
        GL.glClearColor(0.97, 0.98, 1, 1)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glEnable(GL.GL_DEPTH_TEST)
        near = 0.1
        far = 500
        f = 1 / math.tan(math.radians(40) / 2)
        aspect = 1600 / 1100
        projection = np.zeros((4, 4))
        projection[0, 0] = f / aspect
        projection[1, 1] = f
        projection[2, 2] = (far + near) / (near - far)
        projection[2, 3] = 2 * far * near / (near - far)
        projection[3, 2] = -1
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadMatrixd(projection.T)
        eye = center + extent * 1.1 * np.array([0.55, -0.75, math.tan(math.radians(angle)) * 0.7])
        delta = eye - center
        eye = center + np.array([math.cos(rotation) * delta[0] - math.sin(rotation) * delta[1], math.sin(rotation) * delta[0] + math.cos(rotation) * delta[1], delta[2]])
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glLoadMatrixd(view(eye, center).T)
        GL.glPointSize(3.2)
        GL.glEnableClientState(GL.GL_VERTEX_ARRAY)
        GL.glEnableClientState(GL.GL_COLOR_ARRAY)
        GL.glVertexPointer(3, GL.GL_FLOAT, 0, xyz)
        GL.glColorPointer(3, GL.GL_FLOAT, 0, np.ascontiguousarray(colors))
        GL.glDrawArrays(GL.GL_POINTS, 0, len(xyz))
        GL.glDisableClientState(GL.GL_COLOR_ARRAY)
        GL.glDisableClientState(GL.GL_VERTEX_ARRAY)
        GL.glLineWidth(3)
        GL.glColor3f(0.02, 0.45, 0.32)
        GL.glBegin(GL.GL_LINE_STRIP)
        for (x, y) in route:
            GL.glVertex3f(x, y, center[2] + 0.18)
        GL.glEnd()
        GL.glPointSize(9)
        GL.glColor3f(0.85, 0.4, 0.06)
        GL.glBegin(GL.GL_POINTS)
        for stop in task['stops']:
            GL.glVertex3f(stop['observe']['x'], stop['observe']['y'], center[2] + 0.2)
        GL.glEnd()
        data = GL.glReadPixels(0, 0, 1600, 1100, GL.GL_RGB, GL.GL_UNSIGNED_BYTE)
        im = Image.frombytes('RGB', (1600, 1100), data).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        d = ImageDraw.Draw(im)
        d.text((40, 30), f'{scene.capitalize()} / measured LiDAR / roof cutaway' if scene == 'indoor' else f'{scene.capitalize()} / measured LiDAR / oblique view', font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 29), fill='#172b46')
        for k in range(300):
            c = palette[min(4, int(k * 5 / 300))]
            d.line((1180 + k, 1033, 1180 + k, 1050), fill=tuple((c * 255).astype(int)), width=1)
        ft = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 21)
        d.text((1180, 1061), f'z: {zlim[0]:.1f} to {zlim[1]:.1f} m', font=ft, fill='#172b46')
        proc.stdin.write(im.tobytes())
        if frame == 60:
            im.save(out / f'{scene}-tour-poster.jpg', quality=92)
        if frame % 30 == 0:
            print(scene, frame, GL.glGetString(GL.GL_RENDERER), flush=True)
    proc.stdin.close()
    if proc.wait():
        raise RuntimeError('encoding failed')
    subprocess.run([str(ff), '-v', 'error', '-y', '-i', str(output), '-vf', 'fps=12,scale=1000:-2', '-c:v', 'libwebp_anim', '-quality', '76', '-loop', '0', '-threads', '1', str(out / f'{scene}-scene-tour.webp')], check=True)
ctx.free()

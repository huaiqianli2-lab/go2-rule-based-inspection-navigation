"""Generate original SVG/PNG figures and editable draw.io primitive masters.

NumPy/Pillow read the published metric datasets; CairoSVG exports the PNGs.
All schematics are illustrative, not newly measured or simulated results.
"""

from pathlib import Path
import base64
import io
import json
import math
import hashlib
import re
import xml.etree.ElementTree as ET
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from tools.point_cloud import read_xyz, map_view, HEIGHT_COLORS

R = Path(__file__).resolve().parents[1]
BG, FG, MUT = "#f8fafc", "#142b43", "#52677c"
BLUE, TEAL, AMBER, PURPLE, RED = "#2563eb", "#008b8b", "#ca750d", "#7952ca", "#c34654"
NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)


class Figure:
    def __init__(self, name, w, h):
        self.name, self.w, self.h = name, w, h
        self.root = ET.Element(
            "svg", xmlns=NS, width=str(w), height=str(h), viewBox=f"0 0 {w} {h}"
        )
        self.mx = ET.Element("mxfile", host="app.diagrams.net")
        d = ET.SubElement(self.mx, "diagram", name=name, id=name)
        m = ET.SubElement(
            d,
            "mxGraphModel",
            page="1",
            pageWidth=str(w),
            pageHeight=str(h),
            background=BG,
        )
        self.graph = ET.SubElement(m, "root")
        ET.SubElement(self.graph, "mxCell", id="0")
        ET.SubElement(self.graph, "mxCell", id="1", parent="0")
        self.n = 1
        self.rect(0, 0, w, h, BG)

    def cell(self, x, y, w, h, style, value=""):
        self.n += 1
        c = ET.SubElement(
            self.graph,
            "mxCell",
            id=str(self.n),
            value=value,
            style=style,
            vertex="1",
            parent="1",
        )
        ET.SubElement(
            c,
            "mxGeometry",
            x=str(x),
            y=str(y),
            width=str(w),
            height=str(h),
            attrib={"as": "geometry"},
        )

    def element(self, tag, **attrs):
        return ET.SubElement(
            self.root, tag, {k.replace("_", "-"): str(v) for k, v in attrs.items()}
        )

    def rect(self, x, y, w, h, fill="white", stroke="none", r=0):
        self.element(
            "rect", x=x, y=y, width=w, height=h, fill=fill, stroke=stroke, rx=r
        )
        self.cell(
            x,
            y,
            w,
            h,
            f"rounded={int(r>0)};arcSize=10;fillColor={fill};strokeColor={stroke};",
        )

    def text(self, x, y, s, size=26, color=FG, bold=False, anchor="start"):
        e = self.element(
            "text",
            x=x,
            y=y,
            fill=color,
            font_size=size,
            font_family="DejaVu Sans, Arial, sans-serif",
            font_weight="700" if bold else "400",
            text_anchor=anchor,
        )
        e.text = s
        w = len(s) * size * 0.66 + 12
        self.cell(
            x - (w / 2 if anchor == "middle" else w if anchor == "end" else 0),
            y - size,
            w,
            size * 1.45,
            f'text;html=0;align={"center" if anchor=="middle" else "left"};verticalAlign=top;spacing=0;fontFamily=DejaVu Sans;fontSize={size};fontColor={color};fontStyle={int(bold)};strokeColor=none;fillColor=none;',
            s,
        )

    def line(self, pts, color=MUT, width=2, dashed=False, arrow=False):
        pts = np.asarray(pts, dtype=float)
        self.element(
            "polyline",
            points=" ".join(f"{x:.2f},{y:.2f}" for x, y in pts),
            fill="none",
            stroke=color,
            stroke_width=width,
            stroke_linejoin="round",
            stroke_linecap="round",
            stroke_dasharray="9 7" if dashed else "none",
        )
        self.n += 1
        c = ET.SubElement(
            self.graph,
            "mxCell",
            id=str(self.n),
            edge="1",
            parent="1",
            style=f"endArrow=none;strokeColor={color};strokeWidth={width};dashed={int(dashed)};",
        )
        geo = ET.SubElement(c, "mxGeometry", relative="1", attrib={"as": "geometry"})
        for tag, p in [("sourcePoint", pts[0]), ("targetPoint", pts[-1])]:
            ET.SubElement(geo, "mxPoint", x=str(p[0]), y=str(p[1]), attrib={"as": tag})
        if len(pts) > 2:
            arr = ET.SubElement(geo, "Array", attrib={"as": "points"})
            for x, y in pts[1:-1]:
                ET.SubElement(arr, "mxPoint", x=str(x), y=str(y))
        if arrow:
            d = pts[-1] - pts[-2]
            d /= np.linalg.norm(d)
            p = pts[-1] - d * 13
            q = np.array([-d[1], d[0]]) * 6
            self.poly([pts[-1], p + q, p - q], color)

    def circle(self, x, y, r, fill, stroke="none"):
        self.element(
            "circle", cx=x, cy=y, r=r, fill=fill, stroke=stroke, stroke_width=2
        )
        self.cell(
            x - r,
            y - r,
            r * 2,
            r * 2,
            f"ellipse;fillColor={fill};strokeColor={stroke};strokeWidth=2;",
        )

    def poly(self, pts, fill, stroke="none", opacity=1):
        pts = np.array(pts, float)
        lo = pts.min(0) - 2
        hi = pts.max(0) + 2
        w, h = hi - lo
        p = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
        self.element(
            "polygon",
            points=p,
            fill=fill,
            stroke=stroke,
            stroke_width=1.5,
            fill_opacity=opacity,
        )
        # Each projected face remains individually selectable in the draw.io master.
        local = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts - lo)
        svg = f'<svg xmlns="{NS}" width="{w}" height="{h}"><polygon points="{local}" fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" stroke-width="1.5"/></svg>'
        enc = base64.b64encode(svg.encode()).decode()
        self.cell(
            *lo, w, h, f"shape=image;imageAspect=0;image=data:image/svg+xml,{enc};"
        )

    def image(self, x, y, w, h, im):
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        data = base64.b64encode(buf.getvalue()).decode()
        self.element(
            "image", x=x, y=y, width=w, height=h, href="data:image/png;base64," + data
        )
        self.cell(x, y, w, h, f"shape=image;imageAspect=0;image=data:image/png,{data};")

    def save(self, asset):
        import cairosvg

        svg = ET.tostring(self.root, encoding="utf-8", xml_declaration=True)
        (R / "assets" / f"{asset}.svg").write_bytes(svg)
        cairosvg.svg2png(
            bytestring=svg, write_to=str(R / "assets" / f"{asset}.png"), scale=1.5
        )
        ET.indent(self.mx)
        ET.ElementTree(self.mx).write(
            R / "docs" / f"{self.name}.drawio", encoding="utf-8", xml_declaration=True
        )
        # Content-specific URLs prevent stale same-name images in rendered READMEs.
        for extension in ("png", "svg"):
            source = R / "assets" / f"{asset}.{extension}"
            digest = hashlib.sha256(source.read_bytes()).hexdigest()[:12]
            published = f"{asset}-{digest}.{extension}"
            (source.parent / published).write_bytes(source.read_bytes())
            pattern = rf"{re.escape(asset)}(?:-[0-9a-f]{{12}})?\.{extension}"
            for document in ("README.md", "docs/system.md", "docs/mapping.md",
                             "docs/visual-comparison.md"):
                path = R / document
                text = path.read_text()
                updated = re.sub(pattern, published, text)
                if updated != text:
                    path.write_text(updated)


def iso(origin, scale=1):
    def p(x, y, z=0):
        return (
            np.array(origin) + np.array([(x - y) * 0.866, (x + y) * 0.43 - z]) * scale
        )

    return p


def cube(f, p, x, y, z, w, d, h, color=TEAL, opacity=1):
    a, b, c, e = [p(x, y, z), p(x + w, y, z), p(x + w, y + d, z), p(x, y + d, z)]
    aa, bb, cc, ee = [
        p(x, y, z + h),
        p(x + w, y, z + h),
        p(x + w, y + d, z + h),
        p(x, y + d, z + h),
    ]
    f.poly([b, c, cc, bb], color, "#ffffff", opacity * 0.75)
    f.poly([e, c, cc, ee], color, "#ffffff", opacity * 0.9)
    f.poly([aa, bb, cc, ee], color, "#ffffff", opacity)


def grid(f, p, n=5, step=30, ny=None):
    ny = n if ny is None else ny
    f.poly(
        [p(0, 0), p(n * step, 0), p(n * step, ny * step), p(0, ny * step)],
        "#e8eef5",
        "#cad5e2",
    )
    for i in range(n + 1):
        f.line([p(i * step, 0), p(i * step, ny * step)], "#cfdae5", 1)
    for i in range(ny + 1):
        f.line([p(0, i * step), p(n * step, i * step)], "#cfdae5", 1)


def robot(f, x, y, color=PURPLE, s=1):
    f.poly(
        [
            (x - 49 * s, y - 21 * s),
            (x + 32 * s, y - 21 * s),
            (x + 49 * s, y - 8 * s),
            (x - 33 * s, y - 8 * s),
        ],
        color,
    )
    f.poly(
        [
            (x - 33 * s, y - 8 * s),
            (x + 49 * s, y - 8 * s),
            (x + 49 * s, y + 16 * s),
            (x - 33 * s, y + 16 * s),
        ],
        "#394d70",
    )
    for dx in [-28, 32]:
        for off in [0, 15]:
            f.line(
                [
                    (x + dx * s, y + 9 * s - off * 0.5 * s),
                    (x + (dx + 7) * s, y + 32 * s - off * 0.5 * s),
                    (x + (dx - 4) * s, y + 49 * s - off * 0.5 * s),
                ],
                color,
                5 * s,
            )
    f.circle(x + 43 * s, y + 1 * s, 4 * s, "#ffffff")
    f.rect(x - 19 * s, y - 34 * s, 14 * s, 12 * s, "#617a98", r=2)


def go2_pose(f, p, xy, name, scale=1.55):
    """Same orthographic basis and uniform scale as the surrounding scene."""
    meta = json.loads((R / "assets/diagram-robot/anchors.json").read_text())[name]
    k = 100 * scale / meta["pixels_per_m"]
    origin = p(*xy, 0)
    ox, oy = meta["origin_px"]
    f.image(origin[0]-ox*k, origin[1]-oy*k, 600*k, 600*k,
            Image.open(R / f"assets/diagram-robot/{name}.png"))
    return origin + (np.array(meta["camera_px"]) - [ox, oy]) * k


def route_image(scene, size):
    mission = json.loads((R / "datasets" / f"{scene}-route.json").read_text())
    cloud = read_xyz(R / "datasets" / f"{scene}.pcd")
    route = np.asarray(mission["planned_xy_m"])
    stops = np.asarray([a["observe_xyz_m"][:2] for a in mission["stops"] if a["type"] == "inspection"])
    if scene == "indoor":
        cloud = cloud[:, [1,0,2]] * [1,-1,1]
        route = route[:, [1,0]] * [1,-1]
        stops = stops[:, [1,0]] * [1,-1]
    limits = np.percentile(cloud[:,2], [5,95])
    rgb, proj, scale = map_view(cloud, (route.min(0)-2, route.max(0)+2), size, limits,
                               point_radius=0, background=(16,31,48))
    im = Image.fromarray(rgb); d = ImageDraw.Draw(im)
    d.line(list(map(tuple,proj(route))), fill="white", width=8)
    d.line(list(map(tuple,proj(route))), fill="#16d7b4", width=4)
    for xx,yy in proj(stops):
        d.ellipse((xx-4,yy-4,xx+4,yy+4),fill="#ffb65b",outline="white",width=1)
    y=size[1]-25
    d.rectangle((10,y-10,30+5*scale,y+22),fill="#101f30")
    d.line((20,y,20+5*scale,y),fill="white",width=3)
    d.text((20,y+2),"5 m",font=ImageFont.truetype("DejaVuSans.ttf",17),fill="white")
    return im, limits


def overview():
    from PIL import ImageOps
    f = Figure("system-overview",1800,1190)
    f.rect(0,0,1800,1190,"white")
    f.text(32,57,"Rule-based navigation for quadruped inspection",43,bold=True)
    f.text(34,93,"Survey the scene  /  select observation poses  /  navigate, photograph and return",23,MUT)
    def tag(x,y,letter,title):
        f.rect(x,y,33,32,FG,r=3); f.text(x+16.5,y+24,letter,23,"white",True,"middle")
        f.text(x+45,y+25,title,25,FG,True)
    def fit(name,x,y,w,h):
        im=Image.open(R/"assets"/name).convert("RGB")
        f.image(x,y,w,h,ImageOps.fit(im,(int(w),int(h))))
    tag(32,119,"A","Outdoor field demonstration")
    fit("outdoor-day-field.webp",32,162,1030,636)
    # Separate exterior viewpoint is a genuine field clip, not an inserted robot.
    fit("field-exterior-outdoor.webp",52,547,300,230)
    f.rect(52,751,300,26,"#142b43")
    f.text(63,770,"Separate exterior view",17,"white")
    tag(1088,119,"B","Measured scene · planned route")
    im,limits=route_image("outdoor",(680,210));f.image(1088,162,680,210,im)
    f.text(1090,399,"8 observation stops + return to start",21,TEAL,True)
    tag(1088,423,"C","Inspection navigation pipeline")
    workflow=Image.open(R/"assets/figure-panels/inspection-workflow.png")
    f.image(1082,464,692,330,workflow)
    # Each field/map pair documents a scene; no time synchronization is asserted.
    panels=[(32,"D","Indoor · field","field-exterior-indoor.webp"),
            (478,"E","Indoor · planned route",None),
            (924,"F","Outdoor · field","field-exterior-outdoor.webp"),
            (1370,"G","Outdoor · measured 3D","outdoor-scene-3d.png")]
    for x,letter,title,name in panels:
        tag(x,824,letter,title)
        if name is None:
            im,_=route_image("indoor",(398,234));f.image(x,869,398,234,im)
        else: fit(name,x,869,398,234)
    f.line([(34,1131),(94,1131)],TEAL,4)
    f.text(106,1138,"Planned route",20)
    f.circle(304,1131,6,AMBER);f.text(320,1138,"Observation pose",20)
    f.text(595,1138,"Field clips, scan maps and plans are separate evidence views.",20,MUT)
    f.text(34,1171,"Geometry-based planning · Operator-annotated targets · Supervised execution · No detection or recognition module",20,MUT)
    f.save("system-overview")


def principle():
    f = Figure("navigation-sight-principle", 1600, 1120)
    f.text(42, 62, "Two height bands. One observation pose.", 47, bold=True)
    f.text(
        44,
        106,
        "3D schematics of the geometric tests used during view-pose selection",
        25,
        MUT,
    )
    f.rect(42, 141, 730, 675, "white", "#d8e1eb", 16)
    f.rect(794, 141, 764, 675, "white", "#d8e1eb", 16)
    f.text(65, 185, "01  Separate motion from sight", 30, bold=True)
    f.text(818, 185, "02  Filter candidate viewpoints", 30, bold=True)
    f.text(65, 224, "Count returns in each 0.15 m XY cell.", 23, MUT)
    f.text(818, 224, "Illustrative candidates around an annotated target.", 22, MUT)
    # Three separate columns keep exact band heights legible.
    for i, (title, nav, los) in enumerate(
        [("Low barrier", 2, 0), ("High structure", 0, 2), ("Tall obstacle", 2, 2)]
    ):
        cx = 185 + i * 225
        f.text(cx, 275, title, 23, FG, True, "middle")
        p = iso((cx, 530), 0.82)
        grid(f, p, 2, 44)
        if i == 0:
            cube(f, p, 28, 28, 0, 30, 30, 37, "#8b9caf")
        if i == 1:
            cube(f, p, 28, 28, 144, 30, 30, 27, "#8b9caf")
        if i == 2:
            cube(f, p, 28, 28, 0, 30, 30, 206, "#8b9caf")
        for lo, hi, col in [(16, 62.96, TEAL), (90, 220, AMBER)]:
            # Transparent volume with matching top and bottom planes.
            f.poly(
                [p(0, 88, lo), p(88, 88, lo), p(88, 88, hi), p(0, 88, hi)],
                col,
                col,
                0.10,
            )
            for xx, yy in [(0, 0), (88, 0)]:
                f.line(
                    [p(xx, yy, lo), p(xx, yy, hi)],
                    "#90bfc1" if col == TEAL else "#e0bc85",
                    1.2,
                    True,
                )
            for zz in [lo, hi]:
                f.poly(
                    [p(0, 0, zz), p(88, 0, zz), p(88, 88, zz), p(0, 88, zz)],
                    col,
                    col,
                    0.12,
                )
        for zz in ([29, 43] if nav else []):
            f.circle(*p(44, 60, zz), 5, TEAL, "white")
        for zz in ([143, 160] if los else []):
            f.circle(*p(44, 60, zz), 5, AMBER, "white")
        f.text(cx, 626, f"NAV   {nav} returns", 22, TEAL, bool(nav), "middle")
        f.text(cx, 663, f"LOS   {los} returns", 22, AMBER, bool(los), "middle")
    f.rect(65, 697, 680, 43, "#e4f3f3", r=6)
    f.text(79, 726, "NAV   0.16 < h < 0.6296 m", 25, TEAL, True)
    f.rect(65, 748, 680, 43, "#fff0dc", r=6)
    f.text(79, 777, "LOS   0.90 < h < 2.20 m", 25, AMBER, True)
    # The mesh and all geometry share the VTK orthographic projection exactly.
    metas=json.loads((R/"assets/diagram-robot/anchors.json").read_text())
    basis=np.asarray(metas["selected"]["projection_basis_px"]).T/metas["selected"]["pixels_per_m"]
    scale=1.45
    def p(x,y,z=0): return np.array([1060,600])+basis@np.array([x,y,z])*scale
    f.poly([p(-20,-100),p(380,-100),p(380,200),p(-20,200)],"#edf2f7","#cbd7e4")
    for x in range(0,381,40): f.line([p(x,-100),p(x,200)],"#d0dce8",1)
    for y in range(-100,201,40): f.line([p(-20,y),p(380,y)],"#d0dce8",1)
    target3=np.array([140,-80,120.])
    target=p(*target3)
    # Clearance buffer is deliberately more conservative than the physical body.
    poses=[(90,40,"clearance","A",RED),(340,0,"blocked","B",RED),(20,150,"selected","C",TEAL)]
    for x,y,name,letter,col in poses:
        ring=[p(x+55*math.cos(t),y+55*math.sin(t),.5) for t in np.linspace(0,2*math.pi,64)]
        f.poly(ring,col,"none",.06);f.line(ring,col,1.4,True)
    def scene_box(x,y,w,d,h,col):
        # Camera lies in (-X,-Y): draw the two near faces, then the top.
        a,b,c,e=[p(x,y),p(x+w,y),p(x+w,y+d),p(x,y+d)]
        aa,bb,cc,ee=[p(x,y,h),p(x+w,y,h),p(x+w,y+d,h),p(x,y+d,h)]
        f.poly([a,b,bb,aa],col,"white",.85)
        f.poly([a,e,ee,aa],col,"white",.7)
        f.poly([aa,bb,cc,ee],col,"white")
    scene_box(210,-53,35,16,115,"#8d9fb3")
    scene_box(135,48,25,20,30,TEAL)
    anchors={}
    for x,y,name,letter,col in poses:
        anchors[letter]=go2_pose(f,p,(x,y),name,scale)
        d=(target3[:2]-[x,y]);d/=np.linalg.norm(d)
        f.line([p(x+d[0]*38,y+d[1]*38,1),p(x+d[0]*66,y+d[1]*66,1)],col,2,arrow=True)
        q=p(x-15,y+40,0);f.circle(*q,14,col,"white");f.text(q[0],q[1]+6,letter,18,"white",True,"middle")
    cam3=np.array(metas["blocked"]["camera_local_m"])*100+[340,0,0]
    t=(245-cam3[0])/(target3[0]-cam3[0]);hit3=cam3+t*(target3-cam3);hit=p(*hit3)
    f.line([anchors["B"],hit],RED,3,True);f.line([hit,target],"#a1afbd",2,True)
    f.line([hit+[-7,-7],hit+[7,7]],RED,3);f.line([hit+[-7,7],hit+[7,-7]],RED,3)
    f.line([anchors["C"],target],TEAL,3.5,arrow=True)
    # Horizontal forward reference: fixed camera is not mechanically pitched.
    c3=np.array(metas["selected"]["camera_local_m"])*100+[20,150,0]
    horizontal=p(140,-80,c3[2]);v=horizontal-anchors["C"];v/=np.linalg.norm(v)
    f.line([anchors["C"],anchors["C"]+v*95],TEAL,1.5,True)
    f.text(anchors["C"][0]+60,anchors["C"][1]-5,"θ",22,TEAL,True)
    for letter,col in [("B",RED),("C",TEAL)]:f.circle(*anchors[letter],4,col,"white")
    f.line([p(140,-80,0),target],AMBER,1.5,True)
    f.circle(*target,10,AMBER,"white");f.text(target[0]-65,target[1]-24,"Target",23,AMBER,True)
    f.text(818,665,"A   Rejected: conservative NAV clearance margin",23,RED,True)
    f.text(818,710,"B   Rejected: blocked XY sight mask",23,RED,True)
    f.text(818,755,"C   Selected: position + yaw + viewing elevation",23,TEAL,True)
    f.text(818,793,"Front camera anchors are illustrative; feet share the ground plane.",18,MUT)
    # Combined pipeline kept large enough to read in a GitHub README.
    yy = 851
    for x, w, col, title, detail in [
        (42, 360, BLUE, "Candidate positions", "Trajectory first; grid fallback"),
        (445, 360, TEAL, "Geometry checks", "Range + LOS; NAV on grid"),
        (848, 360, AMBER, "Camera checks", "Elevation within vertical FOV"),
        (1251, 307, PURPLE, "Observation pose", "XYZ + yaw + elevation"),
    ]:
        f.rect(x, yy, w, 121, "white", "#d8e1eb", 12)
        f.rect(x, yy, 6, 121, col, r=2)
        f.text(x + 18, yy + 43, title, 25, col, True)
        f.text(x + 18, yy + 83, detail, 20, MUT)
        if x < 1251:
            f.line([(x + w + 6, yy + 60), (x + w + 34, yy + 60)], MUT, 2, arrow=True)
    f.text(
        44,
        1010,
        "h is relative to estimated local ground. Each band flags a cell at ≥2 returns; bounds are strict.",
        23,
        MUT,
    )
    f.text(
        44,
        1050,
        "Illustrative geometry, uncalibrated optics. Below threshold does not establish safe passage or a clear view.",
        23,
        MUT,
    )
    f.text(
        44,
        1090,
        "Uncalibrated camera anchors; LOS checks XY masks, not 3D rays. Fallbacks can relax LOS.",
        22,
        MUT,
    )
    f.save("navigation-sight-layers")


if __name__ == "__main__":
    overview()
    principle()

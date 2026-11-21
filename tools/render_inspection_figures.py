"""Generate original SVG/PNG figures and editable draw.io primitive masters.

NumPy/Pillow read the published metric datasets; CairoSVG exports the PNGs.
All schematics are illustrative, not newly measured or simulated results.
"""
from pathlib import Path
import base64
import io
import json
import math
import xml.etree.ElementTree as ET
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from tools.point_cloud import read_xyz, map_view, HEIGHT_COLORS

R = Path(__file__).resolve().parents[1]
BG, FG, MUT = '#f8fafc', '#142b43', '#52677c'
BLUE, TEAL, AMBER, PURPLE, RED = '#2563eb', '#008b8b', '#ca750d', '#7952ca', '#c34654'
NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)

class Figure:
    def __init__(self, name, w, h):
        self.name, self.w, self.h = name, w, h
        self.root = ET.Element('svg', xmlns=NS, width=str(w), height=str(h), viewBox=f'0 0 {w} {h}')
        self.mx = ET.Element('mxfile', host='app.diagrams.net')
        d = ET.SubElement(self.mx, 'diagram', name=name, id=name)
        m = ET.SubElement(d, 'mxGraphModel', page='1', pageWidth=str(w), pageHeight=str(h), background=BG)
        self.graph = ET.SubElement(m, 'root')
        ET.SubElement(self.graph, 'mxCell', id='0')
        ET.SubElement(self.graph, 'mxCell', id='1', parent='0')
        self.n = 1
        self.rect(0,0,w,h,BG)
    def cell(self, x,y,w,h,style,value=''):
        self.n += 1
        c=ET.SubElement(self.graph,'mxCell',id=str(self.n),value=value,style=style,vertex='1',parent='1')
        ET.SubElement(c,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),attrib={'as':'geometry'})
    def element(self,tag,**attrs):
        return ET.SubElement(self.root,tag,{k.replace('_','-'):str(v) for k,v in attrs.items()})
    def rect(self,x,y,w,h,fill='white',stroke='none',r=0):
        self.element('rect',x=x,y=y,width=w,height=h,fill=fill,stroke=stroke,rx=r)
        self.cell(x,y,w,h,f'rounded={int(r>0)};arcSize=10;fillColor={fill};strokeColor={stroke};')
    def text(self,x,y,s,size=26,color=FG,bold=False,anchor='start'):
        e=self.element('text',x=x,y=y,fill=color,font_size=size,font_family='DejaVu Sans, Arial, sans-serif',font_weight='700' if bold else '400',text_anchor=anchor)
        e.text=s
        w=len(s)*size*.66+12
        self.cell(x-(w/2 if anchor=='middle' else w if anchor=='end' else 0),y-size,w,size*1.45,f'text;html=0;align={"center" if anchor=="middle" else "left"};verticalAlign=top;spacing=0;fontFamily=DejaVu Sans;fontSize={size};fontColor={color};fontStyle={int(bold)};strokeColor=none;fillColor=none;',s)
    def line(self,pts,color=MUT,width=2,dashed=False,arrow=False):
        pts=np.asarray(pts,dtype=float)
        self.element('polyline',points=' '.join(f'{x:.2f},{y:.2f}' for x,y in pts),fill='none',stroke=color,stroke_width=width,stroke_linejoin='round',stroke_linecap='round',stroke_dasharray='9 7' if dashed else 'none')
        self.n+=1
        c=ET.SubElement(self.graph,'mxCell',id=str(self.n),edge='1',parent='1',style=f'endArrow=none;strokeColor={color};strokeWidth={width};dashed={int(dashed)};')
        geo=ET.SubElement(c,'mxGeometry',relative='1',attrib={'as':'geometry'})
        for tag,p in [('sourcePoint',pts[0]),('targetPoint',pts[-1])]:
            ET.SubElement(geo,'mxPoint',x=str(p[0]),y=str(p[1]),attrib={'as':tag})
        if len(pts)>2:
            arr=ET.SubElement(geo,'Array',attrib={'as':'points'})
            for x,y in pts[1:-1]: ET.SubElement(arr,'mxPoint',x=str(x),y=str(y))
        if arrow:
            d=pts[-1]-pts[-2]; d/=np.linalg.norm(d); p=pts[-1]-d*13; q=np.array([-d[1],d[0]])*6
            self.poly([pts[-1],p+q,p-q],color)
    def circle(self,x,y,r,fill,stroke='none'):
        self.element('circle',cx=x,cy=y,r=r,fill=fill,stroke=stroke,stroke_width=2)
        self.cell(x-r,y-r,r*2,r*2,f'ellipse;fillColor={fill};strokeColor={stroke};strokeWidth=2;')
    def poly(self,pts,fill,stroke='none',opacity=1):
        pts=np.array(pts,float); lo=pts.min(0)-2; hi=pts.max(0)+2; w,h=hi-lo
        p=' '.join(f'{x:.2f},{y:.2f}' for x,y in pts)
        self.element('polygon',points=p,fill=fill,stroke=stroke,stroke_width=1.5,fill_opacity=opacity)
        # Each projected face remains individually selectable in the draw.io master.
        local=' '.join(f'{x:.2f},{y:.2f}' for x,y in pts-lo)
        svg=f'<svg xmlns="{NS}" width="{w}" height="{h}"><polygon points="{local}" fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" stroke-width="1.5"/></svg>'
        enc=base64.b64encode(svg.encode()).decode()
        self.cell(*lo,w,h,f'shape=image;imageAspect=0;image=data:image/svg+xml,{enc};')
    def image(self,x,y,w,h,im):
        buf=io.BytesIO(); im.save(buf,format='PNG'); data=base64.b64encode(buf.getvalue()).decode()
        self.element('image',x=x,y=y,width=w,height=h,href='data:image/png;base64,'+data)
        self.cell(x,y,w,h,f'shape=image;imageAspect=0;image=data:image/png,{data};')
    def save(self,asset):
        import cairosvg
        svg=ET.tostring(self.root,encoding='utf-8',xml_declaration=True)
        (R/'assets'/f'{asset}.svg').write_bytes(svg)
        cairosvg.svg2png(bytestring=svg,write_to=str(R/'assets'/f'{asset}.png'),scale=1.5)
        ET.indent(self.mx)
        ET.ElementTree(self.mx).write(R/'docs'/f'{self.name}.drawio',encoding='utf-8',xml_declaration=True)


def iso(origin, scale=1):
    def p(x,y,z=0): return np.array(origin)+np.array([(x-y)*.866,(x+y)*.43-z])*scale
    return p


def cube(f,p,x,y,z,w,d,h,color=TEAL,opacity=1):
    a,b,c,e=[p(x,y,z),p(x+w,y,z),p(x+w,y+d,z),p(x,y+d,z)]
    aa,bb,cc,ee=[p(x,y,z+h),p(x+w,y,z+h),p(x+w,y+d,z+h),p(x,y+d,z+h)]
    f.poly([b,c,cc,bb],color,'#ffffff',opacity*.75)
    f.poly([e,c,cc,ee],color,'#ffffff',opacity*.9)
    f.poly([aa,bb,cc,ee],color,'#ffffff',opacity)


def grid(f,p,n=5,step=30):
    f.poly([p(0,0),p(n*step,0),p(n*step,n*step),p(0,n*step)],'#e8eef5','#cad5e2')
    for i in range(n+1):
        f.line([p(i*step,0),p(i*step,n*step)],'#cfdae5',1)
        f.line([p(0,i*step),p(n*step,i*step)],'#cfdae5',1)


def robot(f,x,y,color=PURPLE,s=1):
    f.poly([(x-49*s,y-21*s),(x+32*s,y-21*s),(x+49*s,y-8*s),(x-33*s,y-8*s)],color)
    f.poly([(x-33*s,y-8*s),(x+49*s,y-8*s),(x+49*s,y+16*s),(x-33*s,y+16*s)],'#394d70')
    for dx in [-28,32]:
        for off in [0,15]:
            f.line([(x+dx*s,y+9*s-off*.5*s),(x+(dx+7)*s,y+32*s-off*.5*s),(x+(dx-4)*s,y+49*s-off*.5*s)],color,5*s)
    f.circle(x+43*s,y+1*s,4*s,'#ffffff')
    f.rect(x-19*s,y-34*s,14*s,12*s,'#617a98',r=2)


def overview():
    f=Figure('system-overview',1600,1110)
    f.text(42,62,'From LiDAR survey to inspection route',48,bold=True)
    f.text(44,106,'Measured maps  /  geometric rules  /  supervised inspection',25,MUT)
    colors=[BLUE,TEAL,AMBER,PURPLE]
    titles=['Scan & map','Select poses','Plan the route','Walk & inspect']
    details=['XT16 + IMU → LIO-SAM','Clearance + visibility','Dijkstra graph distances','Go2 EDU → photos + logs']
    for i,(col,title,detail) in enumerate(zip(colors,titles,details)):
        x=42+i*391
        f.rect(x,144,343,294,'#ffffff','#d8e1eb',18)
        f.rect(x,144,343,8,col,r=3)
        f.text(x+20,187,f'0{i+1}  {title}',29,col,True)
        p=iso((x+176,243),.83)
        if i==0:
            grid(f,p,4,26)
            rng=np.random.default_rng(8)
            for xx,yy,zz in rng.uniform([5,5,0],[98,98,65],(100,3)):
                u,v=p(xx,yy,zz); f.circle(u,v,2.4,colors[int(zz//18)%4])
            f.circle(x+66,254,10,BLUE)
            for dy in [-28,0,28]: f.line([(x+68,254),(x+145,254+dy)],BLUE,2,True)
        elif i==1:
            grid(f,p,4,26)
            cube(f,p,20,20,0,20,20,55,AMBER)
            f.poly([p(3,0,25),p(105,0,25),p(105,105,25),p(3,105,25)],TEAL,TEAL,.16)
            f.poly([p(3,0,66),p(105,0,66),p(105,105,66),p(3,105,66)],AMBER,AMBER,.17)
            a=p(15,90,8); b=p(105,5,92); f.line([a,b],AMBER,3,arrow=True); f.circle(*a,8,TEAL,'white'); f.circle(*b,6,AMBER,'white')
        elif i==2:
            grid(f,p,4,26)
            cube(f,p,38,32,0,28,38,24,'#99abc0')
            path=[p(8,90,3),p(8,14,3),p(85,14,3),p(85,85,3)]
            f.line(path,TEAL,5)
            for pt in [path[0],path[2],path[3]]: f.circle(*pt,6,AMBER,'white')
        else:
            grid(f,p,4,26)
            f.line([(x+58,344),(x+121,324),(x+175,326)],TEAL,4,True)
            robot(f,x+195,285,PURPLE,.88)
            f.rect(x+265,241,45,33,'#eee8fa',PURPLE,4)
            f.circle(x+288,258,9,'white',PURPLE)
            f.line([(x+240,287),(x+265,258)],PURPLE,2,True)
        f.text(x+20,408,detail,22,MUT)
        if i<3: f.line([(x+350,290),(x+382,290)],'#7b8da2',3,arrow=True)
    f.text(46,477,'Operator annotations identify inspection targets before pose selection.',23,MUT)
    for i,scene in enumerate(['indoor','outdoor']):
        x=42+786*i
        f.rect(x,511,730,524,'white','#d8e1eb',16)
        mission=json.loads((R/'datasets'/f'{scene}-route.json').read_text())
        cloud=read_xyz(R/'datasets'/f'{scene}.pcd')
        route=np.asarray(mission['planned_xy_m'])
        stops=np.asarray([a['observe_xyz_m'][:2] for a in mission['stops'] if a['type']=='inspection'])
        if scene=='indoor':
            cloud=cloud[:,[1,0,2]]*[1,-1,1]; route=route[:,[1,0]]*[1,-1]; stops=stops[:,[1,0]]*[1,-1]
        limits=np.percentile(cloud[:,2],[5,95])
        rgb,proj,scale=map_view(cloud,(route.min(0)-2,route.max(0)+2),(694,378),limits,point_radius=0,background=(16,31,48))
        im=Image.fromarray(rgb); d=ImageDraw.Draw(im)
        d.line(list(map(tuple,proj(route))),fill='white',width=8)
        d.line(list(map(tuple,proj(route))),fill='#16d7b4',width=4)
        for xx,yy in proj(stops): d.ellipse((xx-4,yy-4,xx+4,yy+4),fill='#ffb65b',outline='white',width=1)
        d.rectangle((10,333,125,375),fill='#101f30')
        d.line((20,343,20+5*scale,343),fill='white',width=3)
        d.text((20,349),'5 m',font=ImageFont.truetype('DejaVuSans.ttf',23),fill='white')
        f.text(x+20,554,scene.title(),31,bold=True)
        f.text(x+710,553,f'{len(stops)} planned stops',25,TEAL,True,'end')
        f.image(x+18,574,694,378,im)
        f.text(x+22,993,'Map Z (m)',21,MUT)
        for k in range(180):
            t=k/179*4;j=min(3,int(t)); c=(HEIGHT_COLORS[j]*(1-(t-j))+HEIGHT_COLORS[j+1]*(t-j)).astype(int)
            f.rect(x+157+k,978,1.2,13,'#%02x%02x%02x'%tuple(c))
        f.text(x+150,1020,f'{limits[0]:.1f}',22,MUT)
        f.text(x+320,1020,f'{limits[1]:.1f}',22,MUT)
    f.line([(52,1074),(106,1074)],TEAL,5);f.text(119,1082,'Planned route',23)
    f.circle(374,1074,7,AMBER);f.text(391,1082,'Observation pose',23)
    f.text(890,1082,'Maps: measured  ·  Routes: planned',23,MUT)
    f.save('system-overview')


def principle():
    f=Figure('navigation-sight-principle',1600,1120)
    f.text(42,62,'Two height bands. One observation pose.',47,bold=True)
    f.text(44,106,'3D schematics of the geometric tests used during view-pose selection',25,MUT)
    f.rect(42,141,730,675,'white','#d8e1eb',16)
    f.rect(794,141,764,675,'white','#d8e1eb',16)
    f.text(65,185,'01  Separate motion from sight',30,bold=True)
    f.text(818,185,'02  Filter candidate viewpoints',30,bold=True)
    f.text(65,224,'Count returns in each 0.15 m XY cell.',23,MUT)
    f.text(818,224,'Illustrative candidates around an annotated target.',22,MUT)
    # Three separate columns keep exact band heights legible.
    for i,(title,nav,los) in enumerate([('Low barrier',2,0),('High structure',0,2),('Tall obstacle',2,2)]):
        cx=185+i*225
        f.text(cx,275,title,23,FG,True,'middle')
        p=iso((cx,530),.82)
        grid(f,p,2,44)
        if i==0: cube(f,p,28,28,0,30,30,37,'#8b9caf')
        if i==1: cube(f,p,28,28,144,30,30,27,'#8b9caf')
        if i==2: cube(f,p,28,28,0,30,30,206,'#8b9caf')
        for lo,hi,col in [(16,62.96,TEAL),(90,220,AMBER)]:
            # Transparent volume with matching top and bottom planes.
            f.poly([p(0,88,lo),p(88,88,lo),p(88,88,hi),p(0,88,hi)],col,col,.10)
            for xx,yy in [(0,0),(88,0)]:
                f.line([p(xx,yy,lo),p(xx,yy,hi)],'#90bfc1' if col==TEAL else '#e0bc85',1.2,True)
            for zz in [lo,hi]:
                f.poly([p(0,0,zz),p(88,0,zz),p(88,88,zz),p(0,88,zz)],col,col,.12)
        for zz in ([29,43] if nav else []): f.circle(*p(44,60,zz),5,TEAL,'white')
        for zz in ([143,160] if los else []): f.circle(*p(44,60,zz),5,AMBER,'white')
        f.text(cx,626,f'NAV   {nav} returns',22,TEAL,bool(nav),'middle')
        f.text(cx,663,f'LOS   {los} returns',22,AMBER,bool(los),'middle')
    f.rect(65,697,680,43,'#e4f3f3',r=6)
    f.text(79,726,'NAV   0.16 < h < 0.6296 m',25,TEAL,True)
    f.rect(65,748,680,43,'#fff0dc',r=6)
    f.text(79,777,'LOS   0.90 < h < 2.20 m',25,AMBER,True)
    # Oblique candidate scene: all geometry is explanatory, not data.
    p=iso((1178,381),1.3)
    grid(f,p,6,30)
    cube(f,p,102,66,0,44,14,105,'#91a3bb')
    cube(f,p,31,113,0,28,26,28,TEAL)
    a,b,c=[p(55,147,8),p(147,144,8),p(15,20,8)]
    c_camera=p(15,20,85)
    for x,y,col in [(55,147,RED),(15,20,TEAL)]:
        ring=[p(x+19*math.cos(t),y+19*math.sin(t),2) for t in np.linspace(0,2*math.pi,40)]
        f.poly(ring,col,'none',.10)
        f.line(ring,col,1.8,True)
    target=p(130,25,90)
    f.line([b,p(137,80,58)],RED,4,True)
    f.line([p(137,80,58),target],'#9dabbc',2,True)
    f.line([c,c_camera],TEAL,1.8,True)
    f.circle(*c_camera,4,TEAL)
    f.line([c_camera,target],TEAL,4,arrow=True)
    f.poly([c_camera,p(123,23,100),p(140,29,75)],TEAL,'none',.10)
    f.line([p(130,25,0),target],AMBER,1.8,True)
    f.circle(*p(130,25,0),5,'white',AMBER)
    hit=p(137,80,58)
    f.line([hit+[-7,-7],hit+[7,7]],RED,3)
    f.line([hit+[-7,7],hit+[7,-7]],RED,3)
    for pt,name,col in [(a,'A',RED),(b,'B',RED),(c,'C',TEAL)]:
        f.circle(*pt,13,col,'white');f.text(pt[0],pt[1]+6,name,18,'white',True,'middle')
    f.circle(*target,11,AMBER,'white')
    f.line([target,target+[32,-30]],AMBER,2)
    f.text(target[0]-15,target[1]-43,'Target',24,AMBER,True)
    f.text(818,677,'A   Rejected: navigation clearance',24,RED,True)
    f.text(818,720,'B   Rejected: blocked sight ray',24,RED,True)
    f.text(818,763,'C   Selected: position + viewing direction',24,TEAL,True)
    # Combined pipeline kept large enough to read in a GitHub README.
    yy=851
    for x,w,col,title,detail in [(42,360,BLUE,'Candidate positions','Recorded trajectory first'),(445,360,TEAL,'Geometry checks','Navigation + sight + distance'),(848,360,AMBER,'Camera checks','Elevation within vertical FOV'),(1251,307,PURPLE,'Observation pose','XYZ + yaw + elevation')]:
        f.rect(x,yy,w,121,'white','#d8e1eb',12);f.rect(x,yy,6,121,col,r=2)
        f.text(x+18,yy+43,title,25,col,True)
        f.text(x+18,yy+83,detail,20,MUT)
        if x<1251: f.line([(x+w+6,yy+60),(x+w+34,yy+60)],MUT,2,arrow=True)
    f.text(44,1010,'h is relative to estimated local ground. Each band flags a cell at ≥2 returns; bounds are strict.',23,MUT)
    f.text(44,1050,'Schematic only, not to scale. Below threshold does not establish safe passage or a clear view.',23,MUT)
    f.text(44,1090,'Trajectory-first and grid-fallback checks differ; staged fallbacks can relax visibility. See mapping notes.',22,MUT)
    f.save('navigation-sight-layers')

if __name__=='__main__':
    overview()
    principle()

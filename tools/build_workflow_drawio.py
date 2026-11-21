"""Build the editable draw.io workflow used in the multi-panel overview."""
from pathlib import Path
import xml.etree.ElementTree as ET
R=Path(__file__).resolve().parents[1]

def build():
    model=ET.Element('mxGraphModel',dx='900',dy='454',page='1',pageWidth='900',pageHeight='454',background='#ffffff',adaptiveColors='none')
    root=ET.SubElement(model,'root');ET.SubElement(root,'mxCell',id='0');ET.SubElement(root,'mxCell',id='1',parent='0')
    def node(id,label,x,y,w,h,fill='#ffffff',stroke='#bdd2d8',font='#163743',size=22,parent='1',extra=''):
        c=ET.SubElement(root,'mxCell',id=id,value=label,vertex='1',parent=parent,style=f'rounded=1;arcSize=12;whiteSpace=wrap;html=1;fontFamily=Helvetica;fontSize={size};fontColor={font};fillColor={fill};strokeColor={stroke};strokeWidth=1.5;spacing=6;{extra}')
        ET.SubElement(c,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),attrib={'as':'geometry'})
    def edge(id,a,b,col='#667a84',dashed=False,extra=''):
        c=ET.SubElement(root,'mxCell',id=id,edge='1',parent='1',source=a,target=b,style=f'edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=classic;endSize=9;strokeWidth=2;strokeColor={col};dashed={int(dashed)};{extra}')
        ET.SubElement(c,'mxGeometry',relative='1',attrib={'as':'geometry'})
    node('pose_group','',220,20,360,360,'#e8f3f3','#e8f3f3',extra='container=1;pointerEvents=0;')
    node('route_group','',600,20,280,360,'#f9efdf','#f9efdf',extra='container=1;pointerEvents=0;')
    node('map','Map + trajectory',10,80,185,74,'#f3f6f8','#cad7e0')
    node('targets','Target annotations',10,240,185,74,'#f3f6f8','#cad7e0')
    node('nav','NAV',205,30,135,60,'#ffffff','#6baeb2',size=23,parent='pose_group')
    node('los','LOS',20,30,135,60,'#ffffff','#6baeb2',size=23,parent='pose_group')
    node('search','Candidate search',55,135,250,64,'#ffffff','#6baeb2',parent='pose_group')
    node('poses','Observation poses',55,258,250,64,'#ffffff','#6baeb2',parent='pose_group')
    node('paths','Dijkstra leg paths',25,38,230,66,'#ffffff','#cba266',parent='route_group')
    node('mission','Visit order + return',25,156,230,66,'#ffffff','#cba266',parent='route_group')
    node('capture','Navigate + capture',25,274,230,66,'#ffffff','#cba266',parent='route_group')
    edge('e_map','map','search',extra='exitX=1;exitY=0.5;entryX=0;entryY=0.25;')
    edge('e_targets','targets','search',extra='exitX=1;exitY=0.5;entryX=0;entryY=0.75;')
    edge('e_nav','nav','search','#12858c',True);edge('e_los','los','search','#12858c')
    edge('e_nav_paths','nav','paths','#12858c',extra='exitX=1;exitY=0.5;entryX=0;entryY=0.2;')
    edge('e_pose','search','poses','#12858c',extra='exitX=0.1;exitY=1;entryX=0.1;entryY=0;')
    edge('e_route','poses','paths','#b37b29',extra='exitX=1;exitY=0.5;entryX=0;entryY=0.5;')
    edge('e_mission','paths','mission','#b37b29');edge('e_capture','mission','capture','#b37b29')
    node('pose_note','Range · XY LOS · FOV',310,226,260,38,fill='none',stroke='none',font='#163743',size=23)
    node('scope','Trajectory first; NAV checked on grid fallback<br>LOS can be relaxed',10,384,870,66,fill='none',stroke='none',font='#163743',size=24)
    mx=ET.Element('mxfile',host='app.diagrams.net');d=ET.SubElement(mx,'diagram',name='Inspection workflow',id='workflow');d.append(model)
    ET.indent(mx);ET.ElementTree(mx).write(R/'docs/inspection-workflow.drawio',encoding='utf-8',xml_declaration=True)
    return ET.tostring(model,encoding='unicode')
if __name__=='__main__':build()

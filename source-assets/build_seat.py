"""Procedurally builds a stylized airline seat compatible with web GLB viewers.
Reference: user's lime-green/white undergraduate aircraft cabin render.
Coordinate frame: meters, Y up, passenger faces +Z, front-center of seat at origin X=0.
Install: pip install numpy trimesh pillow scipy
Run: python build_seat.py
"""
import io, math, os
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter
import trimesh
from trimesh.visual.material import PBRMaterial
from trimesh.visual.texture import TextureVisuals

HERE = Path(__file__).resolve().parent

GREEN = (104, 215, 31, 255)
GREEN_DARK = (64, 154, 21, 255)
GREEN_TRIM = (103, 191, 37, 255)
IVORY = (233, 238, 231, 255)
SHELL = (229, 233, 225, 255)
WHITE = (244, 247, 240, 255)
PLASTIC_SHADOW = (192, 201, 192, 255)
SCREEN = (21, 33, 28, 255)
SCREEN_GLASS = (36, 56, 46, 255)
STEEL = (137, 149, 140, 255)

# A tiny woven grain similar to the source CGI, embedded as a lightweight texture.
rng = np.random.default_rng(44)
ss = 384
noise = rng.normal(0, 2.4, size=(ss, ss))
ygrid, xgrid = np.mgrid[0:ss, 0:ss]
weave = 2.9*np.sin((xgrid + ygrid*.15) * np.pi/3.3) + 1.8*np.cos((ygrid-xgrid*.11) * np.pi/3.7)
base = np.array(GREEN[:3])[None,None,:]
texarr = np.clip(base + (noise+weave)[:,:,None], 0, 255).astype(np.uint8)
tex = Image.fromarray(texarr, mode='RGB')
tex.save(HERE/'green_fabric_texture.png')

mats = {
    'lime upholstery': PBRMaterial(name='Lime woven fabric', baseColorTexture=tex, baseColorFactor=np.array([255,255,255,255],dtype=np.uint8), roughnessFactor=.93, metallicFactor=0., doubleSided=True),
    'lime accent': PBRMaterial(name='Lime arm caps', baseColorFactor=np.array(GREEN_TRIM,dtype=np.uint8), roughnessFactor=.68, metallicFactor=0., doubleSided=True),
    'green stitch': PBRMaterial(name='Subtle green seat stitching',baseColorFactor=np.array(GREEN_DARK,dtype=np.uint8), roughnessFactor=.98, metallicFactor=0., doubleSided=True),
    'shell': PBRMaterial(name='Warm-white molded seat shell', baseColorFactor=np.array(SHELL,dtype=np.uint8), roughnessFactor=.69, metallicFactor=.02, doubleSided=True),
    'white': PBRMaterial(name='Warm-white shell trim',baseColorFactor=np.array(WHITE,dtype=np.uint8), roughnessFactor=.63, metallicFactor=.0, doubleSided=True),
    'shadow': PBRMaterial(name='Light-grey panel accents',baseColorFactor=np.array(PLASTIC_SHADOW,dtype=np.uint8), roughnessFactor=.85, metallicFactor=.0, doubleSided=True),
    'screen rim': PBRMaterial(name='Seatback display bezel',baseColorFactor=np.array(SCREEN,dtype=np.uint8), roughnessFactor=.68, metallicFactor=0., doubleSided=True),
    'screen': PBRMaterial(name='Dark dormant seatback display',baseColorFactor=np.array(SCREEN_GLASS,dtype=np.uint8), roughnessFactor=.19, metallicFactor=.07, doubleSided=True),
    'steel': PBRMaterial(name='Satin metal supports',baseColorFactor=np.array(STEEL,dtype=np.uint8),roughnessFactor=.52,metallicFactor=.70,doubleSided=True),
}

scene = trimesh.Scene()
objects=[]

def add(name,mesh,mat,uv=None):
    mesh.remove_unreferenced_vertices()
    mesh.fix_normals()
    if uv is None:
        verts=np.asarray(mesh.vertices)
        uv=np.column_stack([(verts[:,0]+.5)*1.1, (verts[:,1]+verts[:,2]+1.0)*1.1])
    mesh.visual = TextureVisuals(uv=np.asarray(uv), material=mats[mat])
    scene.add_geometry(mesh, geom_name=name, node_name=name)
    objects.append((name,mesh,mat))
    return mesh

def outline(w,h,r,n=12):
    """Counterclockwise rounded 2D rectangle centered at zero (2 floats per pt)."""
    a=[]
    for cx,cy,start in [(w/2-r,h/2-r,0),(-w/2+r,h/2-r,90),(-w/2+r,-h/2+r,180),(w/2-r,-h/2+r,270)]:
        for t in np.linspace(math.radians(start),math.radians(start+90),n,endpoint=False):
            a.append((cx+r*math.cos(t),cy+r*math.sin(t)))
    return np.asarray(a)

def shell_back_z(y):
    return -.185-(y-.50)*.20


def back_loft(width,height,ycenter,corner,profiles,nm,mat,taper=False):
    """Smooth cushion/body loft in the XY plane. Profiles back to front, with XY scale and Z offset."""
    pl=outline(width,height,corner)
    ringlen=len(pl)
    vertices=[]; uvs=[]; faces=[]
    for scale,dz in profiles:
        for x,ylocal in pl:
            y=ycenter+ylocal*scale
            xt = x*scale
            if taper: xt*= (1.-.09*max(0,(y-.78)/.5))
            z=shell_back_z(y)+dz
            vertices.append((xt,y,z))
            uvs.append(((xt/width)+.5,(y-.47)/.85))
    for ridx in range(len(profiles)-1):
        for i in range(ringlen):
            a=ridx*ringlen+i;b=ridx*ringlen+(i+1)%ringlen
            c=(ridx+1)*ringlen+(i+1)%ringlen;d=(ridx+1)*ringlen+i
            faces.extend([[a,b,c],[a,c,d]])
    # Cap each end as an n-gon fan, with central profile adjusted for slight upholstered bulge.
    for profile_id,front in [(0,False),(len(profiles)-1,True)]:
        centeridx=len(vertices)
        cen_z=shell_back_z(ycenter)+profiles[profile_id][1]+(.012 if front else -.005)
        vertices.append((0,ycenter,cen_z));uvs.append((.5,(ycenter-.47)/.85))
        for i in range(ringlen):
            a=profile_id*ringlen+i;b=profile_id*ringlen+(i+1)%ringlen
            faces.append([centeridx,a,b] if front else [centeridx,b,a])
    mesh=trimesh.Trimesh(vertices=np.array(vertices),faces=np.array(faces),process=False)
    return add(nm,mesh,mat,uvs)


def seat_loft(width,depth,zcenter,profiles,nm,mat):
    """Loft in XZ (horizontal seat cushion): profiles bottom to top."""
    pl=outline(width,depth,min(.09,width/5,depth/5))
    ringlen=len(pl);vertices=[];uvs=[];faces=[]
    for scale,y in profiles:
        for x,zl in pl:
            z=zcenter+zl*scale
            vertices.append((x*scale,y,z)); uvs.append((x/width+.5, z/depth+.5))
    for r in range(len(profiles)-1):
        for i in range(ringlen):
            a=r*ringlen+i;b=r*ringlen+(i+1)%ringlen
            c=(r+1)*ringlen+(i+1)%ringlen;d=(r+1)*ringlen+i
            faces.extend([(a,b,c),(a,c,d)])
    for pid,front in [(0,False),(len(profiles)-1,True)]:
        vertices.append((0,profiles[pid][1]+(.021 if front else -.004),zcenter));uvs.append((.5,.5))
        ic=len(vertices)-1
        for i in range(ringlen):
            a=pid*ringlen+i;b=pid*ringlen+(i+1)%ringlen
            faces.append((ic,a,b) if front else (ic,b,a))
    mesh=trimesh.Trimesh(vertices=np.array(vertices),faces=np.array(faces),process=False)
    return add(nm,mesh,mat,uvs)


def rounded_box(name,center,size,rad,mat,subdiv=3,rotation=None):
    """Beveled cuboid with soft vertices and no dependency on a CAD/Blender runtime."""
    base=trimesh.creation.box(extents=size)
    # Triangles subdivided to give rounded, smooth transitions at the edges.
    for _ in range(subdiv):
        base=base.subdivide()
    vertex=base.vertices.copy()
    inner=np.maximum(np.asarray(size)/2.0-rad, 1e-5)
    clamped=np.clip(vertex,-inner,inner)
    delta=vertex-clamped
    lengths=np.linalg.norm(delta,axis=1)
    vertex = clamped+ np.divide(delta,np.maximum(lengths[:,None],1e-9))*rad
    if rotation is not None:
        R=trimesh.transformations.rotation_matrix(rotation[0],rotation[1])
        vertex=trimesh.transform_points(vertex,R)
    vertex+=np.asarray(center)
    base.vertices=vertex
    return add(name,base,mat)


def arm_open_frame(side):
    """Real open hole through white molded side supports; no painted faux hole."""
    # Coordinates are (z,y). Outer white hollow rounded-trapezoid arm support.
    outer=outline(.365,.315,.069,n=15)
    inner=outline(.183,.135,.055,n=15)
    cx=.233;cy=.512
    # Both curves share angular topology, so the surface rings bridge predictably.
    outer[:,0]+=cx; outer[:,1]+=cy
    inner[:,0]+=cx+.018;inner[:,1]+=cy-.014
    x=side*.289
    thick=.068
    vertices=[];uvs=[]
    for xs in [x-thick/2, x+thick/2]:
        for loop in [outer,inner]:
            for z,y in loop:
                vertices.append((xs,y,z));uvs.append((z*1.4,y*1.2))
    n=len(outer); faces=[]
    for i in range(n):
        j=(i+1)%n
        # planar annulus (front & back surfaces)
        faces.extend([(i,j,n+j),(i,n+j,n+i)])
        off=2*n
        faces.extend([(off+n+i,off+n+j,off+j),(off+n+i,off+j,off+i)])
        # outer side walls
        faces.extend([(i,off+i,off+j),(i,off+j,j)])
        # inner side walls
        faces.extend([(n+j,off+n+j,off+n+i),(n+j,off+n+i,n+i)])
    geom=trimesh.Trimesh(vertices=np.asarray(vertices),faces=np.asarray(faces),process=False)
    add(('Left' if side<0 else 'Right')+' arm open white frame',geom,'white',uvs)

# 1 | Wide, rounded white rear shell, peeking out as a white border from the front.
back_loft(.535,.785,.876,.125,[
    (.91,-.167),(.985,-.158),(1.,-.139),(1.,-.108),(.997,-.076),(.961,-.056),(.89,-.051)
], 'Molded white curved back shell', 'shell',taper=True)

# 2 | Upholstered main back panel; puffy but streamlined like the reference.
back_loft(.454,.716,.879,.111,[
    (.86,-.063),(.965,-.057),(1.,-.041),(1.,-.015),(.997,.031),(.965,.078),(.83,.097)
], 'Lime upholstered curved seat back', 'lime upholstery',taper=True)

# 3 | White cushion tray followed by rounded cloth cushion.
seat_loft(.501,.638,.075,[(.87,.345),(.99,.347),(1.,.360),(1.,.411),(.965,.431),(.88,.434)],'White seat pan base','shell')
seat_loft(.467,.607,.071,[(.87,.417),(.970,.428),(1.,.446),(1.,.492),(.98,.523),(.87,.536)],'Lime upholstered seat cushion','lime upholstery')

# 4 | Full open-hole arm supports, arm caps with lime-colored pads.
for side in (-1,1):
    p='Left' if side<0 else 'Right'
    arm_open_frame(side)
    rounded_box(p+' pale molded armrest',(.301*side,.693,.086),(.096,.103,.685),.027,'white',subdiv=3)
    rounded_box(p+' lime armrest top',(.301*side,.752,.074),(.077,.021,.585),.010,'lime accent',subdiv=3)
    # discreet joint where the armrest joins the seat shell
    rounded_box(p+' rear armrest attachment',(.302*side,.567,-.247),(.071,.162,.119),.027,'shell',subdiv=3)

# 5 | Under-seat chassis and two floor-contact feet (intentionally simple for web).
rounded_box('White underseat curved skirt',(0,.327,.061),(.466,.103,.554),.046,'shell',subdiv=3)
for side in (-1,1):
    p='Left' if side<0 else 'Right'
    rounded_box(p+' satin support strut',(.165*side,.208,.006),(.056,.262,.069),.015,'steel',subdiv=3)
    rounded_box(p+' foot attachment',(.165*side,.075,.041),(.084,.046,.362),.016,'shadow',subdiv=3)

# 6 | Black rear inset display and pale shell trim, in the original third image.
# Backward = -Z. Add a little tilt around X aligned to the leaning rear shell.
rot=(math.atan(.20),(1,0,0))
rounded_box('Seatback embedded display surround',(0,1.061,shell_back_z(1.061)-.180),(.319,.172,.016),.029,'white',rotation=rot,subdiv=3)
rounded_box('Seatback black display bezel',(0,1.061,shell_back_z(1.061)-.190),(.285,.143,.014),.026,'screen rim',rotation=rot,subdiv=3)
rounded_box('Seatback glossy dark screen',(0,1.061,shell_back_z(1.061)-.199),(.254,.119,.007),.020,'screen',rotation=rot,subdiv=3)
# a white horizontal strip at rear below screen, shell seam.
rounded_box('Seatback lower rear pocket trim',(0,.686,shell_back_z(.686)-.173),(.329,.012,.011),.004,'shadow',rotation=rot,subdiv=2)

# 7 | Subtle horizontal tailoring stitch for backrest, visible only at close distance.
def tube(name, points, radius,mat):
    # Loft narrow circular cross-sections along polyline, with Y constant and X direction.
    pp=np.asarray(points); vertices=[];faces=[];segments=9
    for k,p in enumerate(pp):
        for theta in np.linspace(0,math.tau,segments,endpoint=False):
            vertices.append(p+np.array([0,math.cos(theta),math.sin(theta)])*radius)
    for k in range(len(pp)-1):
        for j in range(segments):
            j2=(j+1)%segments;a=k*segments+j;b=k*segments+j2
            c=(k+1)*segments+j2;d=(k+1)*segments+j
            faces.extend([(a,b,c),(a,c,d)])
    add(name,trimesh.Trimesh(vertices=vertices,faces=faces,process=False),mat)

points=[]
for x in np.linspace(-.190,.190,35):
    y=.834+.004*(x/.19)**2
    z=shell_back_z(y)+.088+ .0015*(1-(x/.19)**2)
    points.append((x,y,z))
tube('Green upholstery understated horizontal seam',points,.0016,'green stitch')

# Export both a compact browser-native GLB and interoperable mesh assets.
blob=scene.export(file_type='glb')
(HERE/'lime_airline_seat.glb').write_bytes(blob)
# trimesh scene OBJ with material definitions from properties; OBJ is useful for DCC import.
obj_export=trimesh.exchange.obj.export_obj(scene,include_normals=True, include_color=False,return_texture=True)
if isinstance(obj_export,tuple):
    objstr, textures=obj_export
    (HERE/'lime_airline_seat.obj').write_text(objstr,encoding='utf-8')
    for filename,data in textures.items():
        (HERE/filename).write_bytes(data)
else:
    (HERE/'lime_airline_seat.obj').write_text(obj_export,encoding='utf-8')

print(f'Built {len(objects)} individually named component meshes')
print(f'GLB bytes: {len(blob):,}; triangles: {sum(len(o.faces) for _,o,_ in objects):,}')
print('Bounds:',scene.bounds)
print('Files:', [p.name for p in HERE.iterdir()])

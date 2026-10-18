"""Build a modular green-and-white airplane cabin glTF/GLB from the seat model.
Run: python build_cabin.py
Requirement: pip install trimesh numpy pillow
Axes: X lateral (A = left), Y vertical, +Z forward (passenger-facing).
Concept visualization dimensions, not certified aircraft measurements.
"""
from pathlib import Path
import json, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import trimesh
from trimesh.visual.material import PBRMaterial
from trimesh.visual.texture import TextureVisuals

P=Path(__file__).resolve().parent
seatpath=P/'lime_airline_seat.glb'
seat_scene=trimesh.load(seatpath,force='scene')
S=trimesh.Scene()

def mat(name,c,rough=.85,met=0.0,glow=None,tex=None):
    return PBRMaterial(name=name,baseColorFactor=np.array(c,dtype=np.uint8),roughnessFactor=rough,metallicFactor=met,doubleSided=True,baseColorTexture=tex,emissiveFactor=np.array(glow,dtype=float) if glow else None)
M={
 'wall':mat('Pearl white molded cabin wall',(226,235,225,255),.86),
 'ceiling':mat('Warm white curved ceiling',(241,246,236,255),.91),
 'floor':mat('Warm pale aisle floor',(227,235,222,255),.98),
 'carpet':mat('Dark spring green seat floor',(96,149,67,255),.98),
 'lighttrim':mat('Molded pale ceiling trim',(214,224,207,255)),
 'bin':mat('Overhead baggage storage shell',(233,240,229,255),.79),
 'bin-seam':mat('Overhead bin joining details',(191,208,189,255)),
 'handle':mat('Overhead bin green handles',(100,189,49,255),.68),
 'light':mat('Pale green ambient LED',(218,255,169,255),.6,glow=(.45,.76,.20)),
 'greenwall':mat('Lime green forward and rear bulkheads',(72,155,29,255),.94),
 'door':mat('Warm pearl central cabin door',(225,236,218,255),.9),
 'window-frame':mat('Glossy white window bezels',(250,252,245,255),.58),
 'window-inner':mat('Soft white window recess',(199,223,219,255),.77),
 'met':mat('Desaturated foot rail metallic trim',(165,179,160,255),.48,.35),
}
# Procedural cloud/sky scene for windows; self-contained in the GLB.
w,h=256,384
ar=np.zeros((h,w,3),dtype=np.uint8)
for y in range(h):
 t=y/(h-1)
 col=np.array([193,224,239])*(1-t)+np.array([247,253,249])*t
 ar[y,:,:]=col.astype(np.uint8)
win=Image.fromarray(ar,'RGB').convert('RGBA')
cloud=Image.new('RGBA',(w,h),(0,0,0,0));D=ImageDraw.Draw(cloud)
for i in range(10):
 x=int(35+(i*37)%240); yy=int(265+(i*23)%75)
 D.ellipse((x-66,yy-25,x+52,yy+17),fill=(255,255,255,140))
cloud=cloud.filter(ImageFilter.GaussianBlur(13));win=Image.alpha_composite(win,cloud).convert('RGB')
win.save(P/'window_sky_texture.png')
M['sky']=mat('Light blue sky outside windows',(255,255,255,255),.99,tex=win,glow=(.08,.11,.12))

geom_count=0

def add(n, mesh, material, transform=None, uv=None, key=None):
 global geom_count
 mesh=mesh.copy()
 if uv is None:
  v=mesh.vertices
  uv=np.column_stack([v[:,0]*.35+v[:,2]*.07+.5,v[:,1]*.45+.5])
 mesh.visual=TextureVisuals(uv=uv,material=M[material])
 S.add_geometry(mesh,geom_name=key or ('cabin_'+str(geom_count)),node_name=n,transform=transform)
 geom_count+=1

def box(n, pos, dims, m, bevel=0):
 mesh=trimesh.creation.box(extents=dims)
 if bevel:
  mesh=mesh.subdivide()
  v=mesh.vertices.copy()
  inner=np.maximum(np.asarray(dims)/2.-bevel,.001)
  near=np.clip(v,-inner,inner); delta=v-near
  v=near+delta/np.maximum(np.linalg.norm(delta,axis=1)[:,None],1e-8)*bevel
  mesh.vertices=v
 mesh.apply_translation(pos)
 add(n,mesh,m)

def band(n,profile,zstart,zend,m):
 """Extrude across Z an XY polyline as a double-sided wall/ceiling sheet."""
 v=[];faces=[]
 for z in (zstart,zend):
  for x,y in profile: v.append((x,y,z))
 N=len(profile)
 for i in range(N-1):
  a=i;b=i+1;c=N+i;d=N+i+1
  faces.extend([(a,c,b),(b,c,d)])
 add(n,trimesh.Trimesh(vertices=v,faces=faces,process=False),m)

def cuboid_frame(n, w,h,r,center,xplane,material,thick=.044,narc=10):
 """Flat frame annulus in YZ plane, around an inset capsule window."""
 def rr(w,h,r,n=10):
  arr=[]
  for cy,cz,start in [(h/2-r,w/2-r,0),(h/2-r,-w/2+r,90),(-h/2+r,-w/2+r,180),(-h/2+r,w/2-r,270)]:
   for a in np.linspace(math.radians(start),math.radians(start+90),n,endpoint=False):
    # coordinates y,z; first component for y
    arr.append((cy+r*math.cos(a),cz+r*math.sin(a)))
  return np.array(arr)
 # simple framing with two loop rings and both front/back surfaces
 a=rr(h,w,r,narc);b=rr(h-.09,w-.09,max(.05,r-.045),narc); N=len(a)
 v=[]
 for off in (-thick/2,thick/2):
  for ring in (a,b):
   for yy,zz in ring:v.append((xplane+off,center[0]+yy,center[1]+zz))
 faces=[]
 for i in range(N):
  j=(i+1)%N
  for start in (0,2*N):
   faces+= [(start+i,start+j,start+N+j),(start+i,start+N+j,start+N+i)]
  faces +=[(i,2*N+i,2*N+j),(i,2*N+j,j)]
  faces +=[(N+i,N+j,3*N+j),(N+i,3*N+j,3*N+i)]
 add(n,trimesh.Trimesh(vertices=v,faces=faces,process=False),material)

def elliptical_window(side,num,z):
 # Rounded vertical window, between each seat bay. Opaque luminous image is intentionally a separate mesh.
 x=side*2.03; y=1.31; zz=z
 # use polygon based on spherical ellipse shape with variable radius, slight protrusion toward inside
 V=[];F=[];UV=[]
 N=40
 V.append((x-side*.008,y,zz)); UV.append((.5,.5))
 for i in range(N):
  a=math.pi*2*i/N
  Y=y+.325*math.cos(a);Z=zz+.228*math.sin(a)
  V.append((x-side*.013,Y,Z));UV.append((.5+.50*math.sin(a),.5+.50*math.cos(a)))
 for i in range(N):F.append((0,1+i,1+(i+1)%N))
 add(f'Window glass_{side}_{num}',trimesh.Trimesh(vertices=V,faces=F,process=False),'sky',uv=UV)
 # ellipse ring in x= side*2.005. Topologically radial annulus
 V=[];F=[]
 for scale,xdelta in [(1.12,0.0),(.99,-side*.006)]:
  for i in range(N):
   a=2*math.pi*i/N
   V.append((side*1.994+xdelta,y+.325*scale*math.cos(a),zz+.228*scale*math.sin(a)))
 for i in range(N):
  j=(i+1)%N; F +=[(i,j,N+j),(i,N+j,N+i)]
 add(f'Window white recessed frame_{side}_{num}',trimesh.Trimesh(vertices=V,faces=F,process=False),'window-frame')
 # gray accent thin secondary ring
 V=[];F=[]
 for scale in (1.145,1.125):
  for i in range(N):
   a=2*math.pi*i/N
   V.append((side*1.996,y+.325*scale*math.cos(a),zz+.228*scale*math.sin(a)))
 for i in range(N):
  j=(i+1)%N;F.extend([(i,j,N+j),(i,N+j,N+i)])
 add(f'Window shadow surround_{side}_{num}',trimesh.Trimesh(vertices=V,faces=F,process=False),'window-inner')

# Overall dimensions 4.2m wide, 15.8m long, 2.8m maximum interior.
L=15.75;z0=-L/2;z1=L/2
box('Floor | central aisle', (0,.007,0),(.775,.035,L),'floor')
for side in (-1,1):
 box(f'Floor | green seat-bank carpet {side}', (side*1.26,.006,0),(1.48,.04,L),'carpet')
 box(f'Floor | narrow runner border {side}', (side*.402,.008,0),(.018,.02,L),'lighttrim')
 # Walls & roof separated into hideable categories in the web viewer.
 band(f'Wall | lower panel {side}',[(side*2.045,.10),(side*2.05,.47),(side*2.075,.84),(side*2.07,1.65)],z0,z1,'wall')
 band(f'Wall | arch {side}',[(side*2.07,1.65),(side*2.05,1.86),(side*1.94,2.04),(side*1.78,2.26),(side*1.55,2.42)],z0,z1,'wall')
 box(f'Wall | slim white floor skirting {side}',(side*1.981,.13,0),(.09,.2,L),'ceiling')
 # Curved wing ceiling from sides to center. This whole set is hideable for overhead view.
 band(f'Roof | rounded upper dome {side}',[(side*1.55,2.42),(side*1.31,2.55),(side*1.00,2.67),(side*.62,2.76),(0,2.79)],z0,z1,'ceiling')
 # Continuous overhead bins. segmented shells preserve readable cabin scale.
 for j in range(15):
  z=z0+.53+j*1.02
  if z>z1-.35:break
  box(f'Bin | luggage compartment {side} {j}',(side*1.52,2.36,z),(.59,.27,.99),'bin',.045)
  box(f'Bin | bright green latch {side} {j}',(side*1.389,2.20,z),(.20,.065,.185),'handle',.024)
  box(f'Bin | latch recess {side} {j}',(side*1.363,2.167,z),(.09,.02,.11),'bin-seam',.009)
 # Luminous strip on each side under bins
 box(f'Light | long green ambient strip {side}',(side*1.181,2.585,0),(.045,.026,L-.25),'light',.006)
 box(f'Light | white underbin line {side}',(side*1.823,1.999,0),(.025,.035,L-.21),'light',.007)
 # Ceiling ceiling line detail
 box(f'Roof | white central diffuser border {side}',(side*.070,2.783,0),(.018,.014,L-.18),'lighttrim')
 # Green seams between bin panels; wall details between windows.
 for i in range(14):
  z=z0+.92+i*1.04
  box(f'Bin | division seam {side} {i}',(side*1.48,2.34,z),(.61,.275,.012),'bin-seam',0)
 # 12 window pairs aligned with 12 seat rows
 for i in range(12):
  rowz=5.72-i*1.04
  elliptical_window(side,i,rowz+.22)

# Front/rear bulkheads with center door and green bulkhead surfaces.
for z,s in [(z1-.058,'front'),(z0+.058,'rear')]:
 box(f'Bulkhead | green wall {s}',(0,1.37,z),(4.12,2.69,.095),'greenwall')
 box(f'Bulkhead | door inset {s}',(0,1.22,z +(-.055 if s=='front' else .055)),(.81,1.92,.029),'door',.05)
 box(f'Bulkhead | door soft trim {s}',(.361,1.18,z+(-.074 if s=='front' else .074)),(.023,1.75,.015),'lighttrim')
 box(f'Bulkhead | door pull {s}',(.27,1.09,z+(-.082 if s=='front' else .082)),(.037,.12,.017),'handle',.013)

# Reuse the SAME chair mesh for 48 seats. Exported glTF nodes carry seat ids.
COLS={'A':-1.42,'B':-.66,'C':.66,'D':1.42}
OCC={'10B','11C','12D','13A','15B','16D','17C','18A','19B','20C'}
seats=[]
for ri in range(12):
 row=ri+10; zz=5.72-ri*1.04
 for c,x in COLS.items():
  sid=f'{row}{c}'; avail=sid not in OCC
  seats.append({'id':sid,'row':row,'column':c,'x':x,'y':0,'z':zz,'type':'window' if c in 'AD' else 'aisle','available':avail,'legroom':'Standard','price':18 if c in 'AD' else 12})
  trans=trimesh.transformations.translation_matrix([x,0,zz])
  for node in seat_scene.graph.nodes_geometry:
   local, gname=seat_scene.graph[node]
   # trimesh Scene.graph comes from GLB; geometries shared between instances in export
   name=f'Seat_{sid}__{node.replace(" ","_")}'
   S.add_geometry(seat_scene.geometry[gname],geom_name='CHAIR_'+gname,node_name=name,transform=trans@local)

out=P/'lime_cabin_full.glb'
out.write_bytes(S.export(file_type='glb'))
(P/'seat_positions.json').write_text(json.dumps({'units':'meters','coordinateSystem':'Y_UP +Z_FRONT','rows':12,'seatsPerRow':4,'seatCount':48,'cabinLength':L,'cabinWidth':4.15,'seatPitchMeters':1.04,'seats':seats},indent=2))
print('GLB',round(out.stat().st_size/1e6,3),'MB, geometries',len(S.geometry),'nodes',len(S.graph.nodes_geometry),'seats',len(seats))
print('Bounds',np.round(S.bounds,2), 'triangles unique total',sum(len(g.faces) for g in S.geometry.values()))

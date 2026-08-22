from __future__ import annotations
import json, math, hashlib, zlib, struct, sys
from pathlib import Path

RENDERER_VERSION="v420-stdlib-zbuffer-1"
TRUTH_ASCII="SCHEMATIC - NOT FOR CONSTRUCTION - UNSEALED - PROFESSIONAL / AHJ REVIEW REQUIRED."

def canon(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False)

def digest(x):
    return hashlib.sha256(canon(x).encode("utf-8")).hexdigest()

def vsub(a,b): return [a[i]-b[i] for i in range(3)]
def dot(a,b): return sum(a[i]*b[i] for i in range(3))
def cross(a,b): return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def norm(a): return math.sqrt(dot(a,a))
def unit(a):
    n=norm(a)
    if n<=1e-15: raise ValueError("zero vector")
    return [x/n for x in a]

def camera_basis(cam):
    fwd=unit(vsub(cam["target"],cam["eye"]))
    right=unit(cross(fwd,cam["up"]))
    up=cross(right,fwd)
    return right,up,fwd

def project(v,cam,basis):
    right,up,fwd=basis
    rel=vsub(v,cam["eye"])
    x=dot(rel,right); y=dot(rel,up); z=dot(rel,fwd)
    if z<=0.05: return None
    focal=0.5*cam["height"]/math.tan(math.radians(cam["fov_deg"])/2)
    return [cam["width"]/2+x*focal/z,cam["height"]/2-y*focal/z,z]

def edge(ax,ay,bx,by,px,py):
    return (px-ax)*(by-ay)-(py-ay)*(bx-ax)

def obj_color(name):
    h=hashlib.sha256(name.encode()).digest()
    return [90+(h[0]%91),90+(h[1]%91),90+(h[2]%91)]

def shade_color(base,normal):
    light=unit([0.5,-0.7,1.0])
    intensity=0.28+0.72*abs(dot(unit(normal),light))
    return [max(0,min(255,int(c*intensity))) for c in base]

def raster_triangle(p0,p1,p2,color,pixels,zbuf,w,h):
    x0,y0,z0=p0; x1,y1,z1=p1; x2,y2,z2=p2
    den=edge(x0,y0,x1,y1,x2,y2)
    if abs(den)<1e-12: return 0
    xmin=max(0,int(math.floor(min(x0,x1,x2))))
    xmax=min(w-1,int(math.ceil(max(x0,x1,x2))))
    ymin=max(0,int(math.floor(min(y0,y1,y2))))
    ymax=min(h-1,int(math.ceil(max(y0,y1,y2))))
    hits=0
    sign=1.0 if den>0 else -1.0
    den*=sign
    for y in range(ymin,ymax+1):
        py=y+0.5
        for x in range(xmin,xmax+1):
            px=x+0.5
            w0=edge(x1,y1,x2,y2,px,py)*sign/den
            w1=edge(x2,y2,x0,y0,px,py)*sign/den
            w2=1.0-w0-w1
            if w0>=-1e-10 and w1>=-1e-10 and w2>=-1e-10:
                invz=w0/z0+w1/z1+w2/z2
                if invz<=0: continue
                z=1.0/invz
                idx=y*w+x
                if z<zbuf[idx]:
                    zbuf[idx]=z
                    off=idx*3
                    pixels[off:off+3]=bytes(color)
                    hits+=1
    return hits

def png_chunk(kind,data):
    kind=kind.encode("ascii")
    return struct.pack(">I",len(data))+kind+data+struct.pack(">I",zlib.crc32(kind+data)&0xffffffff)

def write_png(path,w,h,pixels,text):
    raw=bytearray(); stride=w*3
    for y in range(h):
        raw.append(0); raw.extend(pixels[y*stride:(y+1)*stride])
    out=bytearray(b"\x89PNG\r\n\x1a\n")
    out.extend(png_chunk("IHDR",struct.pack(">IIBBBBB",w,h,8,2,0,0,0)))
    for k,v in text.items():
        out.extend(png_chunk("tEXt",(str(k)+"\x00"+str(v)).encode("latin-1","replace")))
    out.extend(png_chunk("IDAT",zlib.compress(bytes(raw),9)))
    out.extend(png_chunk("IEND",b""))
    Path(path).write_bytes(out)

def all_triangles(model):
    tris=[]
    for obj in model["objects"]:
        verts=obj["vertices"]
        for face in obj["faces"]:
            if len(face)<3: continue
            for i in range(1,len(face)-1):
                tris.append((obj["id"],verts[face[0]],verts[face[i]],verts[face[i+1]]))
    return tris

def render(model,cam,path):
    w=int(cam["width"]); h=int(cam["height"])
    pixels=bytearray([246,247,249])*(w*h)
    zbuf=[float("inf")]*(w*h)
    basis=camera_basis(cam)
    tri_count=0; pixel_hits=0
    for obj_id,a,b,c in all_triangles(model):
        pa=project(a,cam,basis); pb=project(b,cam,basis); pc=project(c,cam,basis)
        if pa is None or pb is None or pc is None: continue
        normal=cross(vsub(b,a),vsub(c,a))
        if norm(normal)<1e-12: continue
        color=shade_color(obj_color(obj_id),normal)
        pixel_hits+=raster_triangle(pa,pb,pc,color,pixels,zbuf,w,h)
        tri_count+=1
    model_digest=digest(model); camera_digest=digest(cam)
    write_png(path,w,h,pixels,{"ModelDigest":model_digest,"CameraDigest":camera_digest,"Renderer":RENDERER_VERSION,"TruthClassification":TRUTH_ASCII})
    return {"name":cam["name"],"width":w,"height":h,"camera":cam,"camera_digest":camera_digest,"triangle_count":tri_count,"pixel_writes":pixel_hits}

def main(model_path,out_dir):
    model=json.loads(Path(model_path).read_text())
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    model_digest=digest(model); views=[]
    for cam in model["cameras"]:
        path=out/f"render_{cam['name']}.png"
        info=render(model,cam,path); info["file"]=path.name; info["sha256"]=hashlib.sha256(path.read_bytes()).hexdigest(); views.append(info)
    manifest={"schema":"AUTOHOUSE_GEOMETRY_FAITHFUL_RENDER_RECEIPT_V420","renderer_version":RENDERER_VERSION,"model_revision":model["revision"],"model_digest":model_digest,"object_count":len(model["objects"]),"vertex_count":sum(len(o["vertices"]) for o in model["objects"]),"face_count":sum(len(o["faces"]) for o in model["objects"]),"views":views,"geometry_source":"canonical vertices/faces only; renderer performs no geometry mutation","truth_classification":model["truth_classification"]}
    manifest["manifest_digest"]=digest(manifest)
    (out/"render_manifest.json").write_text(json.dumps(manifest,indent=2))
    print(json.dumps(manifest,sort_keys=True))

if __name__=="__main__":
    main(sys.argv[1],sys.argv[2])

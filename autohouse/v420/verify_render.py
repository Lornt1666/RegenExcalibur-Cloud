import json,hashlib,struct,sys
from pathlib import Path

def canon(x): return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def digest(x): return hashlib.sha256(canon(x).encode("utf-8")).hexdigest()

def png_text(path):
    b=Path(path).read_bytes()
    if not b.startswith(b"\x89PNG\r\n\x1a\n"): raise ValueError("not PNG")
    i=8; out={}
    while i<len(b):
        n=struct.unpack(">I",b[i:i+4])[0]; typ=b[i+4:i+8]; data=b[i+8:i+8+n]; i+=12+n
        if typ==b"tEXt":
            k,v=data.split(b"\x00",1); out[k.decode("latin-1")]=v.decode("latin-1")
        if typ==b"IEND": break
    return out

model=json.loads(Path(sys.argv[1]).read_text())
out=Path(sys.argv[2])
m=json.loads((out/"render_manifest.json").read_text())
assert m["model_digest"]==digest(model)
assert m["object_count"]==len(model["objects"])
assert m["vertex_count"]==sum(len(o["vertices"]) for o in model["objects"])
assert len(m["views"])==len(model["cameras"])>=3
for v in m["views"]:
    p=out/v["file"]
    assert p.exists() and p.stat().st_size>1000
    assert hashlib.sha256(p.read_bytes()).hexdigest()==v["sha256"]
    tx=png_text(p)
    assert tx["ModelDigest"]==m["model_digest"]
    assert tx["CameraDigest"]==v["camera_digest"]
    assert tx["TruthClassification"].startswith("SCHEMATIC - NOT FOR CONSTRUCTION")
    assert v["triangle_count"]>0 and v["pixel_writes"]>100
copy=dict(m); expected=copy.pop("manifest_digest")
assert digest(copy)==expected
print(json.dumps({"accepted":True,"model_digest":m["model_digest"],"manifest_digest":m["manifest_digest"],"views":[{"name":v["name"],"sha256":v["sha256"],"pixel_writes":v["pixel_writes"]} for v in m["views"]]},sort_keys=True))

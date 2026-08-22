from __future__ import annotations
import json, math, hashlib, platform, sys


def canon(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"), default=str)


def digest(x):
    return hashlib.sha256(canon(x).encode()).hexdigest()


def load_ops():
    import openseespy.opensees as ops
    return ops, "openseespy"


def env_receipt(mode):
    import importlib.metadata as md
    vers = {}
    for p in ["openseespy", "openseespylinux"]:
        try:
            vers[p] = md.version(p)
        except Exception:
            pass
    payload = {
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "backend_mode": mode,
        "packages": vers,
    }
    payload["environment_digest"] = digest(payload)
    return payload


def configure_static(ops):
    ops.system("UmfPack")
    ops.numberer("RCM")
    ops.constraints("Plain")
    ops.test("NormDispIncr", 1e-10, 100, 0)
    ops.algorithm("Newton")
    ops.integrator("LoadControl", 1.0)
    ops.analysis("Static")


def shell_rect_mesh(ops, a, b, nx, ny, E, nu, t, q, section_tag=1):
    ops.wipe()
    ops.model("basic", "-ndm", 3, "-ndf", 6)
    ops.section("ElasticMembranePlateSection", section_tag, E, nu, t, 0.0)
    node = lambda i, j: j * (nx + 1) + i + 1
    for j in range(ny + 1):
        for i in range(nx + 1):
            ops.node(node(i, j), a * i / nx, b * j / ny, 0.0)
    eid = 1
    element_area = (a / nx) * (b / ny)
    nodal_vertical = {}
    for j in range(ny):
        for i in range(nx):
            ns = [node(i, j), node(i + 1, j), node(i + 1, j + 1), node(i, j + 1)]
            ops.element("ShellMITC4", eid, *ns, section_tag)
            for n in ns:
                nodal_vertical[n] = nodal_vertical.get(n, 0.0) - q * element_area / 4
            eid += 1
    for j in range(ny + 1):
        for i in range(nx + 1):
            n = node(i, j)
            if i == 0 or i == nx or j == 0 or j == ny:
                ops.fix(n, 0, 0, 1, 0, 0, 0)
    ops.fix(node(0, 0), 1, 1, 1, 0, 0, 0)
    ops.fix(node(nx, 0), 0, 1, 1, 0, 0, 0)
    ops.timeSeries("Linear", 1)
    ops.pattern("Plain", 1, 1)
    for n, f in nodal_vertical.items():
        ops.load(n, 0, 0, f, 0, 0, 0)
    return node


def plate_case(ops, a, b, t, E, nu, q, nx, ny):
    node = shell_rect_mesh(ops, a, b, nx, ny, E, nu, t, q)
    configure_static(ops)
    ok = ops.analyze(1)
    center = node(nx // 2, ny // 2)
    return {
        "exit_status": "CONVERGED" if ok == 0 else "FAILED",
        "center_deflection_m": abs(float(ops.nodeDisp(center, 3))),
        "mesh": {"nx": nx, "ny": ny, "elements": nx * ny},
        "element_formulation": "ShellMITC4",
    }


def membrane_patch_case(ops, E=200e9, nu=.3, t=.02, L=2.0, H=1.5, sigma=20e6):
    ops.wipe(); ops.model("basic", "-ndm", 3, "-ndf", 6)
    ops.section("ElasticMembranePlateSection", 1, E, nu, t, 0.0)
    pts = {1: (0, 0), 2: (L, 0), 3: (L, H), 4: (0, H)}
    for n, (x, y) in pts.items(): ops.node(n, x, y, 0)
    ops.element("ShellMITC4", 1, 1, 2, 3, 4, 1)
    ops.fix(1, 1, 1, 1, 1, 1, 1); ops.fix(4, 1, 0, 1, 1, 1, 1)
    ops.fix(2, 0, 0, 1, 1, 1, 1); ops.fix(3, 0, 0, 1, 1, 1, 1)
    total = sigma * t * H
    ops.timeSeries("Linear", 1); ops.pattern("Plain", 1, 1)
    ops.load(2, total / 2, 0, 0, 0, 0, 0); ops.load(3, total / 2, 0, 0, 0, 0, 0)
    configure_static(ops); ok = ops.analyze(1)
    ux = (ops.nodeDisp(2, 1) + ops.nodeDisp(3, 1)) / 2
    return {"exit_status": "CONVERGED" if ok == 0 else "FAILED", "observed_ex": float(ux / L), "reference_ex": sigma / E, "element_formulation": "ShellMITC4"}


def von_mises_case(ops, a=2.5, h=.55, E=200e9, A=.004, target_v=-.9):
    ops.wipe(); ops.model("basic", "-ndm", 2, "-ndf", 2)
    ops.node(1, -a, 0); ops.node(2, a, 0); ops.node(3, 0, h)
    ops.fix(1, 1, 1); ops.fix(2, 1, 1); ops.fix(3, 1, 0)
    ops.uniaxialMaterial("Elastic", 1, E)
    ops.element("corotTruss", 1, 1, 3, A, 1); ops.element("corotTruss", 2, 2, 3, A, 1)
    ops.timeSeries("Linear", 1); ops.pattern("Plain", 1, 1); ops.load(3, 0, -1.0)
    ops.system("UmfPack"); ops.numberer("RCM"); ops.constraints("Plain")
    ops.test("NormDispIncr", 1e-10, 100); ops.algorithm("Newton")
    ops.integrator("DisplacementControl", 3, 2, -abs(target_v) / 600); ops.analysis("Static")
    curve = []
    for _ in range(600):
        ok = ops.analyze(1)
        if ok != 0: break
        curve.append({"v_m": float(ops.nodeDisp(3, 2)), "P_down_N": float(ops.getLoadFactor(1))})
    if len(curve) < 10: return {"exit_status": "FAILED", "curve": curve}
    peak = max(curve, key=lambda x: x["P_down_N"])
    return {"exit_status": "CONVERGED", "peak": peak, "curve": curve[::20], "element_formulation": "corotTruss"}


def euler_column_case(ops, E=200e9, A=.01, I=8e-6, L=3.0, segments=20, e0_ratio=1e-4):
    ops.wipe(); ops.model("basic", "-ndm", 2, "-ndf", 3)
    for i in range(segments + 1):
        y = L * i / segments
        x = e0_ratio * L * math.sin(math.pi * y / L)
        ops.node(i + 1, x, y)
    ops.fix(1, 1, 1, 0); ops.fix(segments + 1, 1, 0, 0)
    ops.geomTransf("Corotational", 1)
    for i in range(segments): ops.element("elasticBeamColumn", i + 1, i + 1, i + 2, A, E, I, 1)
    ops.timeSeries("Linear", 1); ops.pattern("Plain", 1, 1); ops.load(segments + 1, 0, -1.0, 0)
    ops.system("UmfPack"); ops.numberer("RCM"); ops.constraints("Plain")
    ops.test("NormDispIncr", 1e-9, 100); ops.algorithm("Newton")
    ops.integrator("DisplacementControl", segments + 1, 2, -L * 1e-5); ops.analysis("Static")
    hist = []; mid = segments // 2 + 1
    for _ in range(2500):
        ok = ops.analyze(1)
        if ok != 0: break
        hist.append({"P_N": float(ops.getLoadFactor(1)), "mid_x_m": float(ops.nodeDisp(mid, 1)), "top_y_m": float(ops.nodeDisp(segments + 1, 2))})
        if abs(ops.nodeDisp(segments + 1, 2)) > L * .02: break
    if not hist: return {"exit_status": "FAILED", "history": []}
    peak = max(hist, key=lambda x: x["P_N"])
    return {"exit_status": "CONVERGED", "peak_load_N": peak["P_N"], "history": hist[::max(1, len(hist) // 50)], "reference_euler_N": math.pi ** 2 * E * I / L ** 2, "element_formulation": "elasticBeamColumn+Corotational"}


def sphere_mesh(R=5.0, n=6):
    nodes = []; index = {}; quads = []
    faces = [lambda u,v:(1,u,v), lambda u,v:(-1,u,-v), lambda u,v:(u,1,v), lambda u,v:(u,-1,-v), lambda u,v:(u,v,1), lambda u,v:(-u,v,-1)]
    def addp(p):
        m = math.sqrt(sum(x*x for x in p)); p = tuple(R*x/m for x in p); key = tuple(round(x,10) for x in p)
        if key not in index: index[key] = len(nodes)+1; nodes.append(p)
        return index[key]
    vals = [-1 + 2*i/n for i in range(n+1)]
    for face in faces:
        grid = [[addp(face(u,v)) for u in vals] for v in vals]
        for j in range(n):
            for i in range(n):
                q = [grid[j][i], grid[j][i+1], grid[j+1][i+1], grid[j+1][i]]
                p = [nodes[k-1] for k in q]
                a = [p[1][x]-p[0][x] for x in range(3)]; b = [p[2][x]-p[0][x] for x in range(3)]
                normal = (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
                cent = tuple(sum(pp[x] for pp in p)/4 for x in range(3))
                if sum(normal[x]*cent[x] for x in range(3)) < 0: q = [q[0], q[3], q[2], q[1]]
                quads.append(q)
    return nodes, quads


def curved_membrane_case(ops, p=80000, R=5.0, t=.08, E=30e9, nu=.2, n=6):
    ops.wipe(); ops.model("basic", "-ndm", 3, "-ndf", 6)
    ops.section("ElasticMembranePlateSection", 1, E, nu, t, 0.0)
    pts, quads = sphere_mesh(R, n)
    for i, x in enumerate(pts, 1): ops.node(i, *x)
    loads = {i: [0.,0.,0.] for i in range(1, len(pts)+1)}
    def tri_area(a,b,c):
        u=[b[i]-a[i] for i in range(3)]; v=[c[i]-a[i] for i in range(3)]
        cr=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
        return .5*math.sqrt(sum(x*x for x in cr))
    for eid, q in enumerate(quads, 1):
        ops.element("ShellMITC4", eid, *q, 1)
        p0,p1,p2,p3=[pts[k-1] for k in q]; area=tri_area(p0,p1,p2)+tri_area(p0,p2,p3)
        cent=[sum(pp[i] for pp in (p0,p1,p2,p3))/4 for i in range(3)]; cm=math.sqrt(sum(x*x for x in cent)); rad=[x/cm for x in cent]
        for k in q:
            for j in range(3): loads[k][j] += p*area*rad[j]/4
    ops.fix(1,1,1,1,0,0,0); ops.fix(2,0,1,1,0,0,0); ops.fix(3,0,0,1,0,0,0)
    ops.timeSeries("Linear",1); ops.pattern("Plain",1,1)
    for k,f in loads.items(): ops.load(k,*f,0,0,0)
    configure_static(ops); ok=ops.analyze(1)
    radial=[]
    for k,x in enumerate(pts,1):
        if k in {1,2,3}: continue
        d=[ops.nodeDisp(k,i) for i in (1,2,3)]; m=math.sqrt(sum(xx*xx for xx in x)); radial.append(sum(d[j]*x[j]/m for j in range(3)))
    return {"exit_status":"CONVERGED" if ok==0 else "FAILED", "mean_radial_expansion_m":sum(radial)/len(radial), "reference_radial_expansion_m":(1-nu)*(p*R/(2*t))/E*R, "mesh":{"nodes":len(pts),"quads":len(quads)}, "element_formulation":"ShellMITC4"}


def run_all():
    ops, mode = load_ops(); env = env_receipt(mode)
    cases = {
        "MEMBRANE_PATCH": membrane_patch_case(ops),
        "THIN_BENDING": plate_case(ops,4,3,.04,30e9,.2,5000,16,12),
        "THICK_PLATE_SHEAR": plate_case(ops,4,3,.12,30e9,.2,5000,16,12),
        "CURVED_MEMBRANE": curved_membrane_case(ops),
        "GEOMETRIC_NONLINEARITY": von_mises_case(ops),
        "EULER_BUCKLING": euler_column_case(ops),
    }
    body = {"solver":"OpenSeesPy", "benchmark_suite_version":"AutoHouse-v340/v360", "environment":env, "cases":cases}
    body["input_digest"] = digest({"suite":"AutoHouse-v340/v360"}); body["result_digest"] = digest(cases)
    body["exit_status"] = "CONVERGED" if all(x.get("exit_status")=="CONVERGED" for x in cases.values()) else "FAILED"
    return body


if __name__ == "__main__":
    print(json.dumps(run_all(), sort_keys=True))

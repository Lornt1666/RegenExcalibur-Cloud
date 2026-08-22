from __future__ import annotations
import json
import opensees_shell_worker as w


def corrected_shell_rect_mesh(ops, a, b, nx, ny, E, nu, t, q, section_tag=1):
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
    n00 = node(0, 0)
    nx0 = node(nx, 0)
    for j in range(ny + 1):
        for i in range(nx + 1):
            n = node(i, j)
            if not (i == 0 or i == nx or j == 0 or j == ny):
                continue
            if n == n00:
                ops.fix(n, 1, 1, 1, 0, 0, 0)
            elif n == nx0:
                ops.fix(n, 0, 1, 1, 0, 0, 0)
            else:
                ops.fix(n, 0, 0, 1, 0, 0, 0)
    ops.timeSeries("Linear", 1)
    ops.pattern("Plain", 1, 1)
    for n, f in nodal_vertical.items():
        ops.load(n, 0, 0, f, 0, 0, 0)
    return node


w.shell_rect_mesh = corrected_shell_rect_mesh

if __name__ == "__main__":
    print(json.dumps(w.run_all(), sort_keys=True))

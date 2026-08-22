from __future__ import annotations
import json, sys, pathlib

TOLERANCES = {
    "MEMBRANE_PATCH": 0.02,
    "CURVED_MEMBRANE": 0.08,
    "THIN_BENDING": 0.05,
    "THICK_PLATE_SHEAR": 0.05,
    "GEOMETRIC_NONLINEARITY": 0.08,
    "EULER_BUCKLING": 0.08,
}


def rel(reference, observed):
    return abs(observed - reference) / abs(reference) if reference else abs(observed)


def main():
    raw_path = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "raw_receipt.json")
    ref_path = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "references.json")
    raw = json.loads(raw_path.read_text())
    refs = json.loads(ref_path.read_text())
    issues = []
    comparisons = {}

    if raw.get("exit_status") != "CONVERGED":
        issues.append("SUITE_NOT_CONVERGED")
    env = raw.get("environment", {})
    if not env.get("environment_digest"):
        issues.append("ENVIRONMENT_DIGEST_MISSING")
    if env.get("packages", {}).get("openseespy") != "3.8.0.0":
        issues.append("OPENSEESPY_VERSION_MISMATCH")
    if env.get("packages", {}).get("openseespylinux") != "3.8.0.0":
        issues.append("OPENSEESPYLINUX_VERSION_MISMATCH")
    for key in ("input_digest", "result_digest", "benchmark_suite_version"):
        if not raw.get(key):
            issues.append(key.upper() + "_MISSING")

    cases = raw.get("cases", {})
    required = list(TOLERANCES)
    for key in required:
        if key not in cases:
            issues.append("CASE_MISSING:" + key)
        elif cases[key].get("exit_status") != "CONVERGED":
            issues.append("CASE_FAILED:" + key)

    if "MEMBRANE_PATCH" in cases and cases["MEMBRANE_PATCH"].get("observed_ex") is not None:
        comparisons["MEMBRANE_PATCH"] = rel(refs["MEMBRANE_PATCH"], cases["MEMBRANE_PATCH"]["observed_ex"])
    if "CURVED_MEMBRANE" in cases and cases["CURVED_MEMBRANE"].get("mean_radial_expansion_m") is not None:
        comparisons["CURVED_MEMBRANE"] = rel(refs["CURVED_MEMBRANE"], cases["CURVED_MEMBRANE"]["mean_radial_expansion_m"])
    for key in ("THIN_BENDING", "THICK_PLATE_SHEAR"):
        if key in cases and cases[key].get("center_deflection_m") is not None:
            comparisons[key] = rel(refs[key], cases[key]["center_deflection_m"])
    if "GEOMETRIC_NONLINEARITY" in cases and cases["GEOMETRIC_NONLINEARITY"].get("peak"):
        comparisons["GEOMETRIC_NONLINEARITY"] = rel(refs["GEOMETRIC_NONLINEARITY"], cases["GEOMETRIC_NONLINEARITY"]["peak"]["P_down_N"])
    if "EULER_BUCKLING" in cases and cases["EULER_BUCKLING"].get("peak_load_N") is not None:
        comparisons["EULER_BUCKLING"] = rel(refs["EULER_BUCKLING"], cases["EULER_BUCKLING"]["peak_load_N"])

    for key in required:
        if key not in comparisons:
            issues.append("COMPARISON_MISSING:" + key)
        elif comparisons[key] > TOLERANCES[key]:
            issues.append("TOLERANCE_EXCEEDED:" + key)

    out = {
        "accepted": not issues,
        "promotion_state": "CROSS_VALIDATED_REFERENCE" if not issues else "BLOCKED",
        "issues": issues,
        "relative_errors": comparisons,
        "tolerances": TOLERANCES,
        "authority_state": "PROFESSIONAL_REVIEW_REQUIRED",
        "raw_result_digest": raw.get("result_digest"),
        "environment_digest": env.get("environment_digest"),
    }
    pathlib.Path("promotion_receipt.json").write_text(json.dumps(out, indent=2, sort_keys=True))
    print(json.dumps(out, indent=2, sort_keys=True))
    raise SystemExit(0 if out["accepted"] else 1)


if __name__ == "__main__":
    main()

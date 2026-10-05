#!/usr/bin/env python3
"""Compare the structure of a case bundle with one recorded on the original backend.

  python tools/shape_diff.py actual_bundle.json s7_review

Reports (1) keys the front end expects that are missing, (2) type mismatches, (3) extra keys (information only).
A recorded value of null means "optional here", so it is never reported. Dynamic-key maps (jobs, by_origin,
sample_replies, progress.done, collect progress groups) are compared by their values only.
Exit code 0 when nothing is missing or mismatched, 1 otherwise."""
import json, sys, pathlib

REF = pathlib.Path(__file__).resolve().parent.parent / "reference" / "recorded_backend_states.json"
DYNAMIC = ("jobs", "by_origin", "sample_replies", "done", "groups")      # maps whose keys vary: compare only keys that were recorded
OPAQUE = ("progress", "settings_json", "thresholds_json", "thresholds", "payload_json", "sample_mix_json", "detail_json", "assumptions_json", "inputs_json", "queries_json")  # free-form: only check it is an object

def kind(x):
    if x is None: return "null"
    if isinstance(x, bool): return "bool"
    if isinstance(x, (int, float)): return "number"
    if isinstance(x, str): return "string"
    if isinstance(x, list): return "array"
    return "object"

def compare(act, exp, path, out):
    ke, ka = kind(exp), kind(act)
    if ke == "null": return
    if ka == "null": out["mismatch"].append(f"{path}: expected {ke}, got null"); return
    if ke != ka: out["mismatch"].append(f"{path}: expected {ke}, got {ka}"); return
    if ke == "object":
        last = path.rsplit(".", 1)[-1].replace("[]", "")
        if last in OPAQUE: return
        if last in DYNAMIC:
            for k, v in act.items():
                if k in exp: compare(v, exp[k], f"{path}.{k}", out)
            return
        for k, v in exp.items():
            if k not in act: out["missing"].append(f"{path}.{k}")
            else: compare(act[k], v, f"{path}.{k}", out)
        for k in act:
            if k not in exp: out["extra"].append(f"{path}.{k}")
    elif ke == "array" and exp:
        # every recorded element shape is a valid shape: check each actual element against the best matching one
        for i, a in enumerate(act):
            best = None
            for e in exp[:30]:
                o = {"missing": [], "mismatch": [], "extra": []}
                compare(a, e, f"{path}[{i}]", o)
                if best is None or len(o["missing"]) + len(o["mismatch"]) < len(best["missing"]) + len(best["mismatch"]): best = o
                if not o["missing"] and not o["mismatch"]: break
            for k in out: out[k].extend(best[k])

def diff(actual, state):
    ref = json.loads(REF.read_text())["states"][state]["bundle"]
    out = {"missing": [], "mismatch": [], "extra": []}
    compare(actual, ref, "bundle", out)
    return out

if __name__ == "__main__":
    if len(sys.argv) != 3: sys.exit(__doc__)
    r = diff(json.load(open(sys.argv[1])), sys.argv[2])
    for k in ("missing", "mismatch"):
        for line in sorted(set(r[k])): print(k.upper(), line)
    for line in sorted(set(r["extra"]))[:20]: print("extra (ok)", line)
    sys.exit(1 if r["missing"] or r["mismatch"] else 0)

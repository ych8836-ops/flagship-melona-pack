import argparse
import importlib.util
import json
import os
import sys


MELONA_NODES = [
    "H3FacePresence",
    "ColorMatchLABChunked",
    "H3DynamicResonanceSuppressor",
    "ApplyLUTToVideoFrames",
    "LUTVideoSave",
]

def load_pack(custom_nodes, folder):
    init_file = os.path.join(custom_nodes, folder, "__init__.py")
    if not os.path.isfile(init_file):
        return None, f"missing folder or __init__.py: {folder}"
    module_name = "melona_verify_" + folder.replace("-", "_").lower()
    spec = importlib.util.spec_from_file_location(
        module_name, init_file, submodule_search_locations=[os.path.dirname(init_file)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        return module, None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def inspect_pack(custom_nodes, folder, required):
    module, error = load_pack(custom_nodes, folder)
    found = sorted(getattr(module, "NODE_CLASS_MAPPINGS", {}).keys()) if module else []
    missing = [name for name in required if name not in found]
    return {
        "loaded": module is not None,
        "required_nodes": required,
        "registered_nodes": found,
        "missing_nodes": missing,
        "error": error,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comfy-root", required=True)
    args = parser.parse_args()
    root = os.path.abspath(args.comfy_root)
    custom_nodes = os.path.join(root, "custom_nodes")
    os.chdir(root)
    sys.path.insert(0, root)

    report = {"comfy_root": root, "packs": {}, "legacy_conflicts": [], "models": {}, "ok": True}
    melona = inspect_pack(custom_nodes, "ComfyUI-Flagship-Melona-Pack", MELONA_NODES)
    report["packs"]["ComfyUI-Flagship-Melona-Pack"] = melona
    if melona["error"] or melona["missing_nodes"]:
        report["ok"] = False

    for folder in (
        "ComfyUI-H3-Workflow-Tools",
        "ComfyUI-H3-Audio-Cleanup",
        "comfyui_lut_video_exporter",
    ):
        if os.path.isdir(os.path.join(custom_nodes, folder)):
            report["legacy_conflicts"].append(folder)
            report["ok"] = False

    detector = os.path.join(root, "models", "ultralytics", "bbox", "face_yolov8m.pt")
    report["models"]["face_yolov8m.pt"] = {
        "exists": os.path.isfile(detector),
        "path": detector,
        "size": os.path.getsize(detector) if os.path.isfile(detector) else 0,
    }
    if not os.path.isfile(detector):
        report["ok"] = False

    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()

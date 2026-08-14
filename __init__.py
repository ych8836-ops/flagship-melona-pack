from .workflow_nodes import NODE_CLASS_MAPPINGS as WORKFLOW_NODE_CLASS_MAPPINGS
from .audio_nodes import NODE_CLASS_MAPPINGS as AUDIO_NODE_CLASS_MAPPINGS
from .lut_nodes import NODE_CLASS_MAPPINGS as LUT_NODE_CLASS_MAPPINGS


NODE_CLASS_MAPPINGS = {}
NODE_CLASS_MAPPINGS.update(WORKFLOW_NODE_CLASS_MAPPINGS)
NODE_CLASS_MAPPINGS.update(AUDIO_NODE_CLASS_MAPPINGS)
NODE_CLASS_MAPPINGS.update(LUT_NODE_CLASS_MAPPINGS)

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3FacePresence": "[Melona] H3 Face Presence — Auto Bypass",
    "ColorMatchLABChunked": "[Melona] Color Match LAB — VRAM Safe",
    "H3DynamicResonanceSuppressor": "[Melona] H3 Dynamic Resonance Suppressor",
    "ApplyLUTToVideoFrames": "[Melona] Apply LUT to Video Frames",
    "LUTVideoSave": "[Melona] LUT Video Save",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_NAME = "LUTVideoSave";
const WIDGET_NAME = "melona_lut_video_preview";

function makeViewUrl(meta, vhs = false) {
    const params = new URLSearchParams({
        filename: meta.filename,
        subfolder: meta.subfolder || "",
        type: meta.type || "output",
        format: meta.format || "video/mp4",
        frame_rate: String(meta.frame_rate || 24),
        timestamp: String(Date.now()),
    });
    return api.apiURL(`${vhs ? "/vhs/viewvideo" : "/view"}?${params}`);
}

function buildPreview(node) {
    if (node.__melonaLutPreview) return node.__melonaLutPreview;

    const root = document.createElement("div");
    root.style.cssText = "position:relative;width:100%;min-height:180px;background:#050505;border-radius:7px;overflow:hidden";

    const video = document.createElement("video");
    video.controls = true;
    video.loop = true;
    video.muted = true;
    video.autoplay = true;
    video.playsInline = true;
    video.preload = "metadata";
    video.style.cssText = "display:none;width:100%;height:100%;min-height:180px;object-fit:contain;background:#000";

    const status = document.createElement("div");
    status.textContent = "Run to preview the saved video.";
    status.style.cssText = "position:absolute;inset:0;display:flex;align-items:center;justify-content:center;padding:12px;color:#b9f6ca;font:12px sans-serif;text-align:center;pointer-events:none";

    const info = document.createElement("div");
    info.style.cssText = "position:absolute;left:7px;top:7px;padding:3px 7px;border-radius:5px;background:#000b;color:#d8ffe2;font:11px sans-serif;pointer-events:none;display:none";

    root.append(video, status, info);
    root.addEventListener("pointerdown", (event) => event.stopPropagation());

    const widget = node.addDOMWidget(WIDGET_NAME, "preview", root, {
        serialize: false,
        hideOnZoom: false,
    });
    widget.computeSize = (width) => [width, Math.max(180, (width - 20) / (node.__melonaLutPreview?.aspect || (16 / 9)))];

    const state = {
        root,
        video,
        status,
        info,
        widget,
        meta: null,
        aspect: 16 / 9,
        triedVhs: false,
    };
    node.__melonaLutPreview = state;

    video.addEventListener("loadedmetadata", () => {
        if (video.videoWidth && video.videoHeight) {
            state.aspect = video.videoWidth / video.videoHeight;
        }
        status.style.display = "none";
        video.style.display = "block";
        const play = video.play();
        if (play?.catch) play.catch(() => {});
        node.setDirtyCanvas?.(true, true);
    });

    video.addEventListener("error", () => {
        if (state.meta && !state.triedVhs) {
            state.triedVhs = true;
            status.textContent = "Preparing a browser-compatible preview…";
            status.style.display = "flex";
            video.src = makeViewUrl(state.meta, true);
            video.load();
            return;
        }
        video.style.display = "none";
        status.textContent = "Preview unavailable for this codec. Use h264_high or install VideoHelperSuite.";
        status.style.display = "flex";
    });

    return state;
}

function showPreview(node, output) {
    const list = output?.lut_video_preview || output?.gifs;
    const meta = Array.isArray(list) ? list[0] : null;
    if (!meta?.filename) return;

    const state = buildPreview(node);
    state.meta = meta;
    state.triedVhs = false;
    const width = Number(meta.width) || 0;
    const height = Number(meta.height) || 0;
    if (width > 0 && height > 0) state.aspect = width / height;

    const details = [];
    if (width && height) details.push(`${width}×${height}`);
    if (meta.frame_rate) details.push(`${Number(meta.frame_rate).toFixed(2).replace(/\.00$/, "")} fps`);
    if (meta.frame_count) details.push(`${meta.frame_count} frames`);
    if (meta.has_audio) details.push("audio");
    info.textContent = details.join(" · ");
    info.style.display = details.length ? "block" : "none";

    status.textContent = "Loading preview…";
    status.style.display = "flex";
    videoReset(state.video, makeViewUrl(meta, false));
}

function videoReset(video, src) {
    video.style.display = "block";
    video.muted = true;
    video.src = src;
    video.load();
}

app.registerExtension({
    name: "FlagshipMelona.LUTVideoPreview",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME) return;

        const onCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = onCreated?.apply(this, arguments);
            buildPreview(this);
            if ((this.size?.[0] || 0) < 360 || (this.size?.[1] || 0) < 320) {
                this.setSize?.([Math.max(this.size?.[0] || 0, 360), Math.max(this.size?.[1] || 0, 320)]);
            }
            return result;
        };

        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (output) {
            const result = onExecuted?.apply(this, arguments);
            try {
                showPreview(this, output || {});
            } catch (error) {
                console.warn("[Flagship Melona] LUT video preview failed", error);
            }
            return result;
        };

        const onRemoved = nodeType.prototype.onRemoved;
        nodeType.prototype.onRemoved = function () {
            const video = this.__melonaLutPreview?.video;
            if (video) {
                video.pause();
                video.removeAttribute("src");
                video.load();
            }
            return onRemoved?.apply(this, arguments);
        };
    },
});


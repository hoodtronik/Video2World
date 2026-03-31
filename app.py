"""
Video2World — Gradio Web UI
Reconstructs 3D Gaussian Splatting worlds from video using non-rigid alignment.

This file lives in the Pinokio launcher root and is executed with CWD = app/
so that all video_to_world modules are importable.
"""

import gradio as gr
import subprocess
import os
import sys
import glob
import time
import re
import signal
import shutil
from pathlib import Path
from datetime import datetime

# Inject ffmpeg into path for Gradio video compatibility
try:
    import imageio_ffmpeg
    ffmpeg_dir = os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())
    os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ["PATH"]
except ImportError:
    pass

# ── Configuration ────────────────────────────────────────────────────────────
OUTPUT_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "outputs")
os.makedirs(OUTPUT_BASE, exist_ok=True)

VIEWER_PROCESS = None

# ── VRAM Guidance ────────────────────────────────────────────────────────────
VRAM_GUIDANCE = """
### 💾 VRAM Requirements

| Setting | Estimated VRAM | Notes |
|---------|---------------|-------|
| Fast mode, 20 frames | ~10-12 GB | Minimum viable |
| Fast mode, 50 frames | ~14-16 GB | Good quality |
| Fast mode, 100 frames | ~20-24 GB | Best quality |
| Extensive mode | ~24 GB+ | Full pipeline |

> **Tip:** Reduce *Max Frames* if you run out of VRAM. The model downloads automatically on first run (~2GB).
"""

# ── Helper Functions ─────────────────────────────────────────────────────────

def get_scene_root_from_video(video_path):
    """Derive scene root path from video file path."""
    return os.path.splitext(os.path.abspath(video_path))[0]


def find_output_videos(scene_root):
    """Find all output videos in a scene root directory."""
    if not scene_root or not os.path.isdir(scene_root):
        return []
    videos = []
    for pattern in ["**/*.mp4"]:
        videos.extend(glob.glob(os.path.join(scene_root, pattern), recursive=True))
    # Exclude the input video / DA3 preview
    return [v for v in videos if "gs_video" in v or "gs_2dgs" in v or "gs_3dgs" in v]


def find_checkpoints(scene_root):
    """Find GS checkpoint directories."""
    if not scene_root or not os.path.isdir(scene_root):
        return []
    checkpoints = []
    for pattern in ["**/gs_2dgs", "**/gs_3dgs"]:
        checkpoints.extend(glob.glob(os.path.join(scene_root, pattern), recursive=True))
    return sorted(checkpoints)


def scan_all_scenes():
    """Scan output directory for all completed scenes."""
    scenes = []
    if not os.path.isdir(OUTPUT_BASE):
        return scenes
    for entry in os.listdir(OUTPUT_BASE):
        scene_path = os.path.join(OUTPUT_BASE, entry)
        if os.path.isdir(scene_path):
            videos = find_output_videos(scene_path)
            checkpoints = find_checkpoints(scene_path)
            if videos or checkpoints:
                scenes.append({
                    "name": entry,
                    "path": scene_path,
                    "videos": videos,
                    "checkpoints": checkpoints,
                })
    return scenes


# ── Reconstruction Pipeline ─────────────────────────────────────────────────

def reconstruct(video_file, mode, renderer, max_frames, max_stride):
    """Run the full Video2World reconstruction pipeline."""
    if video_file is None:
        yield "❌ Please upload a video file first.", None, ""
        return

    # Copy video to outputs directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_name = Path(video_file).stem
    scene_name = f"{video_name}_{timestamp}"
    scene_root = os.path.join(OUTPUT_BASE, scene_name)
    os.makedirs(scene_root, exist_ok=True)

    # Copy input video to scene root
    input_video = os.path.join(scene_root, Path(video_file).name)
    shutil.copy2(video_file, input_video)

    # Build reconstruction command
    cmd = [
        sys.executable, "run_reconstruction.py",
        "--config.input-video", input_video,
        "--config.scene-root", scene_root,
        "--config.mode", mode,
        "--config.preprocess-max-frames", str(int(max_frames)),
        "--config.preprocess-max-stride", str(int(max_stride)),
    ]

    if renderer != "auto":
        cmd.extend(["--config.renderer", renderer])

    cmd_str = " ".join(cmd)
    log = f"🚀 Starting Video2World reconstruction...\n"
    log += f"📁 Scene: {scene_name}\n"
    log += f"⚙️  Mode: {mode} | Renderer: {renderer} | Frames: {int(max_frames)} | Stride: {int(max_stride)}\n"
    log += f"{'═' * 80}\n\n"
    log += f"$ {cmd_str}\n\n"

    yield log, None, ""

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace"
        )

        for line in iter(process.stdout.readline, ''):
            log += line
            # Yield periodically for UI responsiveness
            yield log, None, ""

        process.wait()

        if process.returncode != 0:
            log += f"\n{'═' * 80}\n"
            log += f"❌ Pipeline failed with exit code {process.returncode}\n"
            log += f"\nCommon issues:\n"
            log += f"  • Out of VRAM: try reducing Max Frames\n"
            log += f"  • Missing MSVC Build Tools: required for gsplat/tiny-cuda-nn\n"
            log += f"  • CUDA version mismatch: ensure CUDA 12.x is installed\n"
            yield log, None, ""
            return

    except Exception as e:
        log += f"\n❌ Error running pipeline: {str(e)}\n"
        yield log, None, ""
        return

    # Find output videos
    log += f"\n{'═' * 80}\n"
    output_videos = find_output_videos(scene_root)

    if output_videos:
        latest_video = max(output_videos, key=os.path.getmtime)
        log += f"✅ Reconstruction complete!\n"
        log += f"📹 Output video: {latest_video}\n"
        log += f"📁 Scene directory: {scene_root}\n"

        # Find checkpoints for viewer
        checkpoints = find_checkpoints(scene_root)
        ckpt_info = ""
        if checkpoints:
            ckpt_info = checkpoints[-1]
            log += f"🔮 Checkpoint for 3D viewer: {ckpt_info}\n"

        yield log, latest_video, ckpt_info
    else:
        log += f"✅ Pipeline completed but no output video was found.\n"
        log += f"📁 Check: {scene_root}\n"
        yield log, None, ""


# ── 3D Viewer ────────────────────────────────────────────────────────────────

def launch_viewer(checkpoint_path, port):
    """Launch the interactive Viser 3D viewer."""
    global VIEWER_PROCESS

    if not checkpoint_path or not checkpoint_path.strip():
        return "❌ No checkpoint path provided. Run a reconstruction first, or paste a checkpoint path."

    checkpoint_path = checkpoint_path.strip()
    if not os.path.isdir(checkpoint_path):
        return f"❌ Checkpoint directory not found: {checkpoint_path}"

    # Kill existing viewer process
    if VIEWER_PROCESS is not None and VIEWER_PROCESS.poll() is None:
        try:
            VIEWER_PROCESS.terminate()
            VIEWER_PROCESS.wait(timeout=5)
        except Exception:
            pass

    # Parse checkpoint path to extract root-path and run name
    # Expected: <root>/<run_name>/gs_<renderer>
    ckpt = Path(checkpoint_path)
    run_dir_name = ckpt.parent.name
    root_path = str(ckpt.parent.parent)
    port_num = int(port)

    cmd = [
        sys.executable, "-m", "utils.view_checkpoint",
        "--config.root-path", root_path,
        "--config.run", run_dir_name,
        "--config.checkpoint-dir", checkpoint_path,
        "--config.port", str(port_num),
    ]

    try:
        VIEWER_PROCESS = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        time.sleep(4)

        if VIEWER_PROCESS.poll() is not None:
            output = VIEWER_PROCESS.stdout.read() if VIEWER_PROCESS.stdout else ""
            return f"❌ Viewer process exited immediately.\n\nOutput:\n{output}"

        viewer_url = f"http://localhost:{port_num}"
        return (
            f"✅ Interactive 3D Viewer launched!\n\n"
            f"🌐 Open in your browser: {viewer_url}\n\n"
            f"📁 Viewing checkpoint: {checkpoint_path}\n\n"
            f"Use your mouse to orbit, zoom, and pan the 3D scene."
        )
    except Exception as e:
        return f"❌ Failed to launch viewer: {str(e)}"


def stop_viewer():
    """Stop the interactive viewer."""
    global VIEWER_PROCESS
    if VIEWER_PROCESS is not None and VIEWER_PROCESS.poll() is None:
        try:
            VIEWER_PROCESS.terminate()
            VIEWER_PROCESS.wait(timeout=5)
        except Exception:
            pass
        VIEWER_PROCESS = None
        return "⏹️ Viewer stopped."
    return "ℹ️ No viewer is currently running."


def refresh_scenes():
    """Refresh the list of reconstructed scenes."""
    scenes = scan_all_scenes()
    if not scenes:
        return "No completed reconstructions found yet.", gr.update(choices=[], value=None)

    choices = []
    details = "## 🗂️ Completed Reconstructions\n\n"
    for s in scenes:
        label = s["name"]
        choices.append(label)
        details += f"### 📁 {label}\n"
        details += f"- **Path**: `{s['path']}`\n"
        details += f"- **Videos**: {len(s['videos'])} output(s)\n"
        details += f"- **Checkpoints**: {len(s['checkpoints'])} found\n"
        for ckpt in s['checkpoints']:
            details += f"  - `{os.path.basename(ckpt)}`\n"
        details += "\n"

    return details, gr.update(choices=choices, value=choices[0] if choices else None)


def load_scene_video(scene_name):
    """Load the latest output video for a scene."""
    if not scene_name:
        return None, ""
    scene_path = os.path.join(OUTPUT_BASE, scene_name)
    videos = find_output_videos(scene_path)
    checkpoints = find_checkpoints(scene_path)

    if videos:
        latest = max(videos, key=os.path.getmtime)
        ckpt = checkpoints[-1] if checkpoints else ""
        return latest, ckpt
    return None, checkpoints[-1] if checkpoints else ""


# ── Export ────────────────────────────────────────────────────────────────────

def export_ply(checkpoint_path):
    """Export a checkpoint to PLY format."""
    if not checkpoint_path or not checkpoint_path.strip():
        return "❌ No checkpoint path provided."

    checkpoint_path = checkpoint_path.strip()
    if not os.path.isdir(checkpoint_path):
        return f"❌ Checkpoint not found: {checkpoint_path}"

    ckpt = Path(checkpoint_path)
    run_dir_name = ckpt.parent.name
    root_path = str(ckpt.parent.parent)
    out_ply = os.path.join(checkpoint_path, "splats_exported.ply")

    cmd = [
        sys.executable, "-m", "utils.export_checkpoint_to_ply",
        "--config.root-path", root_path,
        "--config.run", run_dir_name,
        "--config.checkpoint-dir", checkpoint_path,
        "--config.out-ply", out_ply,
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace"
        )
        if result.returncode == 0:
            return f"✅ PLY exported successfully!\n\n📄 File: {out_ply}\n\nYou can open this file in MeshLab, Blender, or other 3D viewers."
        else:
            return f"❌ Export failed:\n{result.stderr or result.stdout}"
    except Exception as e:
        return f"❌ Export error: {str(e)}"


# ── Custom CSS ───────────────────────────────────────────────────────────────

custom_css = """
.main-title {
    text-align: center;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 2.5em;
    font-weight: 800;
    margin-bottom: 0;
    letter-spacing: -1px;
}
.subtitle {
    text-align: center;
    color: #888;
    font-size: 1.1em;
    margin-top: 0;
}
.status-box textarea {
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace !important;
    font-size: 12px !important;
    line-height: 1.4 !important;
}
footer { display: none !important; }
"""


# ── Build Gradio UI ──────────────────────────────────────────────────────────

with gr.Blocks(
    title="Video2World",
) as demo:
    gr.HTML("<h1 class='main-title'>🌍 Video2World</h1>")
    gr.HTML("<p class='subtitle'>Reconstruct 3D Gaussian Splatting Worlds from Video</p>")

    with gr.Tabs():
        # ── Tab 1: Reconstruct ───────────────────────────────────────────
        with gr.Tab("🎬 Reconstruct", id="reconstruct"):
            with gr.Row():
                with gr.Column(scale=1, min_width=320):
                    video_input = gr.Video(
                        label="Upload Video (MP4)",
                        sources=["upload"],
                    )
                    mode = gr.Radio(
                        ["fast", "extensive"],
                        value="fast",
                        label="Reconstruction Mode",
                        info="Fast: ~30 min, 3DGS only. Extensive: ~2+ hrs, full pipeline."
                    )
                    renderer = gr.Radio(
                        ["auto", "3dgs", "2dgs", "both"],
                        value="auto",
                        label="Renderer",
                        info="Auto = 3DGS for fast mode, both for extensive."
                    )

                    with gr.Accordion("⚙️ Advanced Settings", open=False):
                        max_frames = gr.Slider(
                            minimum=10, maximum=200, value=50, step=5,
                            label="Max Frames",
                            info="More frames = better quality but higher VRAM. Reduce if OOM."
                        )
                        max_stride = gr.Slider(
                            minimum=1, maximum=16, value=8, step=1,
                            label="Max Stride",
                            info="Sampling stride between frames. Lower = denser temporal coverage."
                        )

                    run_btn = gr.Button(
                        "🚀 Start Reconstruction",
                        variant="primary",
                        size="lg",
                    )

                    gr.Markdown(VRAM_GUIDANCE)

                with gr.Column(scale=2):
                    log_output = gr.Textbox(
                        label="Pipeline Output",
                        lines=24,
                        max_lines=50,
                        elem_classes=["status-box"],
                        interactive=False,
                    )
                    result_video = gr.Video(label="🎥 Reconstructed Output")
                    viewer_ckpt_hidden = gr.Textbox(visible=False)

            run_btn.click(
                reconstruct,
                inputs=[video_input, mode, renderer, max_frames, max_stride],
                outputs=[log_output, result_video, viewer_ckpt_hidden],
            )

        # ── Tab 2: 3D Viewer ─────────────────────────────────────────────
        with gr.Tab("🔮 3D Viewer", id="viewer"):
            gr.Markdown(
                "### Interactive 3D Scene Viewer\n"
                "Launch the Viser viewer to explore reconstructed scenes in 3D. "
                "Orbit, zoom, and pan using your mouse."
            )

            with gr.Row():
                with gr.Column(scale=2):
                    checkpoint_input = gr.Textbox(
                        label="Checkpoint Directory",
                        placeholder="e.g., outputs/my_scene/frame_to_model_icp_.../gs_3dgs",
                        info="Paste a checkpoint path from the Reconstruct tab, or browse from the Gallery."
                    )
                with gr.Column(scale=1):
                    viewer_port = gr.Number(
                        value=8080,
                        label="Viewer Port",
                        precision=0,
                        info="Port for the Viser viewer server."
                    )

            with gr.Row():
                launch_btn = gr.Button("🚀 Launch Viewer", variant="primary")
                stop_btn = gr.Button("⏹️ Stop Viewer", variant="stop")
                export_btn = gr.Button("📦 Export to PLY", variant="secondary")

            viewer_status = gr.Textbox(
                label="Viewer Status",
                lines=5,
                interactive=False,
            )

            launch_btn.click(
                launch_viewer,
                inputs=[checkpoint_input, viewer_port],
                outputs=[viewer_status],
            )
            stop_btn.click(stop_viewer, outputs=[viewer_status])
            export_btn.click(
                export_ply,
                inputs=[checkpoint_input],
                outputs=[viewer_status],
            )

        # ── Tab 3: Gallery ───────────────────────────────────────────────
        with gr.Tab("🗂️ Gallery", id="gallery"):
            gr.Markdown("### Browse Completed Reconstructions")
            refresh_btn = gr.Button("🔄 Refresh", variant="secondary")

            scene_list = gr.Markdown("Click **Refresh** to scan for completed reconstructions.")
            scene_selector = gr.Dropdown(
                label="Select Scene", choices=[], interactive=True
            )
            gallery_video = gr.Video(label="Output Video")
            gallery_ckpt = gr.Textbox(label="Checkpoint Path (copy to 3D Viewer tab)")

            refresh_btn.click(
                refresh_scenes,
                outputs=[scene_list, scene_selector],
            )
            scene_selector.change(
                load_scene_video,
                inputs=[scene_selector],
                outputs=[gallery_video, gallery_ckpt],
            )

    gr.Markdown(
        "---\n"
        "*Powered by [Video2World](https://github.com/lukasHoel/video_to_world) — "
        "World Reconstruction From Inconsistent Views "
        "([paper](https://arxiv.org/abs/2603.16736))*"
    )


# ── Launch ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("SERVER_PORT", 7860))
    host = os.environ.get("SERVER_NAME", "0.0.0.0")
    demo.queue().launch(
        server_name=host,
        server_port=port,
        show_error=True,
        theme=gr.themes.Soft(
            primary_hue="violet",
            secondary_hue="blue",
            neutral_hue="slate",
        ),
        css=custom_css,
    )


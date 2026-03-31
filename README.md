# Video2World

A Pinokio installer for [video_to_world](https://github.com/lukasHoel/video_to_world) — World Reconstruction From Inconsistent Views.

Reconstructs 3D Gaussian Splatting worlds from video using non-rigid alignment to resolve inherent 3D inconsistencies in generated sequences.

## Requirements

- **NVIDIA GPU** with CUDA support (12.x recommended)
- **Visual Studio Build Tools** with C++ workload (Windows) — required for compiling gsplat and tiny-cuda-nn
- **~20GB+ disk space** for models and dependencies

### VRAM Requirements

| Setting | Estimated VRAM | Notes |
|---------|---------------|-------|
| Fast mode, 20 frames | ~10-12 GB | Minimum viable |
| Fast mode, 50 frames | ~14-16 GB | Good balance of quality/performance |
| Fast mode, 100 frames | ~20-24 GB | Highest quality |
| Extensive mode | ~24 GB+ | Full pipeline with global optimization |

> Reduce the **Max Frames** setting in the UI if you encounter out-of-memory errors.

## Features

- One-click installation via Pinokio
- Gradio Web UI for easy video upload and reconstruction
- Fast and Extensive reconstruction modes
- 2DGS and 3DGS renderer support
- Interactive 3D scene viewer (Viser)
- Export reconstructed scenes to PLY

## Credits

- **[lukasHoel](https://github.com/lukasHoel)** — Original Video2World research and code
- Paper: [World Reconstruction From Inconsistent Views](https://arxiv.org/abs/2603.16736)

module.exports = {
  requires: {
    bundle: "ai"
  },
  run: [
    // ── Step 0: Platform check ──────────────────────────────────────────
    {
      when: "{{gpu === 'amd' || platform === 'darwin'}}",
      method: "notify",
      params: {
        html: "This app requires an NVIDIA GPU with CUDA support and 12GB+ VRAM. Not compatible with AMD GPUs or macOS."
      },
      next: null
    },
    // ── Step 1: MSVC Build Tools warning (Windows) ──────────────────────
    {
      when: "{{platform === 'win32'}}",
      method: "notify",
      params: {
        html: "<h3>⚠️ Build Tools Required</h3><p>This app compiles CUDA extensions (gsplat, tiny-cuda-nn) from source.<br><br><strong>You MUST have Visual Studio Build Tools with C++ workload installed.</strong><br><br>If you don't have it, install it from:<br><a href='https://visualstudio.microsoft.com/visual-cpp-build-tools/'>https://visualstudio.microsoft.com/visual-cpp-build-tools/</a><br><br>Select <strong>'Desktop development with C++'</strong> during installation.<br><br>Installation may take 20-40 minutes due to compilation steps.</p>"
      }
    },
    // ── Step 2: Clone video_to_world ────────────────────────────────────
    {
      method: "shell.run",
      params: {
        message: [
          "git clone https://github.com/lukasHoel/video_to_world app",
        ]
      }
    },
    // ── Step 3: Install PyTorch with correct CUDA version ───────────────
    {
      method: "script.start",
      params: {
        uri: "torch.js",
        params: {
          venv: "env",
          path: "app",
          xformers: true
        }
      }
    },
    // ── Step 4: Install DA3-compatible numpy/opencv ─────────────────────
    {
      method: "shell.run",
      params: {
        venv: "env",
        path: "app",
        message: [
          "uv pip install \"numpy<2\" \"opencv-python<4.12\"",
        ]
      }
    },
    // ── Step 5: Clone DepthAnything3 + checkout pinned commit ────────────
    {
      method: "shell.run",
      params: {
        path: "app",
        message: [
          "git clone https://github.com/ByteDance-Seed/depth-anything-3 third_party/depth-anything-3",
          "git -C third_party/depth-anything-3 checkout 2c21ea849ceec7b469a3e62ea0c0e270afc3281a",
        ]
      }
    },
    // ── Step 6: Install DepthAnything3 as editable ──────────────────────
    {
      method: "shell.run",
      params: {
        venv: "env",
        path: "app",
        message: [
          "uv pip install -e third_party/depth-anything-3",
        ]
      }
    },
    // ── Step 7: Apply DA3 trajectory-export patch ────────────────────────
    {
      method: "shell.run",
      params: {
        path: "app",
        message: [
          "git -C third_party/depth-anything-3 apply ../../patches/da3-export-trajectory.patch",
        ]
      }
    },
    // ── Step 8: Install gsplat (CUDA compilation) ───────────────────────
    {
      method: "shell.run",
      params: {
        venv: "env",
        path: "app",
        env: {
          CUDA_HOME: "{{envs.CUDA_PATH}}"
        },
        message: [
          "uv pip install --no-build-isolation \"git+https://github.com/nerfstudio-project/gsplat.git@v1.5.3\"",
        ]
      }
    },
    // ── Step 9: Install tiny-cuda-nn (CUDA compilation) ─────────────────
    {
      method: "shell.run",
      params: {
        venv: "env",
        path: "app",
        env: {
          CUDA_HOME: "{{envs.CUDA_PATH}}"
        },
        message: [
          "uv pip install setuptools==81.0.0",
          "uv pip install --no-build-isolation \"git+https://github.com/NVlabs/tiny-cuda-nn/#subdirectory=bindings/torch\"",
        ]
      }
    },
    // ── Step 10: Clone + patch RoMaV2 ───────────────────────────────────
    {
      method: "shell.run",
      params: {
        path: "app",
        message: [
          "git clone https://github.com/Parskatt/RoMaV2 third_party/RoMaV2",
          "git -C third_party/RoMaV2 apply ../../patches/romav2-dataclasses.patch",
        ]
      }
    },
    // ── Step 11: Install RoMaV2 as editable ─────────────────────────────
    {
      method: "shell.run",
      params: {
        venv: "env",
        path: "app",
        message: [
          "uv pip install -e third_party/RoMaV2",
        ]
      }
    },
    // ── Step 12: Install remaining dependencies + Gradio UI ─────────────
    {
      method: "shell.run",
      params: {
        venv: "env",
        path: "app",
        message: [
          "uv pip install open3d scipy tyro tqdm tensorboard",
          "uv pip install lpips viser nerfview romatch",
          "uv pip install gradio",
          "uv pip install cmake ninja",
          "uv pip install hf-xet pip",
          "uv pip install \"numpy<2\" \"opencv-python<4.12\"",
        ]
      }
    },
    // ── Step 13: Done ───────────────────────────────────────────────────
    {
      method: 'input',
      params: {
        title: 'Installation completed',
        description: 'Video2World is ready! Click "Start" to launch the Web UI.\n\nNote: First run will download the DepthAnything3 model (~2GB). Ensure you have 12GB+ VRAM available.'
      }
    }
  ]
}

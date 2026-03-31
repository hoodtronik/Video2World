module.exports = {
  run: [{
    method: "shell.run",
    params: {
      message: "git pull --rebase --autostash"
    }
  }, {
    method: "shell.run",
    params: {
      path: "app",
      message: "git pull --rebase --autostash"
    }
  }, {
    method: "shell.run",
    params: {
      venv: "env",
      path: "app",
      message: [
        "uv pip install \"numpy<2\" \"opencv-python<4.12\"",
        "uv pip install -e third_party/depth-anything-3",
        "uv pip install -e third_party/RoMaV2",
        "uv pip install open3d scipy tyro tqdm tensorboard lpips viser nerfview romatch gradio"
      ]
    }
  }]
}

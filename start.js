module.exports = async (kernel) => {
  let port = await kernel.port()
  return {
    requires: {
      bundle: "ai",
    },
    daemon: true,
    run: [
      {
        method: "shell.run",
        params: {
          venv: "env",
          env: {
            GRADIO_SERVER_NAME: "127.0.0.1",
            GRADIO_SERVER_PORT: port
          },
          path: "app",
          message: [
            "python ../app.py"
          ],
          on: [{
            "event": "/(http:\\/\\/[0-9.:]+)/",   
            "done": true
          }]
        }
      },
      {
        method: "local.set",
        params: {
          url: "{{input.event[1]}}"
        }
      }
    ]
  }
}

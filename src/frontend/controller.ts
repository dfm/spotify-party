export class Controller {
  token(callback: (token: string) => void) {
    fetch("/api/token", { method: "POST" })
      .then(response => response.json())
      .then(data => callback(data.token))
      .catch(error => console.log(`couldn't get token: ${error}`));
  }

  stream(
    device_id: string,
    callback: (room_id: string, stream_url: string) => void
  ) {
    fetch("/api/stream", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ device_id: device_id })
    })
      .then(response => response.json())
      .then(data => callback(data.room_id, data.stream_url))
      .catch(error => console.log(`couldn't get stream: ${error}`));
  }

  pause(callback?: () => void) {
    const req = fetch("/api/pause", { method: "PUT" });
    if (callback) req.then(() => callback());
    req.catch(error => console.log(`couldn't pause: ${error}`));
  }

  close(callback?: () => void) {
    const req = fetch("/api/close", { method: "PUT" });
    if (callback) req.then(() => callback());
    req.catch(error => console.log(`couldn't close: ${error}`));
  }

  change(uri: string, position_ms?: number, callback?: () => void) {
    const req = fetch("/api/change", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ uri: uri, position_ms: position_ms })
    });
    if (callback) req.then(() => callback());
    req.catch(error => console.log(`couldn't change: ${error}`));
  }
}

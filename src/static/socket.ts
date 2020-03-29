export class SocketInterface {
  url: string;
  socket: WebSocket | null;

  constructor(url: string) {
    this.url = url;
    this.socket = null;
  }

  connect() {
    this.disconnect();
    this.socket = new WebSocket(this.url);

    this.socket.onopen = this.onopen;
    this.socket.onclose = this.onclose;
    this.socket.onmessage = this.onmessage;
  }

  disconnect() {
    if (this.connected()) this.socket.close();
    this.socket = null;
  }

  connected() {
    return this.socket ? true : false;
  }

  onopen() {
    console.log("socket opened");
  }

  onclose() {
    console.log("socket closed");
  }

  onmessage(event: MessageEvent) {
    const result = JSON.parse(event.data);
    console.log(`got message ${result}`);
  }
}

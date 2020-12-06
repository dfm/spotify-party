export class SpotifyInterface {
  state?: string;
  token?: string;
  popup?: Window;

  doLogin() {
    this.state = Math.random().toString(36).substring(2, 7);
    console.log(this.state);
    this.popup = window.open(
      `/auth?state=${this.state}`,
      "Login with Spotify",
      "width=800,height=600"
    );
  }

  callback(token: string, state: string) {
    console.log(token, state, this.state);
    if (this.popup) {
      this.popup.close();
      this.popup = null;
    }
    if (state != this.state) {
      console.log(state, this.state);
      console.error("mismatched state");
      return;
    }
    this.token = token;
    this.call("/me", console.log);
  }

  call(path: string, callback?: (data: any) => void) {
    let resp = fetch(`https://api.spotify.com/v1${path}`, {
      headers: {
        Authorization: `Bearer ${this.token}`,
      },
    }).then((response) => {
      return response.json();
    });
    if (callback) resp.then(callback);
  }
}

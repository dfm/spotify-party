"use strict";

window.onSpotifyWebPlaybackSDKReady = () => {
  let connection = null;
  let current_track = null;

  const disconnect = () => {
    connection = null;
  };

  const connect = () => {
    disconnect();
    connection = new WebSocket(SOCKET_URL);

    connection.onopen = () => console.log("open ws");
    connection.onclose = () => {
      disconnect();
      console.log("close ws");
    };
    connection.onmessage = event => {
      const data = JSON.parse(event.data);
      console.log("message:", data);
    };
  };

  const get_spotify_token = async callback => {
    await fetch(TOKEN_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      }
    })
      .then(response => response.json())
      .then(data => {
        callback(data.token);
      })
      .catch(error => console.log(`Something went wrong: ${error}`));
  };

  const player = new Spotify.Player({
    name: "Spotify Party",
    getOAuthToken: get_spotify_token
  });

  player.addListener("ready", ({ device_id }) => {
    // When ready, transfer playback to this device
    const this_device_id = device_id;
    get_spotify_token(token => {
      fetch("https://api.spotify.com/v1/me/player", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ device_ids: [this_device_id] })
      })
        .then(() => connect())
        .catch(console.log);
    });
  });

  // Listen for changes in playback status
  player.addListener("player_state_changed", state => {
    console.log(state);
    if (IS_HOST && connection) {
      if (state.paused) return;
      if (!state.track_window || !state.track_window.current_track) return;
      const track = state.track_window.current_track;
      if (track.uri != current_track) {
        connection.send(
          JSON.stringify({ action: "new_track", uri: track.uri })
        );
        current_track = track.uri;
      }
    }
  });

  // Error handling
  player.addListener("initialization_error", ({ message }) => {
    console.error(message);
  });
  player.addListener("authentication_error", ({ message }) => {
    console.error(message);
  });
  player.addListener("account_error", ({ message }) => {
    console.error(message);
  });
  player.addListener("playback_error", ({ message }) => {
    console.error(message);
  });

  // Not Ready
  player.addListener("not_ready", ({ device_id }) => {
    console.log("Device ID has gone offline", device_id);
  });

  // Connect to the player!
  player.connect();
};

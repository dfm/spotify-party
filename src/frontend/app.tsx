import React from "react";
import ReactDOM from "react-dom";
import io from "socket.io-client";

import { API } from "./api";
import { Status, TrackInfo, Error } from "./types";
import { NowPlaying } from "./components/now-playing";
import {
  ListenerButtons,
  BroadcasterButtons,
} from "./components/player-buttons";
import {
  ListenerStatusText,
  BroadcasterStatusText,
} from "./components/status-text";
import { ErrorMessage } from "./components/error-message";

interface AppProps {
  isListener: boolean;
  userId: string;
  initialRoomName: string;
}

interface AppState {
  status: Status;
  isPaused: boolean;
  roomName: string;
  listeners: number;
  deviceId?: string;
  currentTrack?: TrackInfo;
  streamUrl?: string;
  error?: Error;
}

class App extends React.Component<AppProps, AppState> {
  socket: SocketIOClient.Socket;
  player: Spotify.SpotifyPlayer;
  api: API;

  constructor(props: AppProps) {
    super(props);
    this.state = {
      status: Status.Loading,
      isPaused: true,
      roomName: this.props.initialRoomName,
      listeners: 0,
    };

    this.api = new API();
    this.connectSocket();
    this.connectPlayer();

    // Handle window closes gracefully
    window.addEventListener("beforeunload", (event) => {
      if (this.state.status == Status.Streaming) {
        event.preventDefault();
        event.returnValue = "Are you sure?";
        if (this.props.isListener) {
          return "Are you sure you want to stop listening?";
        }
        return "Are you sure you want to stop broadcasting?";
      }
    });
    window.addEventListener("unload", () => navigator.sendBeacon("/api/stop"));
  }

  connectSocket() {
    this.socket = io.connect();
    this.socket.on("listeners", (data: any) => {
      this.setState({ listeners: data.number });
    });
    this.socket.on("changed", (data: any) => {
      if (
        this.state.status == Status.Ready ||
        this.state.status == Status.Loading
      )
        return;
      this.setState({
        status: Status.Streaming,
        listeners: data.number,
        currentTrack: data.playing,
        isPaused: false,
      });
    });
    this.socket.on("pause", () => this.setState({ isPaused: true }));
    this.socket.on("unpause", () => this.setState({ isPaused: false }));
  }

  connectPlayer() {
    // Initialize the player
    this.player = new Spotify.Player({
      name: "distance.dfm.io",
      volume: 1,
      getOAuthToken: (callback: (token: string) => void) => {
        this.api.call("/api/token", {
          callback: (data) => callback(data.token),
        });
      },
    });

    this.player.addListener("ready", ({ device_id }) => {
      console.log(`Device is ready: ${device_id}`);
      this.setState({ status: Status.Ready, deviceId: device_id });
    });

    this.player.addListener("not_ready", ({ device_id }) => {
      console.log(`Device has gone offline ${device_id}`);
    });

    this.player.addListener("player_state_changed", (state) =>
      this.handleChange(state)
    );

    this.player.addListener("initialization_error", ({ message }) => {
      console.error(`initialization_error: ${message}`);
      this.setState({
        status: Status.Error,
        error: {
          message:
            "The Spotify player couldn't be initialized. " +
            "Try refreshing or using a different browser. " +
            "Note: this page is known to not work in Safari.",
          handler: () => location.reload(),
        },
      });
    });
    this.player.addListener("authentication_error", ({ message }) => {
      console.error(`authentication_error: ${message}`);
      this.setState({
        status: Status.Error,
        error: {
          message: "There has been an issue with Spotify credentials.",
          handler: () => location.reload(),
        },
      });
    });
    this.player.addListener("account_error", ({ message }) => {
      console.error(`account_error: ${message}`);
      this.setState({
        status: Status.Error,
        error: {
          message:
            "This page does not work for users without a Spotify Premium account. " +
            "This is a limitation of the Spotify API and we are very sorry!",
        },
      });
    });
    this.player.addListener("playback_error", ({ message }) => {
      console.error(`playback_error: ${message}`);
      this.setState({
        status: Status.Error,
        error: {
          message: "Something went wrong with playback.",
          handler: this.props.isListener ? () => this.sync() : null,
        },
      });
    });

    this.player.connect();
  }

  handleChange(state: Spotify.PlaybackState) {
    if (this.props.isListener || this.state.status < Status.Streaming) {
      return;
    }

    if (!state) {
      // This is what happens when the device gets disconnected
      if (this.state.status == Status.Streaming) {
        this.setState({
          status: Status.Error,
          error: {
            message: "Your Spotify account got disconnected from this device.",
            handler: () => this.transfer(),
          },
        });
      }
      return;
    }

    // Extract the information about the currently playing track
    const track = state.track_window.current_track;
    const data: TrackInfo = {
      uri: track.uri,
      type: track.type,
      name: track.name,
      id: track.id,
    };

    // Work out if this is a change
    if (state.paused && !this.state.isPaused) {
      // The playback should be paused
      this.setState({ isPaused: true });
      this.pauseBroadcast();
    } else if (!state.paused && this.state.isPaused) {
      // The playback should be unpaused
      this.setState({ isPaused: false, currentTrack: data });
      data.position_ms = state.position;
      this.changeTrack(data);
    } else if (!state.paused && this.state.currentTrack.uri != data.uri) {
      // The track has changed
      this.setState({ isPaused: false, currentTrack: data });
      this.changeTrack(data);
    }
  }

  getRoomId() {
    return `${this.props.userId}/${this.state.roomName}`;
  }

  startBroadcast() {
    if (this.state.status == Status.Loading || !this.state.deviceId) {
      this.setState({
        status: Status.Error,
        error: {
          message: "Device is not ready.",
          handler: () => location.reload(),
        },
      });
      return;
    }

    this.setState({ status: Status.Loading });
    this.api.call("/api/broadcast/start", {
      data: { device_id: this.state.deviceId, room_name: this.state.roomName },
      callback: (response) => {
        this.socket.emit("join", response.room_id);
        this.setState({
          status: Status.Streaming,
          streamUrl: response.stream_url,
          currentTrack: response.playing
            ? response.playing
            : this.state.currentTrack,
          listeners: response.number,
        });
      },
      error: (message) => {
        this.setState({
          status: Status.Error,
          error: {
            message: `Failed to start broadcast with message: ${message}.`,
            handler: () => this.startBroadcast(),
          },
        });
      },
    });
  }

  pauseBroadcast() {
    this.api.call("/api/broadcast/pause");
  }

  stopBroadcast() {
    this.player.pause();
    this.setState({ status: Status.Loading });
    this.api.call("/api/broadcast/stop", {
      data: { device_id: this.state.deviceId },
      callback: () => {
        this.setState({ status: Status.Ready });
      },
      error: (message) => {
        this.setState({
          status: Status.Error,
          error: {
            message: `Failed to stop broadcast with message: ${message}.`,
            handler: () => this.stopBroadcast(),
          },
        });
      },
    });
  }

  changeTrack(data: TrackInfo) {
    const track = data;
    this.api.call("/api/broadcast/change", {
      data: track,
      error: (message) => {
        this.setState({
          status: Status.Error,
          error: {
            message: `Failed to change the track with message: '${message}'.`,
            handler: () => this.changeTrack(track),
          },
        });
      },
    });
  }

  startListening() {
    if (this.state.status == Status.Loading || !this.state.deviceId) {
      this.setState({
        status: Status.Error,
        error: {
          message: "Device is not ready.",
          handler: () => location.reload(),
        },
      });
      return;
    }

    this.setState({ status: Status.Loading });
    this.api.call("/api/listen/start", {
      data: {
        device_id: this.state.deviceId,
        room_id: this.getRoomId(),
      },
      callback: (response) => {
        this.socket.emit("join", this.getRoomId());
        this.setState({
          status: Status.Streaming,
          listeners: response.number,
          currentTrack: response.playing,
          isPaused: false,
        });
      },
      error: (message) => {
        this.setState({
          status: Status.Error,
          error: {
            message: `Failed to start listening with message: ${message}.`,
            handler: () => this.startListening(),
          },
        });
      },
    });
  }

  stopListening() {
    this.player.pause();
    this.setState({ status: Status.Loading });
    this.api.call("/api/listen/stop", {
      data: { device_id: this.state.deviceId },
      callback: () => {
        this.setState({ status: Status.Ready });
      },
      error: (message) => {
        this.setState({
          status: Status.Error,
          error: {
            message: `Failed to stop listening with message: ${message}.`,
            handler: () => this.stopListening(),
          },
        });
      },
    });
  }

  sync() {
    this.setState({ status: Status.Loading });
    this.api.call("/api/listen/sync", {
      data: { device_id: this.state.deviceId },
      callback: (response) => {
        this.setState({
          status: Status.Streaming,
          listeners: response.number,
          currentTrack: response.playing,
        });
      },
      error: (message) => {
        this.setState({
          status: Status.Error,
          error: {
            message: `Failed to sync playback with message: ${message}.`,
            handler: () => this.sync(),
          },
        });
      },
    });
  }

  transfer() {
    this.setState({ status: Status.Loading });
    this.api.call("/api/transfer", {
      data: { device_id: this.state.deviceId },
      callback: (response) => {
        this.setState({
          status: Status.Ready,
          currentTrack: response.playing,
        });
      },
      error: (message) => {
        this.setState({
          status: Status.Error,
          error: {
            message: `Failed to transfer playback with message: ${message}.`,
            handler: () => this.transfer(),
          },
        });
      },
    });
  }

  handleStartStop() {
    if (this.state.status < Status.Ready) return;
    if (this.props.isListener) {
      if (this.state.status == Status.Streaming) {
        this.stopListening();
      } else {
        this.startListening();
      }
    } else {
      if (this.state.status == Status.Streaming) {
        this.stopBroadcast();
      } else {
        this.startBroadcast();
      }
    }
  }

  render() {
    return (
      <div>
        <small className="channel-label">channel (click to edit):</small>
        {this.props.isListener || this.state.status != Status.Ready ? (
          <div className="room-name">{this.state.roomName}</div>
        ) : (
          <input
            type="text"
            className="room-name"
            value={this.state.roomName}
            onChange={(event) =>
              this.setState({
                roomName: event.target.value.replace(
                  /[\s;,\/\?:@&=\+\$]/g,
                  "-"
                ),
              })
            }
          />
        )}
        <NowPlaying
          isPaused={this.state.isPaused}
          listeners={this.state.listeners}
          trackInfo={this.state.currentTrack}
        />
        {this.props.isListener ? (
          <>
            <ListenerButtons
              status={this.state.status}
              onStartStop={() => this.handleStartStop()}
              sync={() => this.sync()}
            />
            <ListenerStatusText status={this.state.status} />
          </>
        ) : (
          <>
            <BroadcasterButtons
              status={this.state.status}
              onStartStop={() => this.handleStartStop()}
              streamUrl={this.state.streamUrl}
            />
            <BroadcasterStatusText status={this.state.status} />
          </>
        )}
        {this.state.status == Status.Error ? (
          <ErrorMessage error={this.state.error} />
        ) : null}
      </div>
    );
  }
}

export const renderPlayer = (
  userId: string,
  roomName: string,
  div: Element
) => {
  ReactDOM.render(
    <App isListener={false} userId={userId} initialRoomName={roomName} />,
    div
  );
};

export const renderListener = (
  userId: string,
  roomName: string,
  div: Element
) => {
  ReactDOM.render(
    <App isListener={true} userId={userId} initialRoomName={roomName} />,
    div
  );
};

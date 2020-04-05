import React from "react";
import ReactDOM from "react-dom";
import io from "socket.io-client";

import { API } from "./api";
import { Status, TrackInfo, Error } from "./types";
import { NowPlaying } from "./components/now-playing";
import {
  ListenerButtons,
  BroadcasterButtons
} from "./components/player-buttons";
import {
  ListenerStatusText,
  BroadcasterStatusText
} from "./components/status-text";
import { ErrorMessage } from "./components/error-message";

interface AppProps {
  isListener: boolean;
  initialRoomId: string;
}

interface AppState {
  status: Status;
  isPaused: boolean;
  roomId: string;
  listeners: number;
  deviceId?: string;
  currentTrack?: TrackInfo;
  streamUrl?: string;
  error?: Error;
}

const ReadyState = {
  status: Status.Ready,
  isPaused: true,
  listeners: 0
};

class App extends React.Component<AppProps, AppState> {
  socket: SocketIOClient.Socket;
  player: Spotify.SpotifyPlayer;
  api: API;

  constructor(props: AppProps) {
    super(props);
    this.state = {
      status: Status.Loading,
      isPaused: true,
      roomId: this.props.initialRoomId,
      listeners: 0
    };

    this.api = new API();
    this.connectSocket();
    this.connectPlayer();

    // Handle window closes gracefully
    window.addEventListener("beforeunload", event => {
      if (this.state.status == Status.Streaming) {
        event.preventDefault();
        navigator.sendBeacon("/stop");
        this.setState(ReadyState);
        if (this.props.isListener) {
          return "Are you sure you want to stop listening?";
        }
        return "Are you sure you want to stop broadcasting?";
      }
    });
  }

  connectSocket() {
    this.socket = io.connect();
    this.socket.on("listeners", (data: any) => {
      this.setState({ listeners: data.number });
    });
    this.socket.on("changed", (data: any) => {
      this.setState({
        listeners: data.number,
        currentTrack: data.playing
      });
    });
    this.socket.on("close", () => {
      this.setState(ReadyState);
    });
  }

  connectPlayer() {
    // Initialize the player
    this.player = new Spotify.Player({
      name: "distance.dfm.io",
      volume: 1,
      getOAuthToken: (callback: (token: string) => void) => {
        this.api.call("/api/token", { callback: data => callback(data.token) });
      }
    });

    this.player.addListener("ready", ({ device_id }) => {
      console.log(`Device is ready: ${device_id}`);
      this.setState({ status: Status.Ready, deviceId: device_id });
    });

    this.player.addListener("not_ready", ({ device_id }) => {
      console.log(`Device has gone offline ${device_id}`);
    });

    this.player.addListener("player_state_changed", state =>
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
          handler: () => location.reload()
        }
      });
    });
    this.player.addListener("authentication_error", ({ message }) => {
      console.error(`authentication_error: ${message}`);
      this.setState({
        status: Status.Error,
        error: {
          message: "There has been an issue with Spotify credentials.",
          handler: () => location.reload()
        }
      });
    });
    this.player.addListener("account_error", ({ message }) => {
      console.error(`account_error: ${message}`);
      this.setState({
        status: Status.Error,
        error: {
          message:
            "This page does not work for users without a Spotify Premium account. " +
            "This is a limitation of the Spotify API and we are very sorry!"
        }
      });
    });
    this.player.addListener("playback_error", ({ message }) => {
      console.error(`playback_error: ${message}`);
      this.setState({
        status: Status.Error,
        error: {
          message: "Something went wrong with playback.",
          handler: this.props.isListener ? () => this.sync() : null
        }
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
            handler: () => this.transfer()
          }
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
      id: track.id
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

  startBroadcast() {
    if (this.state.status < Status.Ready || !this.state.deviceId) {
      this.setState({
        status: Status.Error,
        error: {
          message: "Device is not ready.",
          handler: () => location.reload()
        }
      });
      return;
    }

    this.setState({ status: Status.Loading });
    this.api.call("/api/broadcast/start", {
      data: { device_id: this.state.deviceId, room_id: this.state.roomId },
      callback: response => {
        this.socket.emit("join", response.room_id);
        this.setState({
          status: Status.Streaming,
          roomId: response.room_id,
          streamUrl: response.stream_url,
          currentTrack: response.playing
        });
      },
      error: message => {
        this.setState({
          status: Status.Error,
          error: {
            message: `Failed to start broadcast with message: ${message}.`,
            handler: () => this.startBroadcast()
          }
        });
      }
    });
  }

  pauseBroadcast() {
    this.api.call("/api/broadcast/pause");
  }

  stopBroadcast() {
    this.setState({ status: Status.Loading });
    this.api.call("/api/broadcast/stop", {
      callback: () => {
        this.socket.emit("leave", this.state.roomId);
        this.setState(ReadyState);
      },
      error: message => {
        this.setState({
          status: Status.Error,
          error: {
            message: `Failed to stop broadcast with message: ${message}.`,
            handler: () => this.stopBroadcast()
          }
        });
      }
    });
  }

  changeTrack(data: TrackInfo) {
    const track = data;
    this.api.call("/api/broadcast/change", {
      data: track,
      error: message => {
        this.setState({
          status: Status.Error,
          error: {
            message: `Failed to change the track with message: '${message}'.`,
            handler: () => this.changeTrack(track)
          }
        });
      }
    });
  }

  startListening() {
    if (this.state.status < Status.Ready || !this.state.deviceId) {
      this.setState({
        status: Status.Error,
        error: {
          message: "Device is not ready.",
          handler: () => location.reload()
        }
      });
      return;
    }

    this.setState({ status: Status.Loading });
    this.api.call("/api/listen/start", {
      data: {
        device_id: this.state.deviceId,
        room_id: this.props.initialRoomId
      },
      callback: response => {
        this.socket.emit("join", this.props.initialRoomId);
        this.setState({
          status: Status.Streaming,
          listeners: response.number,
          currentTrack: response.playing
        });
      },
      error: message => {
        this.setState({
          status: Status.Error,
          error: {
            message: `Failed to start listening with message: ${message}.`,
            handler: () => this.startListening()
          }
        });
      }
    });
  }

  stopListening() {
    this.setState({ status: Status.Loading });
    this.api.call("/api/listen/stop", {
      callback: () => {
        this.socket.emit("leave", this.props.initialRoomId);
        this.setState(ReadyState);
      },
      error: message => {
        this.setState({
          status: Status.Error,
          error: {
            message: `Failed to stop listening with message: ${message}.`,
            handler: () => this.stopListening()
          }
        });
      }
    });
  }

  sync() {
    this.setState({ status: Status.Loading });
    this.api.call("/api/listen/sync", {
      data: { device_id: this.state.deviceId },
      callback: response => {
        this.setState({
          status: Status.Streaming,
          currentTrack: response
        });
      },
      error: message => {
        this.setState({
          status: Status.Error,
          error: {
            message: `Failed to sync playback with message: ${message}.`,
            handler: () => this.sync()
          }
        });
      }
    });
  }

  transfer() {
    this.setState({ status: Status.Loading });
    this.api.call("/api/transfer", {
      data: { device_id: this.state.deviceId },
      callback: response => {
        this.setState({
          status: Status.Ready,
          currentTrack: response.playing
        });
      },
      error: message => {
        this.setState({
          status: Status.Error,
          error: {
            message: `Failed to transfer playback with message: ${message}.`,
            handler: () => this.transfer()
          }
        });
      }
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

  handleAction2() {
    if (this.state.status < Status.Streaming) return;
    if (this.props.isListener) {
      this.sync();
    } else {
      // this.copyLink()
    }
  }

  render() {
    return (
      <div>
        <NowPlaying
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

export const renderPlayer = (roomId: string, div: Element) => {
  ReactDOM.render(<App isListener={false} initialRoomId={roomId} />, div);
};

export const renderListener = (roomId: string, div: Element) => {
  ReactDOM.render(<App isListener={true} initialRoomId={roomId} />, div);
};

import React from "react";
import ReactDOM from "react-dom";
import io from "socket.io-client";

import { Controller, TrackInfo } from "../controller";
import { Button } from "./button";
import { StreamLink } from "./stream-link";
import { NowPlaying } from "./now-playing";

interface SpotifyPlayerProps {
  controller: Controller;
  isListener: boolean;
  roomId?: string;
}

interface SpotifyPlayerState {
  isPlaying: boolean;
  deviceId?: string;
  streamUrl?: string;
  roomId?: string;
  whatsNext: number;
  nowPlaying?: TrackInfo;
  listeners: number;
}

const stateText = {
  listen: [
    "Negotiating with servers...",
    'Click on "Start listening"...',
    "Sit back and enjoy the tunes!"
  ],
  play: [
    "Negotiating with servers...",
    'Click on "Start broadcast"...',
    "Play music in your Spotify app and share the link with your friends!"
  ]
};

export class SpotifyPlayer extends React.Component<
  SpotifyPlayerProps,
  SpotifyPlayerState
> {
  socket: SocketIOClient.Socket;
  player: Spotify.SpotifyPlayer;
  isPaused: boolean;
  currentTrack?: string;

  constructor(props: SpotifyPlayerProps) {
    super(props);

    const self = this;

    // Setup the default states
    this.currentTrack = null;
    this.isPaused = true;
    this.state = {
      isPlaying: false,
      roomId: props.roomId,
      whatsNext: 0,
      listeners: 0
    };

    // Initialize the socket
    this.socket = io.connect();
    this.socket.on("listeners", (data: any) => {
      self.setState({ listeners: data.number });
    });
    this.socket.on("changed", (data: any) => {
      self.setState({ listeners: data.number, nowPlaying: data.playing });
    });
    this.socket.on("close", () => {
      self.setState({
        isPlaying: false,
        whatsNext: 1,
        listeners: 0,
        nowPlaying: null
      });
    });

    // Shutdown
    window.addEventListener("beforeunload", event => {
      if (self.state.isPlaying) {
        event.preventDefault();
        navigator.sendBeacon("/stop");
        return "Are you sure you want to stop listening?";
      }
    });

    // Initialize the player
    this.player = new Spotify.Player({
      name: "distance.dfm.io",
      volume: 1,
      getOAuthToken: self.props.controller.token
    });

    this.player.addListener("ready", ({ device_id }) => {
      console.log(`Device is ready: ${device_id}`);
      self.setState({ deviceId: device_id, whatsNext: 1 });
    });

    this.player.addListener("player_state_changed", state => {
      if (self.props.isListener || !self.state.isPlaying) {
        return;
      }

      if (!state) {
        // self.stop();
        if (self.state.isPlaying) {
          self.setState({ isPlaying: false, whatsNext: 3 });
        }
        return;
      }

      const track = state.track_window.current_track;
      const data: TrackInfo = {
        uri: track.uri,
        type: track.type,
        name: track.name,
        id: track.id
      };
      this.setState({ nowPlaying: data });
      if (state.paused && !self.isPaused) {
        self.isPaused = true;
        self.props.controller.pause();
      } else if (!state.paused && self.isPaused) {
        self.isPaused = false;
        self.currentTrack = data.uri;
        data.position_ms = state.position;
        self.props.controller.change(data);
      } else if (!state.paused && self.currentTrack != data.uri) {
        self.currentTrack = data.uri;
        self.props.controller.change(data);
      }
    });

    this.player.addListener("initialization_error", ({ message }) => {
      console.error("initialization_error", message);
    });
    this.player.addListener("authentication_error", ({ message }) => {
      console.error("authentication_error", message);
    });
    this.player.addListener("account_error", ({ message }) => {
      console.error("account_error", message);
    });
    this.player.addListener("playback_error", ({ message }) => {
      console.error("playback_error", message);
    });

    this.player.addListener("not_ready", ({ device_id }) => {
      console.log(`Device has gone offline ${device_id}`);
    });

    this.player.connect();
  }

  start() {
    if (this.props.isListener) return;
    if (!this.state.deviceId) return;
    this.setState({ whatsNext: 0 });
    const self = this;
    this.props.controller.stream(
      this.state.deviceId,
      this.state.roomId,
      (roomId: string, streamUrl: string, playing?: TrackInfo) => {
        self.socket.emit("join", roomId);
        self.setState({
          isPlaying: true,
          streamUrl: streamUrl,
          roomId: roomId,
          whatsNext: 2,
          nowPlaying: playing
        });
      }
    );
  }

  stop() {
    if (this.props.isListener) return;
    this.setState({ whatsNext: 0 });
    const self = this;
    this.props.controller.close(() => {
      self.socket.emit("leave", self.state.roomId);
      self.setState({
        isPlaying: false,
        streamUrl: null,
        whatsNext: 1,
        listeners: 0
      });
    });
  }

  listen() {
    if (!this.props.isListener) return;
    if (!this.state.deviceId) return;
    this.setState({ whatsNext: 0 });
    const self = this;
    this.props.controller.listen(
      this.state.deviceId,
      this.props.roomId,
      (listeners: number, nowPlaying: TrackInfo) => {
        self.socket.emit("join", self.props.roomId);
        self.setState({
          isPlaying: true,
          whatsNext: 2,
          listeners: listeners,
          nowPlaying: nowPlaying
        });
      }
    );
  }

  pause() {
    if (!this.props.isListener) return;
    this.setState({ whatsNext: 0 });
    const self = this;
    this.props.controller.pause(() => {
      self.socket.emit("leave", self.props.roomId);
      self.setState({
        isPlaying: false,
        whatsNext: 1,
        nowPlaying: null,
        listeners: 0
      });
    });
  }

  sync() {
    this.setState({ whatsNext: 0 });
    const self = this;
    this.props.controller.sync(this.state.deviceId, data => {
      self.setState({ whatsNext: 2, nowPlaying: data });
    });
  }

  transfer() {
    this.setState({ whatsNext: 0 });
    const self = this;
    this.props.controller.transfer(this.state.deviceId, () => {
      self.setState({ whatsNext: 2 });
    });
  }

  render() {
    let whatsNext: string;
    let text: string;
    let action: () => void;
    let button2: JSX.Element;
    if (this.props.isListener) {
      whatsNext = stateText.listen[this.state.whatsNext];
      text = this.state.isPlaying ? "Stop listening" : "Start listening";
      action = this.state.isPlaying ? () => this.pause() : () => this.listen();
      button2 = (
        <Button
          text="Sync"
          onClick={() => this.sync()}
          enabled={this.state.isPlaying ? true : false}
        />
      );
    } else {
      whatsNext = stateText.play[this.state.whatsNext];
      text = this.state.isPlaying ? "Stop broadcast" : "Start broadcast";
      action = this.state.isPlaying ? () => this.stop() : () => this.start();
      button2 = <StreamLink streamUrl={this.state.streamUrl} />;
    }

    const error = (
      <span>
        <strong>Error:</strong> Your Spotify account got disconnected.{" "}
        <a href="#" onClick={() => this.transfer()}>
          Click here to reconnect.
        </a>
      </span>
    );

    return (
      <div>
        <NowPlaying
          trackInfo={this.state.nowPlaying}
          listeners={this.state.listeners}
        />
        <p className="lead">
          <Button
            text={text}
            onClick={action}
            enabled={this.state.deviceId ? true : false}
          />
          {button2}
        </p>
        <p>{whatsNext ? whatsNext : error}</p>
      </div>
    );
  }
}

export const renderPlayer = (controller: Controller, div: Element) => {
  ReactDOM.render(
    <SpotifyPlayer controller={controller} isListener={false} />,
    div
  );
};

export const renderListener = (
  controller: Controller,
  div: Element,
  roomId: string
) => {
  ReactDOM.render(
    <SpotifyPlayer controller={controller} roomId={roomId} isListener={true} />,
    div
  );
};

import React from "react";
import ReactDOM from "react-dom";

import { Controller } from "../controller";
import { Button } from "./button";
import { StreamLink } from "./stream-link";

export interface SpotifyPlayerProps {
  controller: Controller;
  roomId?: string;
}

export interface SpotifyPlayerState {
  isPlaying: boolean;
  deviceId?: string;
  streamUrl?: string;
}

export class SpotifyPlayer extends React.Component<
  SpotifyPlayerProps,
  SpotifyPlayerState
> {
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
      streamUrl: null,
      deviceId: null
    };

    // Initialize the player
    const player = new Spotify.Player({
      name: "distance.dfm.io",
      volume: 1,
      getOAuthToken: self.props.controller.token
    });

    player.addListener("ready", ({ device_id }) => {
      console.log(`Device is ready: ${device_id}`);
      self.setState({ deviceId: device_id });
    });

    player.addListener("player_state_changed", state => {
      console.log("player_state_changed", state);

      if (self.state.isPlaying) {
        if (!state) {
          self.stop();
          return;
        }

        const pos = state.position;
        const uri = state.track_window?.current_track?.uri;
        if (state.paused && !self.isPaused) {
          self.isPaused = true;
          self.props.controller.pause();
        } else if (!state.paused && self.isPaused) {
          self.isPaused = false;
          self.currentTrack = uri;
          self.props.controller.change(uri, pos);
        } else if (!state.paused && self.currentTrack != uri) {
          self.currentTrack = uri;
          self.props.controller.change(uri);
        }
      }
    });

    player.addListener("initialization_error", ({ message }) => {
      console.error("initialization_error", message);
    });
    player.addListener("authentication_error", ({ message }) => {
      console.error("authentication_error", message);
    });
    player.addListener("account_error", ({ message }) => {
      console.error("account_error", message);
    });
    player.addListener("playback_error", ({ message }) => {
      console.error("playback_error", message);
    });

    player.addListener("not_ready", ({ device_id }) => {
      console.log(`Device has gone offline ${device_id}`);
    });

    player.connect();
  }

  start() {
    console.log("starting broadcast");
    if (!this.state.deviceId) return;
    const self = this;
    this.props.controller.stream(
      this.state.deviceId,
      (roomId: string, streamUrl: string) => {
        console.log("started broadcast");
        self.setState({
          isPlaying: true,
          streamUrl: streamUrl
        });
      }
    );
  }

  stop() {
    console.log("stopping broadcast");
    const self = this;
    this.props.controller.close(() => {
      console.log("stopped broadcast");
      self.setState({ isPlaying: false, streamUrl: null });
    });
  }

  play() {
    console.log("starting to listen");
    if (!this.state.deviceId) return;
    this.props.controller.play(this.state.deviceId, this.props.roomId, () => {
      console.log("started listening");
      this.setState({ isPlaying: true });
    });
  }

  pause() {
    console.log("stopping listening");
    const self = this;
    this.props.controller.pause(() => {
      console.log("stopped listening");
      self.setState({ isPlaying: false });
    });
  }

  sync() {
    console.log("syncing");
    this.props.controller.sync(this.state.deviceId);
  }

  render() {
    if (this.props.roomId) {
      const text = this.state.isPlaying ? "Stop listening" : "Start listening";
      const action = this.state.isPlaying
        ? () => this.pause()
        : () => this.play();

      return (
        <p className="lead">
          <Button
            text={text}
            onClick={action}
            enabled={this.state.deviceId ? true : false}
          />
          <Button
            text="Sync"
            onClick={() => this.sync()}
            enabled={this.state.isPlaying ? true : false}
          />
        </p>
      );
    }
    const text = this.state.isPlaying ? "Stop broadcast" : "Start broadcast";
    const action = this.state.isPlaying
      ? () => this.stop()
      : () => this.start();

    return (
      <p className="lead">
        <Button
          text={text}
          onClick={action}
          enabled={this.state.deviceId ? true : false}
        />
        <StreamLink streamUrl={this.state.streamUrl} />
      </p>
    );
  }
}

export const renderPlayer = (controller: Controller, div: Element) => {
  ReactDOM.render(<SpotifyPlayer controller={controller} />, div);
};

export const renderListener = (
  controller: Controller,
  div: Element,
  roomId: string
) => {
  ReactDOM.render(
    <SpotifyPlayer controller={controller} roomId={roomId} />,
    div
  );
};

import React from "react";
import ReactDOM from "react-dom";

import { Controller } from "../controller";
import { Button } from "./button";
import { StreamLink } from "./stream-link";

export interface SpotifyPlayerProps {
  controller: Controller;
}

export interface SpotifyPlayerState {
  isBroadcasting: boolean;
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
      isBroadcasting: false,
      streamUrl: null,
      deviceId: null
    };

    // Initialize the player
    const player = new Spotify.Player({
      name: "Spotify Party",
      volume: 1,
      getOAuthToken: self.props.controller.token
    });

    player.addListener("ready", ({ device_id }) => {
      console.log(`Device is ready: ${device_id}`);
      self.setState({ deviceId: device_id });
    });

    player.addListener("player_state_changed", state => {
      console.log("player_state_changed", state);
      if (!state && self.state.isBroadcasting) {
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
          isBroadcasting: true,
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
      self.setState({ isBroadcasting: false, streamUrl: null });
    });
  }

  render() {
    const text = this.state.isBroadcasting
      ? "Stop broadcast"
      : "Start broadcast";
    const action = this.state.isBroadcasting
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

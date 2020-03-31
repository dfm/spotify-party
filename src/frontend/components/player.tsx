import React from "react";
import ReactDOM from "react-dom";

import { Controller, TrackInfo } from "../controller";
import { Button } from "./button";
import { StreamLink } from "./stream-link";
import { NowPlaying } from "./now-playing";

interface SpotifyPlayerProps {
  controller: Controller;
  roomId?: string;
}

interface SpotifyPlayerState {
  isPlaying: boolean;
  deviceId?: string;
  streamUrl?: string;
  whatsNext: number;
  nowPlaying?: TrackInfo;
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
      streamUrl: null,
      deviceId: null,
      whatsNext: 0
    };

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
      console.log("player_state_changed", state);

      if (self.state.isPlaying) {
        if (!state) {
          self.stop();
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
    console.log("starting broadcast");
    if (!this.state.deviceId) return;
    this.setState({ whatsNext: 0 });
    const self = this;
    this.props.controller.stream(
      this.state.deviceId,
      (roomId: string, streamUrl: string) => {
        console.log("started broadcast");
        self.setState({
          isPlaying: true,
          streamUrl: streamUrl,
          whatsNext: 2
        });
      }
    );
  }

  stop() {
    console.log("stopping broadcast");
    this.setState({ whatsNext: 0 });
    const self = this;
    this.props.controller.close(() => {
      console.log("stopped broadcast");
      self.setState({ isPlaying: false, streamUrl: null, whatsNext: 1 });
    });
  }

  listen() {
    console.log("starting to listen");
    if (!this.state.deviceId) return;
    this.setState({ whatsNext: 0 });
    this.props.controller.listen(this.state.deviceId, this.props.roomId, () => {
      console.log("started listening");
      this.setState({ isPlaying: true, whatsNext: 2 });
    });
  }

  pause() {
    console.log("stopping listening");
    this.setState({ whatsNext: 0 });
    const self = this;
    this.props.controller.pause(() => {
      console.log("stopped listening");
      self.setState({ isPlaying: false, whatsNext: 1 });
    });
  }

  sync() {
    console.log("syncing");
    this.setState({ whatsNext: 0 });
    const self = this;
    this.props.controller.sync(this.state.deviceId, () => {
      console.log("finished syncing");
      self.setState({ whatsNext: 2 });
    });
  }

  render() {
    let whatsNext: string;
    let text: string;
    let action: () => void;
    let button2: JSX.Element;
    if (this.props.roomId) {
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

    return (
      <div>
        <NowPlaying trackInfo={this.state.nowPlaying} />
        <p className="lead">
          <Button
            text={text}
            onClick={action}
            enabled={this.state.deviceId ? true : false}
          />
          {button2}
        </p>
        <p>{whatsNext}</p>
      </div>
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

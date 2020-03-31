import React from "react";
import { TrackInfo } from "../controller";

interface NowPlayingProps {
  trackInfo?: TrackInfo;
}

export class NowPlaying extends React.Component<NowPlayingProps> {
  render() {
    if (this.props.trackInfo) {
      const url = `https://open.spotify.com/${this.props.trackInfo.type}/${this.props.trackInfo.id}`;
      return (
        <p>
          Now playing:{" "}
          <a target="_blank" rel="noopener noreferrer" href={url}>
            {this.props.trackInfo.name}
          </a>
        </p>
      );
    }
    return <p>Now playing: Nothing.</p>;
  }
}

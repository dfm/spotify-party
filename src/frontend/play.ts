import "./style/base.css";

import { renderPlayer } from "./components/player";
import { Controller } from "./controller";

window.onSpotifyWebPlaybackSDKReady = () => {
  const controller = new Controller();
  renderPlayer(controller, document.getElementById("player"));
};

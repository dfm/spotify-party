import "./style/base.css";

import { renderListener } from "./components/player";
import { Controller } from "./controller";

window.onSpotifyWebPlaybackSDKReady = () => {
  const controller = new Controller();
  renderListener(
    controller,
    document.getElementById("player"),
    window.location.pathname.split("/").pop()
  );
};

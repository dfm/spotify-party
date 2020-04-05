// import React from "react";
// import ReactDOM from "react-dom";
// import io from "socket.io-client";

// import { Controller, TrackInfo } from "../controller";
// import { Button } from "./button";
// import { NowPlaying } from "./now-playing";

// export enum State {
//   Error = -1,
//   Loading = 0,
//   Ready = 1,
//   Streaming = 2
// }

// interface PlayerState {
//   state: State;
//   listeners: number;
//   currentTrack?: TrackInfo;
//   streamUrl?: string;
//   error?: string | JSX.Element;
// }

// export class Player extends React.Component<
//   {
//     onStartStop: () => void;
//     onAction2: () => void;
//   },
//   PlayerState
// > {
//   actionText: string;
//   action2Text: string;
//   stateText: string[];

//   state: PlayerState = {
//     state: State.Loading,
//     listeners: 0,
//     currentTrack: null,
//     streamUrl: null,
//     error: null
//   };

//   render() {
//     return (
//       <div>
//         <NowPlaying
//           trackInfo={this.state.currentTrack}
//           listeners={this.state.listeners}
//         />
//         <p className="lead">
//           <Button
//             text={
//               this.state.state == State.Streaming
//                 ? `Stop ${this.actionText}`
//                 : `Start ${this.actionText}`
//             }
//             onClick={() => this.props.onStartStop()}
//             enabled={this.state.state >= State.Ready}
//           />
//           <Button
//             text="Sync"
//             onClick={() => this.props.onAction2()}
//             enabled={this.state.state == State.Streaming}
//           />
//         </p>
//         <p>
//           {this.state.state > State.Error
//             ? this.stateText[this.state.state]
//             : this.state.error}
//         </p>
//       </div>
//     );
//   }
// }

// export class Broadcaster extends Player {
//   actionText = "broadcast";
//   action2Text = "Copy link";
//   stateText = [
//     "Negotiating with servers...",
//     'Click on "Start broadcast"...',
//     "Play music in your Spotify app and share the link with your friends!"
//   ];
// }

// export class Listener extends Player {
//   actionText = "listening";
//   action2Text = "Sync";
//   stateText = [
//     "Negotiating with servers...",
//     'Click on "Start listening"...',
//     "Sit back and enjoy the tunes!"
//   ];
// }

// // export class SpotifyPlayer extends React.Component<
// //   {},
// //   {
// //     state: State;
// //     listeners: number;
// //     currentTrack?: TrackInfo;
// //     errorText?: string;
// //   }
// // > {
// //   constructor(props: {}) {
// //     super(props);
// //     this.state = {
// //       state: State.Loading,
// //       listeners: 0
// //     };
// //   }

// //   start() {
// //     if (this.props.isListener) return;
// //     if (!this.state.deviceId) return;
// //     this.setState({ whatsNext: 0 });
// //     const self = this;
// //     this.props.controller.stream(
// //       this.state.deviceId,
// //       this.state.roomId,
// //       (roomId: string, streamUrl: string, playing?: TrackInfo) => {
// //         self.socket.emit("join", roomId);
// //         self.setState({
// //           isPlaying: true,
// //           streamUrl: streamUrl,
// //           roomId: roomId,
// //           whatsNext: 2,
// //           nowPlaying: playing
// //         });
// //       }
// //     );
// //   }

// //   stop() {
// //     if (this.props.isListener) return;
// //     this.setState({ whatsNext: 0 });
// //     const self = this;
// //     this.props.controller.close(() => {
// //       self.socket.emit("leave", self.state.roomId);
// //       self.setState({
// //         isPlaying: false,
// //         streamUrl: null,
// //         whatsNext: 1,
// //         listeners: 0
// //       });
// //     });
// //   }

// //   listen() {
// //     if (!this.props.isListener) return;
// //     if (!this.state.deviceId) return;
// //     this.setState({ whatsNext: 0 });
// //     const self = this;
// //     this.props.controller.listen(
// //       this.state.deviceId,
// //       this.props.roomId,
// //       (listeners: number, nowPlaying: TrackInfo) => {
// //         self.socket.emit("join", self.props.roomId);
// //         self.setState({
// //           isPlaying: true,
// //           whatsNext: 2,
// //           listeners: listeners,
// //           nowPlaying: nowPlaying
// //         });
// //       }
// //     );
// //   }

// //   pause() {
// //     if (!this.props.isListener) return;
// //     this.setState({ whatsNext: 0 });
// //     const self = this;
// //     this.props.controller.pause(() => {
// //       self.socket.emit("leave", self.props.roomId);
// //       self.setState({
// //         isPlaying: false,
// //         whatsNext: 1,
// //         nowPlaying: null,
// //         listeners: 0
// //       });
// //     });
// //   }

// //   sync() {
// //     this.setState({ whatsNext: 0 });
// //     const self = this;
// //     this.props.controller.sync(this.state.deviceId, data => {
// //       self.setState({ whatsNext: 2, nowPlaying: data });
// //     });
// //   }

// //   transfer() {
// //     this.setState({ whatsNext: 0 });
// //     const self = this;
// //     this.props.controller.transfer(this.state.deviceId, () => {
// //       self.setState({ whatsNext: 2 });
// //     });
// //   }

// //   render() {
// //     let whatsNext: string;
// //     let text: string;
// //     let action: () => void;
// //     let button2: JSX.Element;
// //     if (this.props.isListener) {
// //       whatsNext = stateText.listen[this.state.whatsNext];
// //       text = this.state.isPlaying ? "Stop listening" : "Start listening";
// //       action = this.state.isPlaying ? () => this.pause() : () => this.listen();
// //       button2 = (
// //         <Button
// //           text="Sync"
// //           onClick={() => this.sync()}
// //           enabled={this.state.isPlaying ? true : false}
// //         />
// //       );
// //     } else {
// //       whatsNext = stateText.play[this.state.whatsNext];
// //       text = this.state.isPlaying ? "Stop broadcast" : "Start broadcast";
// //       action = this.state.isPlaying ? () => this.stop() : () => this.start();
// //       button2 = <StreamLink streamUrl={this.state.streamUrl} />;
// //     }

// //     const error = (
// //       <span>
// //         <strong>Error:</strong> Your Spotify account got disconnected.{" "}
// //         <a href="#" onClick={() => this.transfer()}>
// //           Click here to reconnect.
// //         </a>
// //       </span>
// //     );

// //     return (
// //       <div>
// //         <NowPlaying
// //           trackInfo={this.state.nowPlaying}
// //           listeners={this.state.listeners}
// //         />
// //         <p className="lead">
// //           <Button
// //             text={text}
// //             onClick={action}
// //             enabled={this.state.deviceId ? true : false}
// //           />
// //           {button2}
// //         </p>
// //         <p>{whatsNext ? whatsNext : error}</p>
// //       </div>
// //     );
// //   }
// // }

// export const renderPlayer = (controller: Controller, div: Element) => {
//   ReactDOM.render(
//     <SpotifyPlayer controller={controller} isListener={false} />,
//     div
//   );
// };

// export const renderListener = (
//   controller: Controller,
//   div: Element,
//   roomId: string
// ) => {
//   ReactDOM.render(
//     <SpotifyPlayer controller={controller} roomId={roomId} isListener={true} />,
//     div
//   );
// };

import React from "react";
import { Status } from "../types";

function StatusText(props: { status: Status; statusText: string[] }) {
  if (props.status == Status.Error) {
    return null;
  }
  return <p>{props.statusText[props.status]}</p>;
}

export function ListenerStatusText(props: { status: Status }) {
  const statusText = [
    "Negotiating with servers...",
    'Click on "Start listening"...',
    "Sit back and enjoy the tunes!"
  ];
  return <StatusText status={props.status} statusText={statusText} />;
}

export function BroadcasterStatusText(props: { status: Status }) {
  const statusText = [
    "Negotiating with servers...",
    'Click on "Start broadcast"...',
    "Play music in your Spotify app and share the link with your friends!"
  ];
  return <StatusText status={props.status} statusText={statusText} />;
}

import React from "react";

import { Status } from "../types";
import { Button } from "./button";
import { StreamLink } from "./stream-link";

function PlayerButtons(props: {
  actionText: string;
  // action2Text: string;
  status: Status;
  onStartStop: () => void;
  // onAction2: () => void;
  button: JSX.Element;
}) {
  return (
    <p className="lead">
      <Button
        text={
          props.status == Status.Streaming
            ? `Stop ${props.actionText}`
            : `Start ${props.actionText}`
        }
        onClick={() => props.onStartStop()}
        enabled={props.status >= Status.Ready}
      />
      {props.button}
    </p>
  );
}

export function ListenerButtons(props: {
  status: Status;
  onStartStop: () => void;
  sync: () => void;
}) {
  return (
    <PlayerButtons
      actionText="listening"
      status={props.status}
      onStartStop={props.onStartStop}
      button={
        <Button
          text="Sync"
          onClick={() => props.sync()}
          enabled={props.status == Status.Streaming}
        />
      }
    />
  );
}

export function BroadcasterButtons(props: {
  status: Status;
  onStartStop: () => void;
  streamUrl?: string;
}) {
  return (
    <PlayerButtons
      actionText="broadcast"
      status={props.status}
      onStartStop={props.onStartStop}
      button={
        <StreamLink
          streamUrl={props.streamUrl}
          enabled={props.status == Status.Streaming}
        />
      }
    />
  );
}

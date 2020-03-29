import React from "react";
import copy from "copy-to-clipboard";
import { Button } from "./button";

export interface StreamLinkProps {
  streamUrl?: string;
}

export interface StreamLinkState {
  isCopied: boolean;
}

export class StreamLink extends React.Component<
  StreamLinkProps,
  StreamLinkState
> {
  constructor(props: StreamLinkProps) {
    super(props);
    this.state = { isCopied: false };
  }

  handleClick() {
    const self = this;
    copy(this.props.streamUrl);
    this.setState({ isCopied: true });
    setTimeout(() => {
      self.setState({ isCopied: false });
    }, 1000);
  }

  render() {
    return (
      <Button
        text={this.state.isCopied ? "Copied to clipboard" : "Copy stream URL"}
        enabled={this.props.streamUrl ? true : false}
        onClick={() => {
          this.handleClick();
        }}
      />
    );
  }
}

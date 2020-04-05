import React from "react";
import copy from "copy-to-clipboard";
import { Button } from "./button";

export class StreamLink extends React.Component<
  { enabled: boolean; streamUrl?: string },
  { isCopied: boolean }
> {
  state = { isCopied: false };

  handleClick() {
    copy(this.props.streamUrl);
    this.setState({ isCopied: true });
    setTimeout(() => {
      this.setState({ isCopied: false });
    }, 1000);
  }

  render() {
    return (
      <Button
        text={this.state.isCopied ? "Copied to clipboard" : "Copy link"}
        enabled={this.props.enabled}
        onClick={() => this.handleClick()}
      />
    );
  }
}

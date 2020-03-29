import React from "react";

export interface ButtonProps {
  enabled: boolean;
  text: string;
  onClick: () => void;
}

export class Button extends React.Component<ButtonProps, {}> {
  constructor(props: ButtonProps) {
    super(props);
  }

  setEnabled(enabled: boolean) {
    this.setState({ enabled: enabled });
  }

  setText(text: string) {
    this.setState({ text: text });
  }

  render() {
    if (this.props.enabled) {
      return (
        <button
          className="btn btn-lg btn-secondary"
          type="button"
          onClick={this.props.onClick}
        >
          {this.props.text}
        </button>
      );
    }
    return (
      <button
        className="btn btn-lg btn-secondary"
        type="button"
        disabled
        onClick={this.props.onClick}
      >
        {this.props.text}
      </button>
    );
  }
}

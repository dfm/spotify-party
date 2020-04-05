import React from "react";
import { Error } from "../types";

export function ErrorMessage(props: { error?: Error }) {
  let message = "Something went horribly wrong!";
  if (props.error?.message) message = props.error.message;
  return (
    <p className="alert alert-danger" role="alert">
      <strong>Error:</strong> {message}{" "}
      {props.error?.handler ? (
        <span className="retry" onClick={() => props.error?.handler()}>
          Click here to retry.
        </span>
      ) : null}
    </p>
  );
}

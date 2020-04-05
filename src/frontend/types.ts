export enum Status {
  Error = -1,
  Loading = 0,
  Ready = 1,
  Streaming = 2
}

export interface TrackInfo {
  uri: string;
  name: string;
  type: string;
  id: string;
  position_ms?: number;
}

export interface Error {
  message?: string;
  handler?: () => void;
}

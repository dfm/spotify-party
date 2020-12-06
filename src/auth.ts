export function redirect() {
  const search = new URLSearchParams(window.location.search);
  const params = new URLSearchParams({
    client_id: "76e7a14e109144fd90e32bc4750f589a",
    response_type: "token",
    redirect_uri: "http://localhost:8000/callback",
    state: search.get("state"),
  });
  window.location.replace(
    "https://accounts.spotify.com/authorize?" + params.toString()
  );
}

export function callback() {
  const params = new URLSearchParams(window.location.hash.substr(1));
  window.opener.spotifyCallback(
    params.get("access_token"),
    params.get("state")
  );
}

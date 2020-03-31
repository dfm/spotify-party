CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    display_name TEXT,
    access_token TEXT,
    refresh_token TEXT,
    expires_at INT,
    listening_to TEXT,
    playing_to TEXT UNIQUE,
    paused INT DEFAULT 0,
    device_id TEXT
)

CREATE TABLE running_shoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    brand TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    max_distance_m INTEGER NOT NULL CHECK(max_distance_m > 0),
    photo_filename TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE activities ADD COLUMN shoe_id INTEGER REFERENCES running_shoes(id) ON DELETE SET NULL;
CREATE INDEX idx_activities_shoe ON activities(shoe_id);

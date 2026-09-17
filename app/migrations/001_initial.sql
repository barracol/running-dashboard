CREATE TABLE activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_date TEXT NOT NULL,
    distance_m INTEGER NOT NULL CHECK (distance_m >= 0),
    duration_s INTEGER NOT NULL CHECK (duration_s > 0),
    calories INTEGER CHECK (calories IS NULL OR calories >= 0),
    avg_heart_rate INTEGER CHECK (avg_heart_rate IS NULL OR avg_heart_rate BETWEEN 20 AND 250),
    activity_type TEXT NOT NULL DEFAULT 'running',
    notes TEXT NOT NULL DEFAULT '',
    original_filename TEXT,
    original_file_path TEXT,
    original_file_hash TEXT UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_activities_date ON activities(activity_date DESC);
CREATE INDEX idx_activities_type ON activities(activity_type);

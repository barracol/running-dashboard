ALTER TABLE activities ADD COLUMN record_status TEXT NOT NULL DEFAULT 'verified'
CHECK (record_status IN ('verified', 'draft'));

CREATE INDEX idx_activities_status_date
ON activities(record_status, activity_date DESC, id DESC);

CREATE TABLE planned_workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    planned_date TEXT NOT NULL,
    activity_type TEXT NOT NULL DEFAULT 'running',
    title TEXT NOT NULL,
    target_distance_m INTEGER CHECK (target_distance_m IS NULL OR target_distance_m >= 0),
    target_duration_s INTEGER CHECK (target_duration_s IS NULL OR target_duration_s > 0),
    notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'completed', 'skipped')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_planned_workouts_date ON planned_workouts(planned_date, id);

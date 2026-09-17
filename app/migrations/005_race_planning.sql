CREATE TABLE planned_races (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    race_date TEXT NOT NULL,
    name TEXT NOT NULL,
    location TEXT NOT NULL DEFAULT '',
    distance_m INTEGER CHECK (distance_m IS NULL OR distance_m > 0),
    cost_cents INTEGER CHECK (cost_cents IS NULL OR cost_cents >= 0),
    website_url TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    registered INTEGER NOT NULL DEFAULT 0 CHECK (registered IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_planned_races_date ON planned_races(race_date, id);
CREATE INDEX idx_planned_races_registered_date ON planned_races(registered, race_date);

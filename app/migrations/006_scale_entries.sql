CREATE TABLE scale_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    measured_date TEXT NOT NULL,
    weight_kg REAL CHECK (weight_kg IS NULL OR weight_kg BETWEEN 20 AND 500),
    body_fat_percent REAL CHECK (body_fat_percent IS NULL OR body_fat_percent BETWEEN 0 AND 100),
    muscle_mass_kg REAL CHECK (muscle_mass_kg IS NULL OR muscle_mass_kg BETWEEN 0 AND 300),
    water_percent REAL CHECK (water_percent IS NULL OR water_percent BETWEEN 0 AND 100),
    bmi REAL CHECK (bmi IS NULL OR bmi BETWEEN 5 AND 100),
    visceral_fat REAL CHECK (visceral_fat IS NULL OR visceral_fat BETWEEN 0 AND 100),
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_scale_entries_date ON scale_entries(measured_date DESC, id DESC);

ALTER TABLE running_shoes ADD COLUMN manual_distance_m INTEGER NOT NULL DEFAULT 0 CHECK(manual_distance_m >= 0);

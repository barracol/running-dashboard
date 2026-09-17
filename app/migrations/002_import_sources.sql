ALTER TABLE activities ADD COLUMN source TEXT;
ALTER TABLE activities ADD COLUMN source_activity_id TEXT;
ALTER TABLE activities ADD COLUMN activity_name TEXT;
ALTER TABLE activities ADD COLUMN elapsed_s INTEGER;

CREATE UNIQUE INDEX idx_activities_source_id
ON activities(source, source_activity_id)
WHERE source IS NOT NULL AND source_activity_id IS NOT NULL;

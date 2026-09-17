CREATE INDEX IF NOT EXISTS idx_activities_type_date
ON activities(activity_type, activity_date DESC, id DESC);

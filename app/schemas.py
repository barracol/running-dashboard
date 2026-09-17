from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ActivityType = Literal[
    "running", "trail_running", "walking", "hiking", "cycling", "mountain_biking",
    "swimming", "rowing", "kayaking", "skiing", "cross_country_skiing", "skating",
    "workout", "yoga", "football", "tennis", "other",
]


class ActivityBase(BaseModel):
    activity_date: date
    distance_m: int = Field(ge=0, le=1_000_000)
    duration_s: int = Field(gt=0, le=604_800)
    calories: int | None = Field(default=None, ge=0, le=100_000)
    avg_heart_rate: int | None = Field(default=None, ge=20, le=250)
    activity_type: ActivityType = "running"
    notes: str = Field(default="", max_length=2_000)
    shoe_id: int | None = Field(default=None, gt=0)


class ActivityCreate(ActivityBase):
    pass


class ActivityUpdate(BaseModel):
    activity_date: date | None = None
    distance_m: int | None = Field(default=None, ge=0, le=1_000_000)
    duration_s: int | None = Field(default=None, gt=0, le=604_800)
    calories: int | None = Field(default=None, ge=0, le=100_000)
    avg_heart_rate: int | None = Field(default=None, ge=20, le=250)
    activity_type: ActivityType | None = None
    notes: str | None = Field(default=None, max_length=2_000)
    shoe_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def required_fields_cannot_be_null(self):
        required = {"activity_date", "distance_m", "duration_s", "activity_type"}
        for field in required & self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class Activity(ActivityBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    original_filename: str | None = None
    original_file_hash: str | None = None
    activity_name: str | None = None
    elapsed_s: int | None = None
    source: str | None = None
    record_status: Literal["verified", "draft"] = "verified"
    created_at: str
    updated_at: str


class ImportResult(BaseModel):
    id: int
    filename: str
    sha256: str
    status: str = "stored_not_parsed"


class PlannedWorkoutBase(BaseModel):
    planned_date: date
    activity_type: ActivityType = "running"
    title: str = Field(min_length=1, max_length=200)
    target_distance_m: int | None = Field(default=None, ge=0, le=1_000_000)
    target_duration_s: int | None = Field(default=None, gt=0, le=604_800)
    notes: str = Field(default="", max_length=2_000)
    status: Literal["planned", "completed", "skipped"] = "planned"


class PlannedWorkoutCreate(PlannedWorkoutBase):
    pass


class PlannedWorkoutUpdate(BaseModel):
    planned_date: date | None = None
    activity_type: ActivityType | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    target_distance_m: int | None = Field(default=None, ge=0, le=1_000_000)
    target_duration_s: int | None = Field(default=None, gt=0, le=604_800)
    notes: str | None = Field(default=None, max_length=2_000)
    status: Literal["planned", "completed", "skipped"] | None = None

    @model_validator(mode="after")
    def non_nullable_fields(self):
        for field in {"planned_date", "activity_type", "title", "status"} & self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class PlannedWorkout(PlannedWorkoutBase):
    id: int
    created_at: str
    updated_at: str


Weekday = Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


class CoachPlanRequest(BaseModel):
    week_start: date
    sessions: int = Field(default=3, ge=1, le=7)
    swimming_sessions: int = Field(default=0, ge=0, le=7)
    cycling_sessions: int = Field(default=0, ge=0, le=7)
    available_days: list[Weekday] = Field(default_factory=list, max_length=7)
    goal: str = Field(default="Migliorare gradualmente mantenendo continuità", max_length=500)
    instructions: str = Field(default="", max_length=1_500)

    @model_validator(mode="after")
    def week_must_start_on_monday(self):
        if self.week_start.weekday() != 0:
            raise ValueError("week_start must be a Monday")
        if self.available_days and self.sessions > len(set(self.available_days)):
            raise ValueError("sessions cannot exceed the available days")
        if self.swimming_sessions > self.sessions:
            raise ValueError("swimming_sessions cannot exceed sessions")
        if self.cycling_sessions > self.sessions:
            raise ValueError("cycling_sessions cannot exceed sessions")
        if self.swimming_sessions + self.cycling_sessions > self.sessions:
            raise ValueError("swimming_sessions and cycling_sessions cannot exceed sessions")
        return self


class CoachFeedbackRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2_000)


class CoachFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(min_length=1, max_length=6_000)
    highlights: list[str] = Field(default_factory=list, max_length=8)
    cautions: list[str] = Field(default_factory=list, max_length=8)


class CoachWorkout(BaseModel):
    model_config = ConfigDict(extra="forbid")
    planned_date: date
    activity_type: ActivityType
    title: str = Field(min_length=1, max_length=200)
    target_distance_m: int | None = Field(default=None, ge=0, le=200_000)
    target_duration_s: int | None = Field(default=None, gt=0, le=28_800)
    intensity: Literal["recovery", "easy", "moderate", "hard", "long"]
    notes: str = Field(default="", max_length=1_500)
    rationale: str = Field(default="", max_length=800)


class CoachPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    week_start: date
    analysis_summary: str = Field(min_length=1, max_length=2_000)
    load_guidance: str = Field(min_length=1, max_length=1_000)
    cautions: list[str] = Field(default_factory=list, max_length=8)
    workouts: list[CoachWorkout] = Field(min_length=1, max_length=7)

    @model_validator(mode="after")
    def workouts_belong_to_week(self):
        end = self.week_start.fromordinal(self.week_start.toordinal() + 6)
        dates = [item.planned_date for item in self.workouts]
        if any(item < self.week_start or item > end for item in dates):
            raise ValueError("All workouts must belong to the selected week")
        if len(dates) != len(set(dates)):
            raise ValueError("Only one workout per day is supported")
        return self


class CoachAcceptResult(BaseModel):
    created: list[PlannedWorkout]


class PlannedRaceBase(BaseModel):
    race_date: date
    name: str = Field(min_length=1, max_length=200)
    location: str = Field(default="", max_length=300)
    distance_m: int | None = Field(default=None, gt=0, le=1_000_000)
    cost_cents: int | None = Field(default=None, ge=0, le=10_000_000)
    website_url: str = Field(default="", max_length=1_000)
    notes: str = Field(default="", max_length=2_000)
    registered: bool = False


class PlannedRaceCreate(PlannedRaceBase):
    pass


class PlannedRaceUpdate(BaseModel):
    race_date: date | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    location: str | None = Field(default=None, max_length=300)
    distance_m: int | None = Field(default=None, gt=0, le=1_000_000)
    cost_cents: int | None = Field(default=None, ge=0, le=10_000_000)
    website_url: str | None = Field(default=None, max_length=1_000)
    notes: str | None = Field(default=None, max_length=2_000)
    registered: bool | None = None

    @model_validator(mode="after")
    def required_race_fields(self):
        for field in {"race_date", "name", "location", "website_url", "notes", "registered"} & self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class PlannedRace(PlannedRaceBase):
    id: int
    created_at: str
    updated_at: str


class ScaleEntryBase(BaseModel):
    measured_date: date
    weight_kg: float | None = Field(default=None, ge=20, le=500)
    body_fat_percent: float | None = Field(default=None, ge=0, le=100)
    muscle_mass_kg: float | None = Field(default=None, ge=0, le=300)
    water_percent: float | None = Field(default=None, ge=0, le=100)
    bmi: float | None = Field(default=None, ge=5, le=100)
    visceral_fat: float | None = Field(default=None, ge=0, le=100)
    notes: str = Field(default="", max_length=2_000)

    @model_validator(mode="after")
    def at_least_one_measurement(self):
        fields = ("weight_kg", "body_fat_percent", "muscle_mass_kg", "water_percent", "bmi", "visceral_fat")
        if not any(getattr(self, field) is not None for field in fields):
            raise ValueError("At least one measurement is required")
        return self


class ScaleEntryCreate(ScaleEntryBase):
    pass


class ScaleEntryUpdate(BaseModel):
    measured_date: date | None = None
    weight_kg: float | None = Field(default=None, ge=20, le=500)
    body_fat_percent: float | None = Field(default=None, ge=0, le=100)
    muscle_mass_kg: float | None = Field(default=None, ge=0, le=300)
    water_percent: float | None = Field(default=None, ge=0, le=100)
    bmi: float | None = Field(default=None, ge=5, le=100)
    visceral_fat: float | None = Field(default=None, ge=0, le=100)
    notes: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def date_cannot_be_null(self):
        if "measured_date" in self.model_fields_set and self.measured_date is None:
            raise ValueError("measured_date cannot be null")
        return self


class ScaleEntry(ScaleEntryBase):
    id: int
    created_at: str
    updated_at: str


class SportsDocumentsUpdate(BaseModel):
    run_card_number: str = Field(default="", max_length=100)
    run_card_expiry: date | None = None
    medical_certificate_expiry: date | None = None


class SportsDocuments(SportsDocumentsUpdate):
    updated_at: str


class RunningShoeBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    brand: str = Field(default="", max_length=100)
    model: str = Field(default="", max_length=150)
    max_distance_m: int = Field(gt=0, le=5_000_000)
    manual_distance_m: int = Field(default=0, ge=0, le=20_000_000)
    active: bool = True


class RunningShoeCreate(RunningShoeBase):
    pass


class RunningShoeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    brand: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=150)
    max_distance_m: int | None = Field(default=None, gt=0, le=5_000_000)
    manual_distance_m: int | None = Field(default=None, ge=0, le=20_000_000)
    active: bool | None = None


class RunningShoe(RunningShoeBase):
    id: int
    photo_url: str | None = None
    distance_m: int = 0
    tracked_distance_m: int = 0
    activities: int = 0
    avg_speed_kmh: float | None = None
    avg_pace_min_km: float | None = None
    remaining_m: int = 0
    usage_percent: float = 0
    created_at: str
    updated_at: str

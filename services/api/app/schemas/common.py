from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False


class UserOut(ORMModel):
    id: UUID
    email: EmailStr
    full_name: str
    role: str
    status: str
    facility_id: UUID
    facility_name: str | None = None
    facility_code: str | None = None


class TokenUserResponse(BaseModel):
    user: UserOut
    csrf_token: str
    disclaimer: str


class ChildCreate(BaseModel):
    date_of_birth: date
    sex: str
    facility_id: UUID | None = None
    external_patient_id: str | None = None
    responsible_team: str | None = None
    caregiver_relationship: str | None = "mother"
    caregiver_display_name: str | None = None
    caregiver_phone: str | None = None


class ChildUpdate(BaseModel):
    responsible_team: str | None = None
    status: str | None = None
    external_patient_id: str | None = None


class ChildListItem(ORMModel):
    id: UUID
    pseudonymous_id: str
    age_months: int
    sex: str
    last_visit: datetime | None = None
    current_status: str | None = None
    current_risk: float | None = None
    progress: str | None = None
    next_follow_up: date | None = None
    facility_code: str | None = None
    alert_type: str | None = None
    synthetic: bool = True


class AnthropometricIn(BaseModel):
    age_months: float
    sex: str
    height_cm: float | None = None
    weight_kg: float | None = None
    muac_cm: float | None = None
    birth_weight_kg: float | None = None
    head_circumference_cm: float | None = None
    previous_weight_kg: float | None = None
    previous_height_cm: float | None = None


class SocioeconomicIn(BaseModel):
    wealth_proxy: str | None = None
    maternal_education: str | None = None
    paternal_education: str | None = None
    maternal_employment: str | None = None
    household_size: int | None = None
    geographical_area: str | None = None
    drinking_water: str | None = None
    sanitation: str | None = None
    household_changed: bool = True


class DietaryIn(BaseModel):
    breastfeeding_status: str | None = None
    breastfeeding_duration_months: float | None = None
    complementary_feeding: bool | None = None
    dietary_diversity_score: int | None = None
    meal_frequency: int | None = None
    food_groups: list[str] | None = None
    micronutrient_supplementation: bool | None = None


class MaternalIn(BaseModel):
    maternal_bmi: float | None = None
    gestational_age_weeks: int | None = None
    immunization_uptodate: bool | None = None
    vitamin_a: bool | None = None
    recent_diarrhoea: bool | None = None
    recent_respiratory_illness: bool | None = None
    recent_hospitalization: bool | None = None
    birth_characteristics: str | None = None


class VisitCreate(BaseModel):
    visit_date: datetime
    visit_type: str = "follow_up"
    scheduled: bool = True
    save_as_draft: bool = False
    confirmation_attested: bool = False
    anthropometric: AnthropometricIn
    socioeconomic: SocioeconomicIn | None = None
    dietary: DietaryIn | None = None
    maternal_child_health: MaternalIn | None = None


class VisitOut(ORMModel):
    id: UUID
    child_id: UUID
    visit_number: int
    visit_date: datetime
    visit_type: str
    status: str
    scheduled: bool
    data_quality: dict | None = None


class PredictionOut(BaseModel):
    id: UUID
    visit_id: UUID
    run_number: int
    is_active: bool
    mode: str
    status_prediction: str
    severity_prediction: str
    raw_probabilities: dict
    calibrated_probabilities: dict
    primary_risk_score: float
    confidence: str
    inference_ms: float
    model_version: str
    calibration_version: str | None = None
    demo: bool


class AlertOut(ORMModel):
    id: UUID
    child_id: UUID
    pseudonymous_id: str | None = None
    type: str
    severity: str
    status: str
    message: str
    trigger_value: dict | None = None
    created_at: datetime
    acknowledged_at: datetime | None = None


class AlertPatch(BaseModel):
    notes: str | None = None
    reason: str | None = None


class NoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=8000)
    visit_id: UUID | None = None


class FollowUpCreate(BaseModel):
    expected_date: date
    interval_days: int = 30
    responsible_user_id: UUID | None = None
    notes: str | None = None


class FollowUpPatch(BaseModel):
    expected_date: date | None = None
    status: str | None = None
    notes: str | None = None


class CounterfactualRequest(BaseModel):
    child_id: str
    visit_id: UUID
    trigger: str
    current_prediction: dict[str, Any] = Field(default_factory=dict)
    current_risk: float
    trajectory_summary: dict[str, Any] = Field(default_factory=dict)
    model_version: str


class Page(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int

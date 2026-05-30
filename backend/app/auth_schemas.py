from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1, max_length=255)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class OnboardingSubmitRequest(BaseModel):
    primary_goal: str
    secondary_goal: str | None = None
    equipment: str
    days_per_week: int = Field(ge=1, le=7)
    workout_duration_minutes: int = Field(ge=15, le=120)
    preferred_workout_time: str
    injuries_limitations: str | None = None
    fitness_level: str
    exercises_hate: str | None = None
    exercises_love: str | None = None


class ProfileUpdateRequest(BaseModel):
    name: str | None = None
    age: int | None = Field(default=None, ge=13, le=100)
    weight: float | None = Field(default=None, ge=30, le=300)
    avatar_letter: str | None = Field(default=None, min_length=1, max_length=1)
    primary_goal: str | None = None
    secondary_goal: str | None = None
    equipment: str | None = None
    days_per_week: int | None = Field(default=None, ge=1, le=7)
    workout_duration_minutes: int | None = Field(default=None, ge=15, le=120)
    preferred_workout_time: str | None = None
    injuries_limitations: str | None = None
    fitness_level: str | None = None
    exercises_hate: str | None = None
    exercises_love: str | None = None


class AthleteProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    age: int
    weight: float
    fitness_goals: str | None = None
    medical_history: str | None = None
    avatar_letter: str | None = None
    onboarding_completed: bool = False
    strava_onboarding_done: bool = False
    primary_goal: str | None = None
    secondary_goal: str | None = None
    equipment: str | None = None
    days_per_week: int | None = None
    workout_duration_minutes: int | None = None
    preferred_workout_time: str | None = None
    injuries_limitations: str | None = None
    fitness_level: str | None = None
    exercises_hate: str | None = None
    exercises_love: str | None = None


class UserResponse(BaseModel):
    id: int
    email: str
    profile: AthleteProfileResponse | None = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

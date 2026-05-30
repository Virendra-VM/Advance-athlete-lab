from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth_schemas import AthleteProfileResponse, UserResponse
from app.database import get_db
from app.models import AthleteProfile, User
from app.services.auth import decode_access_token

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


def build_user_response(user: User, db: Session) -> UserResponse:
    profile = None
    if user.athlete_profile_id:
        db_profile = (
            db.query(AthleteProfile)
            .filter(AthleteProfile.id == user.athlete_profile_id)
            .first()
        )
        if db_profile:
            profile = AthleteProfileResponse.model_validate(db_profile)

    return UserResponse(id=user.id, email=user.email, profile=profile)

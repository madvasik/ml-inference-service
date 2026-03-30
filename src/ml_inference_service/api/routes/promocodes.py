from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ml_inference_service.database import get_db
from ml_inference_service.deps import get_current_user, require_admin
from ml_inference_service.models.promocode import Promocode, PromocodeType
from ml_inference_service.models.user import User
from ml_inference_service.schemas.promocode import (
    PromocodeActivateRequest,
    PromocodeActivateResponse,
    PromocodeCreateRequest,
    PromocodeCreateResponse,
)
from ml_inference_service.services import promocode as promocode_service

router = APIRouter()


@router.post("/activate", response_model=PromocodeActivateResponse)
def activate(
    body: PromocodeActivateRequest,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
) -> PromocodeActivateResponse:
    try:
        msg, credits, discount = promocode_service.activate_promocode(
            db, user_id=current.id, code=body.code
        )
        db.commit()
    except promocode_service.PromocodeAlreadyUsedError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except promocode_service.PromocodeInvalidError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return PromocodeActivateResponse(
        message=msg,
        credits_granted=credits,
        discount_percent_next_topup=discount,
    )


@router.post("/admin", response_model=PromocodeCreateResponse, dependencies=[Depends(require_admin)])
def create_promocode(
    body: PromocodeCreateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> Promocode:
    kind = PromocodeType(body.kind)
    code_upper = body.code.strip().upper()
    existing = db.query(Promocode).filter(func.upper(Promocode.code) == code_upper).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Code already exists")
    row = Promocode(
        code=code_upper,
        kind=kind,
        value=body.value,
        expires_at=body.expires_at,
        max_activations=body.max_activations,
        activations_count=0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

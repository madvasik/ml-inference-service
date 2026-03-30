from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.billing import build_prediction_cost_snapshot, charge_prediction, get_balance, refund_prediction_if_debited
from backend.app.config import settings
from backend.app.db import get_db
from backend.app.loyalty import get_loyalty_snapshot
from backend.app.ml import validate_input_features
from backend.app.models import MLModel, Prediction, PredictionStatus, User
from backend.app.schemas import PredictionCreate, PredictionList, PredictionResponse, PredictionTaskResponse
from backend.app.security import get_current_user
from backend.app.worker import execute_prediction


router = APIRouter()


@router.post("", response_model=PredictionTaskResponse, status_code=status.HTTP_202_ACCEPTED)
def create_prediction(
    prediction_data: PredictionCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    model = (
        db.query(MLModel)
        .filter(MLModel.id == prediction_data.model_id, MLModel.owner_id == current_user.id)
        .first()
    )
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
    try:
        validate_input_features(prediction_data.input_data, model.feature_names)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    request.state.model_id = str(prediction_data.model_id)
    loyalty_snapshot = get_loyalty_snapshot(current_user)
    discount_amount, final_cost = build_prediction_cost_snapshot(
        settings.prediction_cost,
        loyalty_snapshot.discount_percent,
    )

    prediction = Prediction(
        user_id=current_user.id,
        model_id=prediction_data.model_id,
        input_data=prediction_data.input_data,
        status=PredictionStatus.PENDING,
        base_cost=settings.prediction_cost,
        discount_percent=loyalty_snapshot.discount_percent,
        discount_amount=discount_amount,
        credits_spent=final_cost,
    )
    db.add(prediction)
    db.flush()
    success, _ = charge_prediction(
        db,
        prediction,
        description=f"Prediction #{prediction.id} (queued)",
    )
    if not success:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient balance. Required: {final_cost}, Available: {get_balance(db, current_user.id)}",
        )
    db.commit()
    db.refresh(prediction)

    try:
        task = execute_prediction.delay(prediction_id=prediction.id)
        prediction.task_id = task.id
        db.commit()
        db.refresh(prediction)
    except Exception:
        prediction.status = PredictionStatus.FAILED
        prediction.failure_reason = "queue_unavailable"
        refund_prediction_if_debited(db, prediction, commit=False)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Prediction queue is unavailable. Please try again later.",
        )

    return PredictionTaskResponse(
        task_id=task.id,
        prediction_id=prediction.id,
        status="pending",
        message="Prediction task created. Use GET /predictions/{prediction_id} to check status.",
    )


@router.get("", response_model=PredictionList)
def list_predictions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    predictions = (
        db.query(Prediction)
        .filter(Prediction.user_id == current_user.id)
        .order_by(Prediction.created_at.desc())
        .all()
    )
    return PredictionList(predictions=predictions, total=len(predictions))


@router.get("/{prediction_id}", response_model=PredictionResponse)
def get_prediction(prediction_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prediction = (
        db.query(Prediction)
        .filter(Prediction.id == prediction_id, Prediction.user_id == current_user.id)
        .first()
    )
    if prediction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prediction not found")
    return prediction

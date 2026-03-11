from celery import Task
from sqlalchemy.orm import Session
from backend.app.tasks.celery_app import celery_app
from backend.app.database.session import SessionLocal
from backend.app.models.prediction import Prediction, PredictionStatus
from backend.app.models.ml_model import MLModel
from backend.app.services.model_loader import load_model
from backend.app.services.ml_service import predict
from backend.app.billing.service import deduct_credits
from backend.app.config import settings
from backend.app.monitoring.metrics import prediction_errors_total
import logging

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Базовый класс для задач с доступом к БД"""
    _db: Session = None

    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="predictions.execute_prediction",
    max_retries=3,
    default_retry_delay=60
)
def execute_prediction(self, prediction_id: int, model_id: int, user_id: int, input_data: dict):
    """
    Выполнение предсказания в фоновом режиме
    
    Args:
        prediction_id: ID предсказания в БД
        model_id: ID модели
        user_id: ID пользователя
        input_data: Входные данные для предсказания
    """
    db = self.db
    
    try:
        # Получаем предсказание
        prediction = db.query(Prediction).filter(Prediction.id == prediction_id).first()
        if not prediction:
            logger.error(f"Prediction {prediction_id} not found")
            return {"status": "failed", "error": "Prediction not found"}
        
        # Получаем модель
        model = db.query(MLModel).filter(MLModel.id == model_id).first()
        if not model:
            logger.error(f"Model {model_id} not found")
            prediction.status = PredictionStatus.FAILED
            db.commit()
            prediction_errors_total.labels(error_type="model_not_found").inc()
            return {"status": "failed", "error": "Model not found"}
        
        # Загружаем ML модель
        ml_model = load_model(model.file_path)
        
        # Выполняем предсказание
        result = predict(ml_model, input_data)
        
        # Списание кредитов (атомарно)
        if not deduct_credits(db, user_id, settings.prediction_cost, f"Prediction #{prediction_id}"):
            logger.error(f"Failed to deduct credits for prediction {prediction_id}")
            prediction.status = PredictionStatus.FAILED
            db.commit()
            prediction_errors_total.labels(error_type="insufficient_credits").inc()
            return {"status": "failed", "error": "Failed to deduct credits"}
        
        # Обновляем предсказание
        prediction.result = result
        prediction.status = PredictionStatus.COMPLETED
        prediction.credits_spent = settings.prediction_cost
        db.commit()
        
        logger.info(f"Prediction {prediction_id} completed successfully")
        return {
            "status": "completed",
            "prediction_id": prediction_id,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Error executing prediction {prediction_id}: {str(e)}", exc_info=True)
        
        # Обновляем метрики ошибок
        prediction_errors_total.labels(error_type="execution_error").inc()
        
        # Обновляем статус на FAILED
        try:
            prediction = db.query(Prediction).filter(Prediction.id == prediction_id).first()
            if prediction:
                prediction.status = PredictionStatus.FAILED
                db.commit()
        except Exception as commit_error:
            logger.error(f"Failed to update prediction status: {str(commit_error)}")
        
        # Повторяем задачу при определенных ошибках
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        
        return {"status": "failed", "error": str(e)}

from sqlalchemy.orm import Session
from backend.app.models.balance import Balance
from backend.app.models.transaction import Transaction, TransactionType
from backend.app.config import settings


def get_balance(db: Session, user_id: int) -> int:
    """Получение баланса пользователя"""
    balance = db.query(Balance).filter(Balance.user_id == user_id).first()
    if not balance:
        # Создаем баланс, если его нет
        balance = Balance(user_id=user_id, credits=0)
        db.add(balance)
        db.commit()
        db.refresh(balance)
    return balance.credits


def deduct_credits(db: Session, user_id: int, amount: int, description: str = None) -> bool:
    """Атомарное списание кредитов"""
    # Используем SELECT FOR UPDATE для блокировки строки
    balance = db.query(Balance).filter(Balance.user_id == user_id).with_for_update().first()
    
    if not balance:
        balance = Balance(user_id=user_id, credits=0)
        db.add(balance)
        db.flush()
    
    if balance.credits < amount:
        return False
    
    # Списание кредитов
    balance.credits -= amount
    
    # Создание транзакции
    transaction = Transaction(
        user_id=user_id,
        amount=amount,
        type=TransactionType.DEBIT,
        description=description or f"Prediction cost: {amount} credits"
    )
    db.add(transaction)
    db.commit()
    
    return True


def add_credits(db: Session, user_id: int, amount: int, description: str = None) -> None:
    """Пополнение баланса"""
    balance = db.query(Balance).filter(Balance.user_id == user_id).first()
    
    if not balance:
        balance = Balance(user_id=user_id, credits=0)
        db.add(balance)
        db.flush()
    
    balance.credits += amount
    
    # Создание транзакции
    transaction = Transaction(
        user_id=user_id,
        amount=amount,
        type=TransactionType.CREDIT,
        description=description or f"Top-up: {amount} credits"
    )
    db.add(transaction)
    db.commit()

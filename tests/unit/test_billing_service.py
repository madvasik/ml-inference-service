import pytest
from backend.app.billing.service import get_balance, deduct_credits, add_credits
from backend.app.models.balance import Balance
from backend.app.models.transaction import Transaction, TransactionType


def test_get_balance_existing(db_session, test_user):
    """Тест получения существующего баланса"""
    # Обновляем существующий баланс
    balance = db_session.query(Balance).filter(Balance.user_id == test_user.id).first()
    if balance:
        balance.credits = 500
    else:
        balance = Balance(user_id=test_user.id, credits=500)
        db_session.add(balance)
    db_session.commit()
    
    result = get_balance(db_session, test_user.id)
    assert result == 500


def test_get_balance_not_existing(db_session, test_user):
    """Тест получения баланса для пользователя без баланса"""
    # Удаляем баланс если существует
    balance = db_session.query(Balance).filter(Balance.user_id == test_user.id).first()
    if balance:
        db_session.delete(balance)
        db_session.commit()
    
    result = get_balance(db_session, test_user.id)
    assert result == 0
    
    # Проверяем, что баланс был создан
    balance = db_session.query(Balance).filter(Balance.user_id == test_user.id).first()
    assert balance is not None
    assert balance.credits == 0


def test_deduct_credits_success(db_session, test_user):
    """Тест успешного списания кредитов"""
    # Обновляем существующий баланс
    balance = db_session.query(Balance).filter(Balance.user_id == test_user.id).first()
    if balance:
        balance.credits = 1000
    else:
        balance = Balance(user_id=test_user.id, credits=1000)
        db_session.add(balance)
    db_session.commit()
    
    result = deduct_credits(db_session, test_user.id, 100, "Test deduction")
    
    assert result is True
    db_session.refresh(balance)
    assert balance.credits == 900
    
    # Проверяем, что транзакция создана
    transaction = db_session.query(Transaction).filter(
        Transaction.user_id == test_user.id,
        Transaction.type == TransactionType.DEBIT
    ).first()
    assert transaction is not None
    assert transaction.amount == 100


def test_deduct_credits_insufficient(db_session, test_user):
    """Тест списания при недостаточном балансе"""
    # Обновляем существующий баланс
    balance = db_session.query(Balance).filter(Balance.user_id == test_user.id).first()
    if balance:
        balance.credits = 50
    else:
        balance = Balance(user_id=test_user.id, credits=50)
        db_session.add(balance)
    db_session.commit()
    
    result = deduct_credits(db_session, test_user.id, 100, "Test deduction")
    
    assert result is False
    db_session.refresh(balance)
    assert balance.credits == 50  # Баланс не изменился


def test_deduct_credits_no_balance(db_session, test_user):
    """Тест списания для пользователя без баланса"""
    # Удаляем баланс если существует
    balance = db_session.query(Balance).filter(Balance.user_id == test_user.id).first()
    if balance:
        db_session.delete(balance)
        db_session.commit()
    
    result = deduct_credits(db_session, test_user.id, 100, "Test deduction")
    
    assert result is False
    
    # Проверяем, что баланс был создан с нулевым значением
    balance = db_session.query(Balance).filter(Balance.user_id == test_user.id).first()
    assert balance is not None
    assert balance.credits == 0


def test_add_credits_existing_balance(db_session, test_user):
    """Тест пополнения существующего баланса"""
    # Обновляем существующий баланс
    balance = db_session.query(Balance).filter(Balance.user_id == test_user.id).first()
    if balance:
        balance.credits = 500
    else:
        balance = Balance(user_id=test_user.id, credits=500)
        db_session.add(balance)
    db_session.commit()
    
    add_credits(db_session, test_user.id, 200, "Test top-up")
    
    db_session.refresh(balance)
    assert balance.credits == 700
    
    # Проверяем, что транзакция создана
    transaction = db_session.query(Transaction).filter(
        Transaction.user_id == test_user.id,
        Transaction.type == TransactionType.CREDIT
    ).first()
    assert transaction is not None
    assert transaction.amount == 200


def test_add_credits_no_balance(db_session, test_user):
    """Тест пополнения для пользователя без баланса"""
    # Удаляем баланс если существует
    balance = db_session.query(Balance).filter(Balance.user_id == test_user.id).first()
    if balance:
        db_session.delete(balance)
        db_session.commit()
    
    add_credits(db_session, test_user.id, 300, "Test top-up")
    
    # Проверяем, что баланс был создан
    balance = db_session.query(Balance).filter(Balance.user_id == test_user.id).first()
    assert balance is not None
    assert balance.credits == 300


def test_add_credits_default_description(db_session, test_user):
    """Тест пополнения с дефолтным описанием"""
    # Обновляем существующий баланс
    balance = db_session.query(Balance).filter(Balance.user_id == test_user.id).first()
    if balance:
        balance.credits = 100
    else:
        balance = Balance(user_id=test_user.id, credits=100)
        db_session.add(balance)
    db_session.commit()
    
    add_credits(db_session, test_user.id, 50)
    
    transaction = db_session.query(Transaction).filter(
        Transaction.user_id == test_user.id,
        Transaction.type == TransactionType.CREDIT
    ).first()
    assert transaction is not None
    assert "Top-up" in transaction.description


def test_deduct_credits_default_description(db_session, test_user):
    """Тест списания с дефолтным описанием"""
    # Обновляем существующий баланс
    balance = db_session.query(Balance).filter(Balance.user_id == test_user.id).first()
    if balance:
        balance.credits = 1000
    else:
        balance = Balance(user_id=test_user.id, credits=1000)
        db_session.add(balance)
    db_session.commit()
    
    deduct_credits(db_session, test_user.id, 50)
    
    transaction = db_session.query(Transaction).filter(
        Transaction.user_id == test_user.id,
        Transaction.type == TransactionType.DEBIT
    ).first()
    assert transaction is not None
    assert "Prediction cost" in transaction.description

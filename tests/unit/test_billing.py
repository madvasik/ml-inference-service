from unittest.mock import patch

import pytest

from backend.app.billing import charge_prediction, create_payment, get_balance
from backend.app.models import Balance, Payment, Prediction, PredictionStatus, Transaction, TransactionType
from tests.helpers import auth_headers


def test_payment_endpoint_adds_credits_and_transaction(client, access_token_for, test_user, db_session):
    headers = auth_headers(access_token_for(test_user))
    starting_balance = get_balance(db_session, test_user.id)

    response = client.post("/api/v1/billing/payments", headers=headers, json={"amount": 75})

    assert response.status_code == 200
    assert response.json()["credits"] == starting_balance + 75
    assert db_session.query(Payment).filter(Payment.user_id == test_user.id).count() == 1
    transaction = db_session.query(Transaction).filter(Transaction.user_id == test_user.id).one()
    assert transaction.type == TransactionType.CREDIT
    assert transaction.amount == 75


def test_create_payment_rolls_back_on_failure(db_session, test_user):
    with patch("backend.app.billing.add_credits", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError):
            create_payment(db_session, test_user.id, 20)

    assert db_session.query(Payment).filter(Payment.user_id == test_user.id).count() == 0
    assert db_session.query(Transaction).filter(Transaction.user_id == test_user.id).count() == 0
    assert get_balance(db_session, test_user.id) == 1000


def test_charge_prediction_is_idempotent(db_session, test_user, test_ml_model):
    prediction = Prediction(
        user_id=test_user.id,
        model_id=test_ml_model.id,
        input_data={"feature1": 1},
        status=PredictionStatus.PENDING,
        base_cost=10,
        discount_percent=0,
        discount_amount=0,
        credits_spent=10,
    )
    db_session.add(prediction)
    db_session.commit()
    db_session.refresh(prediction)

    first_success, first_transaction = charge_prediction(db_session, prediction)
    db_session.commit()
    second_success, second_transaction = charge_prediction(db_session, prediction)

    balance = db_session.query(Balance).filter(Balance.user_id == test_user.id).one()
    assert first_success is True
    assert second_success is True
    assert first_transaction.id == second_transaction.id
    assert balance.credits == 990
    assert db_session.query(Transaction).filter(Transaction.user_id == test_user.id).count() == 1


def test_billing_routes_validate_positive_amount(client, access_token_for, test_user):
    response = client.post(
        "/api/v1/billing/payments",
        headers=auth_headers(access_token_for(test_user)),
        json={"amount": -1},
    )

    assert response.status_code == 400

from backend.app.models import Payment, PaymentStatus, Prediction, PredictionStatus, Transaction, TransactionType
from tests.helpers import auth_headers


def test_admin_can_list_platform_entities(client, access_token_for, admin_user, test_user, test_ml_model, db_session):
    prediction = Prediction(
        user_id=test_user.id,
        model_id=test_ml_model.id,
        input_data={"feature1": 1},
        result={"prediction": 1},
        status=PredictionStatus.COMPLETED,
        base_cost=10,
        discount_percent=0,
        discount_amount=0,
        credits_spent=10,
    )
    payment = Payment(
        user_id=test_user.id,
        amount=50,
        provider="mock",
        status=PaymentStatus.CONFIRMED,
        external_id="mock:1",
    )
    transaction = Transaction(user_id=test_user.id, amount=50, type=TransactionType.CREDIT, payment=payment)
    db_session.add_all([prediction, payment, transaction])
    db_session.commit()

    headers = auth_headers(access_token_for(admin_user))

    users_response = client.get("/api/v1/admin/users", headers=headers)
    predictions_response = client.get("/api/v1/admin/predictions", headers=headers)
    payments_response = client.get("/api/v1/admin/payments", headers=headers)
    transactions_response = client.get("/api/v1/admin/transactions", headers=headers)

    assert users_response.status_code == 200
    assert any(item["email"] == test_user.email for item in users_response.json())
    assert predictions_response.json()["total"] == 1
    assert payments_response.json()["total"] == 1
    assert any(item["user_id"] == test_user.id and item["amount"] == 50 for item in transactions_response.json()["transactions"])


def test_admin_routes_require_admin_role(client, access_token_for, test_user):
    response = client.get("/api/v1/admin/users", headers=auth_headers(access_token_for(test_user)))

    assert response.status_code == 403

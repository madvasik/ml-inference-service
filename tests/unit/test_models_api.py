from unittest.mock import patch

import json
import os

from backend.app.models import MLModel, Prediction, PredictionStatus
from tests.helpers import auth_headers


def test_model_upload_list_get_and_delete(client, access_token_for, test_user, test_model_file, db_session):
    headers = auth_headers(access_token_for(test_user))

    with open(test_model_file, "rb") as model_file:
        upload = client.post(
            "/api/v1/models/upload",
            headers=headers,
            data={"model_name": "uploaded-model", "feature_names": json.dumps(["feature1", "feature2"])},
            files={"file": ("model.skops", model_file, "application/octet-stream")},
        )
    assert upload.status_code == 201
    payload = upload.json()
    model_id = payload["id"]
    file_path = db_session.get(MLModel, model_id).file_path
    assert os.path.exists(file_path)

    listing = client.get("/api/v1/models", headers=headers)
    detail = client.get(f"/api/v1/models/{model_id}", headers=headers)
    delete = client.delete(f"/api/v1/models/{model_id}", headers=headers)

    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert detail.status_code == 200
    assert detail.json()["model_name"] == "uploaded-model"
    assert "file_path" not in detail.json()
    assert delete.status_code == 204
    assert not os.path.exists(file_path)


def test_model_upload_rejects_invalid_extension(client, access_token_for, test_user):
    headers = auth_headers(access_token_for(test_user))

    response = client.post(
        "/api/v1/models/upload",
        headers=headers,
        data={"model_name": "bad-model"},
        files={"file": ("model.txt", b"not-a-model", "text/plain")},
    )

    assert response.status_code == 400


def test_model_upload_requires_feature_schema_for_nameless_models(client, access_token_for, test_user, test_model_file):
    headers = auth_headers(access_token_for(test_user))

    with open(test_model_file, "rb") as model_file:
        response = client.post(
            "/api/v1/models/upload",
            headers=headers,
            data={"model_name": "uploaded-model"},
            files={"file": ("model.skops", model_file, "application/octet-stream")},
        )

    assert response.status_code == 400
    assert "feature" in response.json()["detail"].lower()


def test_model_access_is_scoped_to_owner(client, access_token_for, test_user, admin_user, test_ml_model):
    response = client.get(
        f"/api/v1/models/{test_ml_model.id}",
        headers=auth_headers(access_token_for(admin_user)),
    )

    assert response.status_code == 404


def test_model_upload_hides_internal_errors(client, access_token_for, test_user, test_model_file):
    headers = auth_headers(access_token_for(test_user))

    with open(test_model_file, "rb") as model_file:
        with patch("backend.app.api.models.os.rename", side_effect=OSError("disk path leaked")):
            response = client.post(
                "/api/v1/models/upload",
                headers=headers,
                data={"model_name": "uploaded-model", "feature_names": json.dumps(["feature1", "feature2"])},
                files={"file": ("model.skops", model_file, "application/octet-stream")},
            )

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to upload model"}


def test_model_delete_rejects_models_with_predictions(client, access_token_for, test_user, test_ml_model, db_session):
    prediction = Prediction(
        user_id=test_user.id,
        model_id=test_ml_model.id,
        input_data={"feature1": 1.0},
        status=PredictionStatus.COMPLETED,
        result={"prediction": 1},
    )
    db_session.add(prediction)
    db_session.commit()

    response = client.delete(
        f"/api/v1/models/{test_ml_model.id}",
        headers=auth_headers(access_token_for(test_user)),
    )

    assert response.status_code == 409
    assert os.path.exists(test_ml_model.file_path)
    assert db_session.get(MLModel, test_ml_model.id) is not None


def test_model_delete_keeps_file_when_commit_fails(
    client,
    access_token_for,
    test_user,
    test_ml_model,
    db_session,
    monkeypatch,
):
    def broken_commit():
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(db_session, "commit", broken_commit)

    response = client.delete(
        f"/api/v1/models/{test_ml_model.id}",
        headers=auth_headers(access_token_for(test_user)),
    )

    assert response.status_code == 500
    assert os.path.exists(test_ml_model.file_path)
    assert db_session.get(MLModel, test_ml_model.id) is not None

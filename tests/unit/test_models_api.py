import os

from tests.helpers import auth_headers


def test_model_upload_list_get_and_delete(client, access_token_for, test_user, test_model_file):
    headers = auth_headers(access_token_for(test_user))

    with open(test_model_file, "rb") as model_file:
        upload = client.post(
            "/api/v1/models/upload",
            headers=headers,
            data={"model_name": "uploaded-model"},
            files={"file": ("model.pkl", model_file, "application/octet-stream")},
        )
    assert upload.status_code == 201
    payload = upload.json()
    model_id = payload["id"]
    file_path = payload["file_path"]
    assert os.path.exists(file_path)

    listing = client.get("/api/v1/models", headers=headers)
    detail = client.get(f"/api/v1/models/{model_id}", headers=headers)
    delete = client.delete(f"/api/v1/models/{model_id}", headers=headers)

    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert detail.status_code == 200
    assert detail.json()["model_name"] == "uploaded-model"
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


def test_model_access_is_scoped_to_owner(client, access_token_for, test_user, admin_user, test_ml_model):
    response = client.get(
        f"/api/v1/models/{test_ml_model.id}",
        headers=auth_headers(access_token_for(admin_user)),
    )

    assert response.status_code == 404


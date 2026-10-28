import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_registration_and_jwt_authentication():
    client = APIClient()
    registration = client.post(
        reverse("register"),
        {
            "username": "alex",
            "email": "alex@example.com",
            "password": "SecurePassphrase-42",
        },
        format="json",
    )
    assert registration.status_code == 201
    assert registration.data["username"] == "alex"
    assert get_user_model().objects.filter(username="alex").exists()

    token_response = client.post(
        reverse("token_obtain_pair"),
        {"username": "alex", "password": "SecurePassphrase-42"},
        format="json",
    )
    assert token_response.status_code == 200
    assert "access" in token_response.data

    refresh_response = client.post(
        reverse("token_refresh"),
        {"refresh": token_response.data["refresh"]},
        format="json",
    )
    assert refresh_response.status_code == 200
    assert "access" in refresh_response.data


@pytest.mark.django_db
def test_registration_validation_uses_standard_error_schema():
    response = APIClient().post(
        reverse("register"),
        {
            "username": "alex",
            "email": "alex@example.com",
            "password": "password",
        },
        format="json",
    )
    assert response.status_code == 400
    assert set(response.data) == {"error"}
    assert {"code", "message", "details"} <= set(response.data["error"])


@pytest.mark.django_db
def test_protected_catalog_requires_authentication():
    response = APIClient().get(reverse("event-list"))
    assert response.status_code == 401
    assert "error" in response.data

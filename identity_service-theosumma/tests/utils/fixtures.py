import pytest
from datetime import datetime, timedelta
from identity_service.schemas.user import UserCreate

@pytest.fixture
def user_create_data(random_email):
    return {
        "first_name": "Test",
        "last_name": "User",
        "email": random_email,
        "password": "securepassword123",
        "recaptcha_token": "test_token",
        "roles": ["SUBSCRIBER"]
    }

@pytest.fixture
def expired_token_fixture():
    from identity_service.services.auth import create_jwt_at_token
    from identity_service.schemas.auth import AccessTokenPayload
    expired_payload = AccessTokenPayload(
        user_id="3fa85f64-5717-4562-b3fc-2c963f66afa6"
    )
    return create_jwt_at_token(expired_payload)

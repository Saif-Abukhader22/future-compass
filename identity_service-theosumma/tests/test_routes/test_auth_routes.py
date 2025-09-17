import pytest
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from identity_service.schemas.auth import TokenData


class TestAuthRoutes:
    @pytest.mark.asyncio
    def test_register_and_login(self, test_client, random_email, db_session: AsyncSession):
        # Test registration
        register_data = {
            "first_name": "Test",
            "last_name": "User",
            "email": random_email,
            "password": "securepassword123",
            "recaptcha_token": "test_token",
            "roles": ["SUBSCRIBER"]
        }

        # Make request
        response = test_client.post("/account", json=register_data)

        # Assertions
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["email"] == random_email

        # Test login
        login_data = {
            "username": random_email,
            "password": "securepassword123"
        }
        response = test_client.post("/login", data=login_data)

        assert response.status_code == status.HTTP_200_OK
        assert "access_token" in response.json()

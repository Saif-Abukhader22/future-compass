import pytest
from fastapi import HTTPException
from identity_service.services.auth import (
    create_user,
    login_user,
    verify_recaptcha,
    check_verification_code_general
)
from identity_service.schemas.user import UserCreate


class TestAuthServices:
    @pytest.mark.asyncio
    async def test_user_creation(self, db_session, random_email):
        user_data = UserCreate(
            first_name="Test",
            last_name="User",
            email=random_email,
            password="securepassword123",
            recaptcha_token="test_token",
            roles=["SUBSCRIBER"]
        )

        # The db_session fixture now properly yields the session
        user = await create_user(user_data, db_session)
        assert user.email == random_email
        assert user.auth is not None

        # Verify password hashing
        from identity_service.services.auth import verify_hash_pass
        assert verify_hash_pass("securepassword123", user.auth.hashed_password)

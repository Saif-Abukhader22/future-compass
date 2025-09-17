import pytest
from datetime import datetime
from uuid import UUID
from pydantic import ValidationError
from identity_service.schemas.user import UserCreate, UserRead


class TestUserSchemas:
    def test_user_read_schema(self):
        valid_data = {
            "user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "created_at": datetime.now(),
            "updated_at": None,
            "roles": ["SUBSCRIBER"]
        }

        user = UserRead(**valid_data)
        assert isinstance(user.user_id, UUID)

        # Test invalid UUID
        with pytest.raises(ValidationError):
            invalid_data = valid_data.copy()
            invalid_data["user_id"] = "not-a-uuid"
            UserRead(**invalid_data)

from enum import Enum


class ErrorCode(str, Enum):
        LOGIN_INVALID_ERROR = "login_invalid_error"
        OLD_USER = "old_user"
        EMAIL_NOT_CONFIRM = "email_not_confirmed"
        INVALID_VERIFICATION_CODE = "invalid_verification_code"
        INVALID_SUBMISSION_ID = "invalid_submission_id"
        FAILED_TO_SEND_RESPONSE = "failed_to_send_response"
        EXPIRED_VERIFICATION_CODE = "expired_verification_code"
        RECAPTCHA_FAILED = "recaptcha_failed"
        PASSWORDS_DONT_MATCH = "passwords_dont_match"
        OLD_PASSWORD_INCORRECT = "old_password_incorrect"
        PASSWORD_CHANGE_ERROR = "password_change_error"
        UNEXPECTED_ERROR = "unexpected_error"
        ACCOUNT_LOCKED = "account_locked"
        ACCOUNT_LOCKED_MINUTES = "account_locked_minutes"

        EXIST_EMAIL = "email_already_registered"
        USER_NOT_FOUND = "user_not_found"
        FAILED_TO_SEND_EMAIL = "failed_to_send_email"
        FAILED_TO_Update_EMAIL = "failed_to_update_email"
        FAILED_TO_GET_COUNTRIES = "failed_to_get_countries"
        EMAIL_ERROR = "email_does_not_belong_to_account"
        LOGIN_INVALID_password_ERROR = "login_invalid_password_error"
        UNAU_PUBLIC_REGIS = "unauthorized_public_registration_in_development"
        NOT_ADMIN = "ADMIN_ONLY"

        ERROR_SYNCING_USER = "error_syncing_user"
        INVALID_JSON_RESPONSE_MICROSERVICE = "invalid_json_response_from_microservice"
        ERROR_SYNCING_USERS_MICROSERVICES = "error_syncing_users_with_microservices"
        INTERNAL_ERROR_SYNCING_USER_MICROSERVICES = "internal_error_syncing_user_with_microservices"






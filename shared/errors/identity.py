from enum import Enum


class IdentityErrors(str, Enum):
    INTERNAL_SERVER_ERROR = 'internal_server_error'
    UNEXPECTED_ERROR = 'unexpected_error'
    INVALID_AUTHORIZATION_HEADER = 'invalid_authorization_header'
    INVALID_CREDENTIALS = 'invalid_credentials'
    USER_NOT_FOUND = 'user_not_found'
    ACCESS_TOKEN_NOT_EXPIRED = 'access_token_not_expired'
    ACCESS_TOKEN_EXPIRED = 'access_token_expired'
    REFRESH_TOKEN_EXPIRED = 'refresh_token_expired'
    INVALID_REFRESH_TOKEN = 'invalid_refresh_token'
    INVALID_ACCESS_TOKEN = 'invalid_access_token'
    NO_REFRESH_TOKEN_PROVIDED = 'no_refresh_token_provided'
    ERROR_DECODING_TOKEN = "Error_decoding_token"

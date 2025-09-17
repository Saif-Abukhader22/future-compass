from enum import Enum


class NotificationCode(str, Enum):
    # General categories
    USER_NOT_FOUND = "user_not_found"
    NOTIFICATION_NOT_FOUND = "notification_not_found"
    FORBIDDEN = "user_does_not_have_permission_to_mark_notification_as_read"
    DEVICE_NOT_FOUND = "device_token_not_found"

    NOT_IMPLEMENTED = "not_implemented"
    TIMEOUT = "timeout"
    NO_RECURRING_NEED = "no_recurring_needed"



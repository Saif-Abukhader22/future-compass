from enum import Enum


class SubscriptionCode(str, Enum):
    # General categories
    USER_NOT_FOUND = "user_not_found"
    PLAN_NOT_FOUND = "plan_not_found"
    SUBSCRIPTION_NOT_FOUND = "subscription_not_found"
    INVALID_INPUT = "invalid_input"
    UNAUTHORIZED = "unauthorized"
    SERVER_ERROR = "server_error"
    PAYMENT_FAILED = "payment_failed"
    RESOURCE_CONFLICT = "resource_conflict"
    FORBIDDEN = "forbidden"
    NOT_IMPLEMENTED = "not_implemented"
    TIMEOUT = "timeout"
    NO_RECURRING_NEED = "no_recurring_needed"
    CARD_NOT_FOUND = "card_not_found"
    TRANSACTIONS_NOT_FOUND = "transactions_not_found"
    NO_CHANGE = "no_change"

    INVALID_PLAN_ID_FORMAT = "invalid_plan_id_format"
    NO_PLAN_FOUND_IN_SYS = "no_plan_found_in_system"
    NO_SUBSCRIPTIONS_FOUND_FOR_THE_USER = "no_subscriptions_found_for_the_user"
    FAILED_TO_CREATE_CHECKOUT_DUE_TO_EXTERNAL_API_ERROR = "failed_to_create_checkout_due_to_external_api_error"
    UNEXPECTED_ERROR_IN_PAYMENT_CHECKOUT = "unexpected_error_in_payment_checkout"
    FAILED_TO_COMMUNICATE_WITH_PAYMENT_SERVER = "failed_to_communicate_with_payment_server"
    CHECKOUT_RECORD_NOT_FOUND = "checkout_record_not_found"
    UNEXPECTED_ERROR_IN_PAYMENT_STATUS = "unexpected_error_in_payment_status"
    FAILED_TO_RETRIEVE_PLANS = "failed_to_retrieve_plans"
    FAILED_TO_RETRIEVE_PLAN = "failed_to_retrieve_plan"
    INVALID_USER_ID_FORMAT = "invalid_user_id_format"
    FAILED_TO_CANCEL_SUBS_DUE_TO_DATABASE_CONSTRAINT = "failed_to_cancel_subscription_due_to_database_constraint"
    UNEXPECTED_ERROR_CANCELLING_SUBS = "unexpected_error_cancelling_subscription"
    FAILED_TO_RETRIEVE_SUBS_HISTORY = "failed_to_retrieve_subscription_history"
    FAILED_TO_RETRIEVE_CURRENT_PLAN = "failed_to_retrieve_current_plan"
    FAILED_TO_RENEW_PAYMENT = "Failed_to_renew_payment"

    INVALID_CHECKOUT_ID = "invalid_checkout_id"
    PAYMENT_RECORD_NOT_FOUND = "payment_record_not_found"

    INTERNAL_SERVER_ERROR_UPDATING_SUBSCRIPTION = "internal_server_error_updating_subscription"
    HTTP_ERROR_UPDATING_SUBSCRIPTION = "http_error_updating_subscription"
    BILLING_INFORMATION_REQUIRED = "billing_information_required"
    CODE_USAGE_LIMIT_EXCEEDED = "code_usage_limit_exceeded"
    PAYMENT_PROCESSED_RECORD_SAVE_FAILED = "payment_processed_record_save_failed"
    INVALID_RESPONSE_FORMAT_CORE_SERVICE = "invalid_response_format_core_service"
    EMPTY_RESPONSE_RECEIVED_CORE_SERVICE = "empty_response_received_core_service"
    CHECKOUT_NOT_FOUND = "checkout_not_found"
    UNEXPECTED_ERROR_RECURRING_PAYMENT = "unexpected_error_recurring_payment"
    FAILED_TO_RETRIEVE_RECEIPTS = "failed_to_retrieve_receipts"
    ERROR_DECODING_TOKEN = "error_decoding_token"
    FAILED_TO_GENERATE_RECEIPT = "failed_to_generate_receipt"
    MISSING_REQUIRED_QUERY_PARAMETERS = "missing_required_query_parameters"














import json
from shared.errors.community import CommunityErrors
from shared.errors.core import CoreErrors
from shared.errors.identity import IdentityErrors
from shared.errors.bible import BibleCode
from shared.errors.notification import NotificationCode
from shared.errors.subscription import SubscriptionCode


def collect_error_codes(*enum_classes):
    error_dict = {}
    for enum_cls in enum_classes:
        for error in enum_cls:
            error_dict[error.value] = ""
    return error_dict


if __name__ == "__main__":
    all_errors = collect_error_codes(CommunityErrors, CoreErrors, IdentityErrors, BibleCode, NotificationCode,
                                     SubscriptionCode)

    with open("all_error_codes.json", "w", encoding="utf-8") as f:
        json.dump(all_errors, f, indent=4, ensure_ascii=False)

    print("JSON file created: all_error_codes.json")

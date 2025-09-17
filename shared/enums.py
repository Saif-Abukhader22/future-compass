import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class MicroServiceName(str, Enum):
    CORE_SERVICE = 'core-service'
    IDENTITY_SERVICE = 'identity-service'
    SUBSCRIPTION_SERVICE = 'subscription-service'
    COMMUNITY_SERVICE = 'community-service'
    DOC_CHATTING_SERVICE = 'doc-chatting-service'
    BIBLE_SERVICE = 'bible-service'
    ASSESSMENTS_SERVICE = 'assessments-service'
    NOTIFICATIONS_SERVICE = 'notifications-service'

    def snake(self) -> str:
        return self.name.lower()


class CloudFlareR2Buckets(Enum):
    PUBLIC = "public"
    PRIVATE = "private"


class CloudFlareFileSource(str, Enum):
    CHAT_IMAGE_UPLOAD = "chat-image-upload"
    USER_PROFILE = "user_profile"
    CHAT_PDF_UPLOAD = "chat-pdf-upload"


class PlatformSupportedLanguages(Enum):
    ENGLISH = 'ENGLISH'
    ARABIC = 'ARABIC'


class AgentDocumentProcessingStatus(Enum):
    """
    Steps:
    1. Uploading
    2. extracting text
    3. chunking text semantically
    4. embed and store each chunk in ES
    """
    NEW = 'NEW'
    UPLOADED = 'UPLOADED'
    FAILED = 'FAILED'
    EXTRACTING_TEXT = 'EXTRACTING_TEXT'
    PROCESSING= 'PROCESSING'
    CHUNKING_TEXT_SEMANTICALLY = 'CHUNKING_TEXT_SEMANTICALLY'
    EMBEDDING_AND_STORING_IN_ES = 'EMBEDDING_AND_STORING_IN_ES'
    COMPLETED = 'COMPLETED'
    EXTRACTING_TEXT_FAILED = 'EXTRACTING_TEXT_FAILED'
    CHUNKING_TEXT_SEMANTICALLY_FAILED = 'CHUNKING_TEXT_SEMANTICALLY_FAILED'
    EMBEDDING_AND_STORING_IN_ES_FAILED = 'EMBEDDING_AND_STORING_IN_ES_FAILED'


class UserGender(Enum):
    MALE = 'MALE'
    FEMALE = 'FEMALE'
    OTHER = 'OTHER'


class UserRole(Enum):
    SUBSCRIBER = "SUBSCRIBER"
    MODERATOR = "MODERATOR"
    TESTER = "TESTER"
    ADMIN = "ADMIN"
    CONTENT_MANAGER= "CONTENT_MANAGER"
    TEAM_MEMBER = "TEAM_MEMBER"



class OpenAIModelSlugEnum(str, Enum):
    GPT_5_CHAT = "ggpt-5-chat-latest"
    GPT_4_1 = "gpt-4.1"
    GPT_4_1_MINI = "gpt-4.1-mini"
    GPT_4_1_NANO = "gpt-4.1-nano"
    GPT_4O = "gpt-4o"
    GPT_4O_MINI = "gpt-4o-mini"
    TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small"
    TEXT_EMBEDDING_3_LARGE = "text-embedding-3-large"
    WHISPER_1 = "whisper-1"


class MongoDBChatMessageType(Enum):
    text = 'text'
    image = 'image'
    audio = 'audio'
    video = 'video'
    document = 'document'


class BibleVersionModel(BaseModel):
    version: str
    full_name: str
    version_language: str


class BibleVersionEnum(Enum):
    AVD = BibleVersionModel(version="avd", full_name="Arabic Van Dyke", version_language="Arabic")
    CAV = BibleVersionModel(version="cav", full_name="Catholic Arabic Version", version_language="Arabic")
    CEB = BibleVersionModel(version="ceb", full_name="Common English Bible", version_language="English")
    ESV = BibleVersionModel(version="esv", full_name="English Standard Version", version_language="English")
    NIV = BibleVersionModel(version="niv", full_name="New International Version", version_language="English")
    KJV = BibleVersionModel(version="kjv", full_name="King James Version", version_language="English")

    """
    Usage Example:
        # Get Enum member
        enum_member = BibleVersionEnum.from_code("esv")
        print(enum_member.name)  # ESV
        
        # Get Pydantic model directly
        model = BibleVersionEnum.model_from_code("esv")
        print(model.full_name)  # English Standard Version
    """

    @classmethod
    def from_code(cls, version_code: str) -> Optional["BibleVersionEnum"]:
        """Return the enum member given a version short name, or None if not found."""
        version_code = version_code.lower()
        for member in cls:
            if member.value.version == version_code:
                return member
        return None

    @classmethod
    def model_from_code(cls, version_code: str) -> Optional[BibleVersionModel]:
        """Return the Pydantic model (value) for a given version code."""
        member = cls.from_code(version_code)
        return member.value if member else None


class SubscriptionPlanEnum(Enum):
    MONTHLY = "MONTHLY"
    ANNUAL = "ANNUAL"


class ChattingTools(Enum):
    SEARCH_DOCUMENT = 'SEARCH_DOCUMENT'
    EXPLAIN_IN_DOCUMENT = 'EXPLAIN_IN_DOCUMENT'
    SEARCH_INTERNET = 'SEARCH_INTERNET'

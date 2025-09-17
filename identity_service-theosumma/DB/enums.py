from enum import Enum


class AgentStatus(Enum):
    ACTIVE = 'ACTIVE'  # available for use
    INACTIVE = 'INACTIVE'  # not available for use and should be removed from the API
    UNDER_MAINTENANCE = 'UNDER_MAINTENANCE'  # not available for use but should be available in the API for future use


class StaticPromptType(Enum):
    GENERAL_INTRO = 'GENERAL_INTRO'
    GENERAL_OUTRO = 'GENERAL_OUTRO'
    TOPIC_DIVINITY_OF_CHRIST = 'TOPIC_DIVINITY_OF_CHRIST'
    TOPIC_HUMANITY_AND_TOTAL_DEPRAVITY = 'TOPIC_HUMANITY_AND_TOTAL_DEPRAVITY'
    TOPIC_INCARNATION_DOCTRINE = 'TOPIC_INCARNATION_DOCTRINE'
    TOPIC_ISLAM = 'TOPIC_ISLAM'
    TOPIC_LGBTQ = 'TOPIC_LGBTQ'
    TOPIC_SALVATION = 'TOPIC_SALVATION'
    TOPIC_SCIENCE_SCIENTISM_AND_CHRISTIAN_FAITH = 'TOPIC_SCIENCE_SCIENTISM_AND_CHRISTIAN_FAITH'
    TOPIC_ORIGIN_AND_INSPIRATION_OF_THE_BIBLE = 'TOPIC_ORIGIN_AND_INSPIRATION_OF_THE_BIBLE'
    TOPIC_THEOLOGY_ANTHROPOLOGY_AND_APOLOGY = 'TOPIC_THEOLOGY_ANTHROPOLOGY_AND_APOLOGY'
    TOPIC_THEORIES_OF_SALVATION_ATONMENT = 'TOPIC_THEORIES_OF_SALVATION_ATONMENT'
    TOPIC_TRINITY_AND_TRINITARIANISM_DOCTRINE = 'TOPIC_TRINITY_AND_TRINITARIANISM_DOCTRINE'
    TOPIC_TRUINE_GOD_IS_ONE_AND_SPIRIT = 'TOPIC_TRUINE_GOD_IS_ONE_AND_SPIRIT'


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


class AuthProvider(Enum):
    LOCAL = "LOCAL"
    GOOGLE = "GOOGLE"
    FACEBOOK = "FACEBOOK"
    APPLE = "APPLE"

class SystemAITasks(str, Enum):
    CHECK_PROMPT_SECURITY = 'check_prompt_security'
    SUMMARIZE_TEXT = 'summarize_text'
    SELECT_PROMPT_TOPICS = 'select_prompt_topics'
    GENERATE_TITLE = 'generate_title'
    INTERNAL_DATA_PROCESSING = 'internal_data_processing'
    TRANSLATE_TEXT = 'translate_text'
    AGENT_ROUTER = 'agent_router'
    RAG_QUERY_GENERATOR = 'rag_query_generator'


class OpenAIModelSlugEnum(str, Enum):
    GPT_4O = "gpt-4o"
    GPT_4O_MINI = "gpt-4o-mini"
    TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small"
    TEXT_EMBEDDING_3_LARGE = "text-embedding-3-large"
    WHISPER_1 = "whisper-1"


class TheoSummaModelSlugEnum(str, Enum):
    THEOSUMMA_REGULAR = 'THEOSUMMA_REGULAR'
    THEOSUMMA_EXPERT = 'THEOSUMMA_EXPERT'


class TheoSummaModelCapabilities(str, Enum):
    TEXT_GENERATION = 'TEXT_GENERATION'  # the model has the ability to generate text
    DOCUMENT_DISCUSSION = 'DOCUMENT_DISCUSSION'  # the model has the ability to collect RAG data
    COMMUNITY_DISCUSSION_CREATION = 'COMMUNITY_DISCUSSION_CREATION'  # Discussion prompt should be added to the model collector
    COMMUNITY_REPLIES = 'COMMUNITY_REPLIES'  # reply prompt should be added to the model collector
    PERSONALITY_ASSESSMENT = 'PERSONALITY_ASSESSMENT'  # don't know yet
    WORLD_VIEW_ASSESSMENT = 'WORLD_VIEW_ASSESSMENT'  # don't know yet
    BIBLICAL_FIGURE_DISCUSSION = 'BIBLICAL_FIGURE_DISCUSSION'  # don't know yet
    BIBLE_VERSES_RETRIEVAL = 'BIBLE_VERSES_RETRIEVAL'  # the model's answer should go through bible verse refiner to collect the exact bible verses and then embed them to be replace the mentioned bible verses.
    BIBLICAL_INTERPRETATION_AND_TRANSLATION = 'BIBLICAL_INTERPRETATION_AND_TRANSLATION'  # don't know yet


class PlatformFeature(str, Enum):
    SPEECH_TO_TEXT = "SPEECH_TO_TEXT"
    PDF_ANALYSIS = "PDF_ANALYSIS"
    IMAGE_RECOGNITION = "IMAGE_RECOGNITION"


class PlatformPlans(str, Enum):
    FREE = 'FREE'
    STANDARD = 'STANDARD'
    PRO = 'PRO'


class AgentType(Enum):
    """
    Each agent type is responsible for defining scope of work
    """
    GENERAL_DISCUSSION_ROUTER = "GENERAL_DISCUSSION_ROUTER"
    """
    Agents that are responsible for direct interaction with collectors. The collectors highly depend on them to 
    directly collect the answers. Example: Catholic AI Agent that is responsible about direct answers about Catholicism
    using its knowledge base and training data.
    """
    AREA_OF_KNOWLEDGE = "AREA_OF_KNOWLEDGE"  # (_EXPERT)
    """
    Agents that serve as knowledge cluster. Used by routers to retrieve information about different domains.
    Example: divinity_of_christ agent that is responsible about divinity of Christ opinion using only its training data.
    """
    TOPIC_EXPERT = "TOPIC_EXPERT"
    BIBLICAL_CHARACTER = "BIBLICAL_CHARACTER"
    PDF_DISCUSSION = "PDF_DISCUSSION"
    BIBLE_DISCUSSION = "BIBLE_DISCUSSION"
    PERSONALITY_ASSESSMENT = "PERSONALITY_ASSESSMENT"
    WORLDS_VIEW_ASSESSMENT = "WORLDS_VIEW_ASSESSMENT"
    COMMUNITY_POST = "COMMUNITY_POST"
    COMMUNITY_REPLIES = "COMMUNITY_REPLIES"
    LIVE_AGENT = "LIVE_AGENT"
    AUDIO_TRANSCRIPTION = "AUDIO_TRANSCRIPTION"
    COLLECTOR = "COLLECTOR"
    TRANSLATOR = "TRANSLATOR"
    QUERY_GENERATOR = "QUERY_GENERATOR"  # Refine and enhance user question.
    BIBLE_VERSE_RETRIEVER = "BIBLE_VERSE_RETRIEVER"  # Extract Bible verses from a given text

    def capabilities(self):
        mapping = {
            AgentType.GENERAL_DISCUSSION_ROUTER: [
                TheoSummaModelCapabilities.TEXT_GENERATION,
                TheoSummaModelCapabilities.DOCUMENT_DISCUSSION,
                TheoSummaModelCapabilities.BIBLE_VERSES_RETRIEVAL
            ],
            AgentType.AREA_OF_KNOWLEDGE: [
                TheoSummaModelCapabilities.TEXT_GENERATION,
                TheoSummaModelCapabilities.DOCUMENT_DISCUSSION,
                TheoSummaModelCapabilities.BIBLE_VERSES_RETRIEVAL
            ],
            AgentType.BIBLICAL_CHARACTER: [
                TheoSummaModelCapabilities.BIBLICAL_FIGURE_DISCUSSION,
                TheoSummaModelCapabilities.TEXT_GENERATION,
                TheoSummaModelCapabilities.DOCUMENT_DISCUSSION,
                TheoSummaModelCapabilities.BIBLE_VERSES_RETRIEVAL
            ],
            AgentType.PDF_DISCUSSION: [
                TheoSummaModelCapabilities.BIBLE_VERSES_RETRIEVAL,
                TheoSummaModelCapabilities.DOCUMENT_DISCUSSION,
                TheoSummaModelCapabilities.TEXT_GENERATION
            ],
            AgentType.BIBLE_DISCUSSION: [
                TheoSummaModelCapabilities.BIBLE_VERSES_RETRIEVAL,
                TheoSummaModelCapabilities.TEXT_GENERATION,
                TheoSummaModelCapabilities.DOCUMENT_DISCUSSION,
                TheoSummaModelCapabilities.BIBLICAL_INTERPRETATION_AND_TRANSLATION
            ],
            AgentType.PERSONALITY_ASSESSMENT: [
                TheoSummaModelCapabilities.PERSONALITY_ASSESSMENT,
                TheoSummaModelCapabilities.TEXT_GENERATION
            ],
            AgentType.WORLDS_VIEW_ASSESSMENT: [
                TheoSummaModelCapabilities.WORLD_VIEW_ASSESSMENT,
                TheoSummaModelCapabilities.TEXT_GENERATION
            ],
            AgentType.COMMUNITY_POST: [
                TheoSummaModelCapabilities.BIBLE_VERSES_RETRIEVAL,
                TheoSummaModelCapabilities.COMMUNITY_DISCUSSION_CREATION,
                TheoSummaModelCapabilities.TEXT_GENERATION
            ],
            AgentType.COMMUNITY_REPLIES: [
                TheoSummaModelCapabilities.BIBLE_VERSES_RETRIEVAL,
                TheoSummaModelCapabilities.COMMUNITY_REPLIES,
                TheoSummaModelCapabilities.TEXT_GENERATION
            ],
            AgentType.LIVE_AGENT: [
                TheoSummaModelCapabilities.TEXT_GENERATION,
                TheoSummaModelCapabilities.DOCUMENT_DISCUSSION
            ],
            AgentType.AUDIO_TRANSCRIPTION: [
                TheoSummaModelCapabilities.TEXT_GENERATION
            ],
        }
        return mapping.get(self, [])

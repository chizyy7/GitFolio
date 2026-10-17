"""
Pydantic schema registry.

Import from ``app.schemas`` for convenience::

    from app.schemas import PushRequest, RepoRead
"""

from app.schemas.ai import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    Citation,
    IndexStatus,
    ReviewResponse,
    SearchHit,
    SearchRequest,
    SearchResponse,
)
from app.schemas.auth import AuthResponse, Token, TokenPayload, UserLogin, UserRegister
from app.schemas.commit import (
    ActivityPoint,
    AIReviewRead,
    AuthorRead,
    CommitDetail,
    CommitListResponse,
    CommitRead,
    DashboardResponse,
    HeatmapDay,
    HeatmapResponse,
    LanguageStat,
    StreakStats,
)
from app.schemas.repository import (
    FileContent,
    FileNode,
    FileRead,
    PushFile,
    PushFileResult,
    PushRequest,
    PushResponse,
    RepoBase,
    RepoCreate,
    RepoDetail,
    RepoRead,
    RepoUpdate,
)
from app.schemas.skill import AISkillProfile, SkillProfileResponse, UserSkillRead
from app.schemas.user import UserCreate, UserMe, UserProfile, UserRead, UserUpdate

__all__ = [
    "AISkillProfile",
    "AIReviewRead",
    "ActivityPoint",
    "AuthResponse",
    "AuthorRead",
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "Citation",
    "CommitDetail",
    "CommitListResponse",
    "CommitRead",
    "DashboardResponse",
    "FileContent",
    "FileNode",
    "FileRead",
    "HeatmapDay",
    "HeatmapResponse",
    "IndexStatus",
    "LanguageStat",
    "PushFile",
    "PushFileResult",
    "PushRequest",
    "PushResponse",
    "RepoBase",
    "RepoCreate",
    "RepoDetail",
    "RepoRead",
    "RepoUpdate",
    "ReviewResponse",
    "SearchHit",
    "SearchRequest",
    "SearchResponse",
    "SkillProfileResponse",
    "StreakStats",
    "Token",
    "TokenPayload",
    "UserCreate",
    "UserLogin",
    "UserMe",
    "UserProfile",
    "UserRead",
    "UserSkillRead",
    "UserUpdate",
]

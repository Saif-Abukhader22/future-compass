from enum import Enum


class CommunityErrors(str, Enum):
    UNEXPECTED_ERROR = 'unexpected_error'
    INVALID_REQUEST = 'invalid_request'
    USER_NOT_FOUND = 'user_not_found'
    POST_NOT_FOUND = 'post_not_found'
    COMMENT_NOT_FOUND = 'comment_not_found'
    REPLY_NOT_FOUND = 'reply_not_found'
    UNAUTHORIZED_POST_ACCESS = 'unauthorized_post_access'
    UNAUTHORIZED_COMMENT_ACCESS = 'unauthorized_comment_access'
    UNAUTHORIZED_REPLY_ACCESS = 'unauthorized_reply_access'
    UNAUTHORIZED_USER_FOLLOW_ACCESS = 'unauthorized_user_follow_access'
    UNAUTHORIZED_USER_UNFOLLOW_ACCESS = 'unauthorized_user_unfollow_access'
    UNAUTHORIZED_USER_FOLLOW_REQUEST_ACCESS = 'unauthorized_user_follow_request_access'
    CANNOT_INVITE_SELF = 'cannot_invite_self'
    INVITATION_NOT_FOUND = 'invitation_not_found'
    INVITATION_ALREADY_EXISTS = 'invitation_already_exists'
    INVALID_INVITATION_TOKEN = 'invalid_invitation_token'
    UNAUTHORIZED_INVITATION_ACCEPTANCE = 'unauthorized_invitation_acceptance'
    USER_DELETED = 'user_deleted'
    CANNOT_FOLLOW_SELF = 'cannot_follow_self'
    CANNOT_UNFOLLOW_SELF = 'cannot_unfollow_self'
    NOT_FOLLOWING_USER = 'not_following_user'
    CANNOT_REMOVE_SELF = 'cannot_remove_self'
    CANNOT_REMOVE_CREATOR = 'cannot_remove_creator'
    CANNOT_REMOVE_INVITED_USER = 'cannot_remove_invited_user'
    CANNOT_REMOVE_FOLLOWING_USER = 'cannot_remove_following_user'
    INVALID_FOLLOWER_USER = "Invalid_follower_user"
    INVALID_FOLLOWING_USER = "Invalid_following_user"
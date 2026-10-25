import enum


class UserRole(enum.StrEnum):
    member = "member"
    admin = "admin"
    editor = "editor"
    author = "author"


class ContentType(enum.StrEnum):
    music = "music"
    gallery = "gallery"
    community = "community"
    homepage = "homepage"
    video = "video"


class MusicProvider(enum.StrEnum):
    soundcloud = "soundcloud"
    youtube = "youtube"
    vimeo = "vimeo"


class ContentStatus(enum.StrEnum):
    draft = "draft"
    published = "published"
    archived = "archived"


class ReactionType(enum.StrEnum):
    """Cảm xúc kiểu Facebook cho bài viết cộng đồng."""

    like = "like"
    love = "love"
    haha = "haha"
    wow = "wow"
    sad = "sad"
    angry = "angry"

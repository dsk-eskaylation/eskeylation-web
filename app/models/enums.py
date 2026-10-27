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


class AlbumKind(enum.StrEnum):
    album = "album"
    mixtape = "mixtape"
    ep = "ep"
    # Curated groupings that were never released as one record (sessions, guest verses)
    collection = "collection"


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

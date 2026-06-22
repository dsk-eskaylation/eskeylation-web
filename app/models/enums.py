import enum


class UserRole(enum.StrEnum):
    admin = "admin"
    editor = "editor"
    author = "author"


class ContentType(enum.StrEnum):
    music = "music"
    gallery = "gallery"
    community = "community"
    homepage = "homepage"


class ContentStatus(enum.StrEnum):
    draft = "draft"
    published = "published"
    archived = "archived"

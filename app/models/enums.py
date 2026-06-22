import enum


class UserRole(str, enum.Enum):
    admin = "admin"
    editor = "editor"
    author = "author"


class ContentType(str, enum.Enum):
    music = "music"
    gallery = "gallery"
    community = "community"
    homepage = "homepage"


class ContentStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    archived = "archived"

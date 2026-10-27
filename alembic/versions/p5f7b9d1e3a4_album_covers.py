"""Album covers: official art where it exists, otherwise a photo from the archive.

Only fills albums whose cover is still empty, so covers set in the CMS are kept.
"""

from alembic import op
import sqlalchemy as sa

revision = "p5f7b9d1e3a4"
down_revision = "o4e6a8c0d2f3"
branch_labels = None
depends_on = None

# DSK Kollek: Spotify release art. TTNMP Vol. 1-4: the official video thumbnails, which
# carry the square cover centred. The rest have no released cover; they use photos from
# the site's own gallery (S3/CloudFront).
COVERS = [
    ('waking-life', 'https://d2nlc4lzcofrv0.cloudfront.net/cms/drive/18kxoc4Y2sqsmsdpy9yVGub5I-NEUvLnq/display.webp'),
    ('saigon-smoking-weed', 'https://d2nlc4lzcofrv0.cloudfront.net/cms/drive/1GdIg7boxI8GNJ7FZdOHFnToqv0xUN9Vv/display.webp'),
    ('ttnmp-vol-1', 'https://i.ytimg.com/vi/s7ef8-nMlsY/maxresdefault.jpg'),
    ('ttnmp-vol-2', 'https://i.ytimg.com/vi/qlOuWYzcKEE/maxresdefault.jpg'),
    ('ttnmp-vol-3', 'https://i.ytimg.com/vi/XaL2CgZokVU/maxresdefault.jpg'),
    ('ttnmp-vol-4', 'https://i.ytimg.com/vi/1FAYFEJGRg8/maxresdefault.jpg'),
    ('dsk-kollek', 'https://i.scdn.co/image/ab67616d0000b273ae4fa53671abf55bb3d73185'),
    ('nhung-ngay-o-kong', 'https://d2nlc4lzcofrv0.cloudfront.net/cms/drive/1FfS_nH8EQEqNabv5GU87-wkZsf5TTWMo/display.webp'),
    ('prod-taiheo', 'https://d2nlc4lzcofrv0.cloudfront.net/cms/drive/1b8BeSaM-HdxtBmK3uiN4DX_R3OasJmxr/display.webp'),
    ('rap-elite-cypher', 'https://d2nlc4lzcofrv0.cloudfront.net/cms/drive/1KMIb3dhzcwpPqrkxOJNSgmZYymDfqrqb/display.webp'),
    ('diss-tracks', 'https://d2nlc4lzcofrv0.cloudfront.net/cms/drive/1AX7jjLv-0wr9XEvATkoTHI0XxrljGZUA/display.webp'),
    ('ket-hop', 'https://d2nlc4lzcofrv0.cloudfront.net/cms/drive/1J7ZITNUcoHxMqX7noK8kxZBpBcHX2dsJ/display.webp'),
    ('demo-freestyle', 'https://d2nlc4lzcofrv0.cloudfront.net/cms/drive/1BSP600flNuRSSuahqqBAmazSAQrDVjS8/display.webp'),
]


def upgrade():
    op.get_bind().execute(
        sa.text(
            "UPDATE albums SET cover_url = :url, updated_at = now() "
            "WHERE slug = :slug AND cover_url IS NULL"
        ),
        [dict(slug=s, url=u) for s, u in COVERS],
    )


def downgrade():
    op.get_bind().execute(
        sa.text(
            "UPDATE albums SET cover_url = NULL WHERE slug = :slug AND cover_url = :url"
        ),
        [dict(slug=s, url=u) for s, u in COVERS],
    )

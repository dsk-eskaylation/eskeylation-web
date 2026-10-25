"""Seed music albums from the archive's own tags and verified tracklists.

Tracks are matched by slug; only unassigned tracks and untouched artist credits are
changed, so re-running or running after CMS edits never overwrites manual work.
"""

from alembic import op
import sqlalchemy as sa

revision = "o4e6a8c0d2f3"
down_revision = "n3d5f7b9c1e2"
branch_labels = None
depends_on = None

# (slug, title, kind, year, position)
ALBUMS = [
    ('waking-life', 'Waking Life', 'mixtape', 2009, 10),
    ('saigon-smoking-weed', 'Saigon Smoking Weed', 'mixtape', 2012, 20),
    ('ttnmp-vol-1', 'Tuyển Tập Nhạc Miễn Phí Vol. 1', 'mixtape', 2018, 30),
    ('ttnmp-vol-2', 'Tuyển Tập Nhạc Miễn Phí Vol. 2', 'mixtape', 2018, 40),
    ('ttnmp-vol-3', 'Tuyển Tập Nhạc Miễn Phí Vol. 3', 'mixtape', 2019, 50),
    ('ttnmp-vol-4', 'Tuyển Tập Nhạc Miễn Phí Vol. 4', 'mixtape', 2021, 60),
    ('dsk-kollek', 'Die Sonnen Kinder – DSK Kollek', 'ep', 2021, 70),
    ('nhung-ngay-o-kong', 'Những Ngày Ở Kong', 'collection', 2017, 80),
    ('prod-taiheo', 'Prod. TaiHeo', 'collection', 2021, 90),
    ('rap-elite-cypher', 'Rap Elite Cypher', 'collection', None, 100),
    ('diss-tracks', 'Diss Tracks', 'collection', None, 110),
    ('ket-hop', 'Kết Hợp & Góp Giọng', 'collection', None, 120),
    ('demo-freestyle', 'Demo & Freestyle', 'collection', None, 130),
]

# (content slug, album slug, track_no or None when the release has no order)
TRACKS = [
    ('chien-binh-demo-7f75c2090dbc', 'demo-freestyle', None),
    ('chua-thuoc-lam-demo-a3becdfb1e02', 'demo-freestyle', None),
    ('demo-thu-n-1-voi-1e6a095c414', 'demo-freestyle', None),
    ('draft-339c48b19911', 'demo-freestyle', None),
    ('dsk-battle-c3fa55ddc2e1', 'demo-freestyle', None),
    ('dsk-freestyle-1-9b508fee1760', 'demo-freestyle', None),
    ('dsk-freestyle-2-20a0bae4c19a', 'demo-freestyle', None),
    ('goddog-bebb22c491e9', 'demo-freestyle', None),
    ('japansong-fun-demo-5b21f9481fb5', 'demo-freestyle', None),
    ('ngay-test-c144fafe3ffb', 'demo-freestyle', None),
    ('nho-bang-demo-a21e828d23fb', 'demo-freestyle', None),
    ('quintska-test-rap-b1b96869d05a', 'demo-freestyle', None),
    ('rap-log-mixed-f1437a64d141', 'demo-freestyle', None),
    ('tam-goi-la-doi-de-mo-de-72e875522d21', 'demo-freestyle', None),
    ('unrelease-fun-verse-on-parlee-beat-at-munich-374aa6dc977', 'demo-freestyle', None),
    ('30-phut-cho-rap-viet-1-2008-d65e2757453e', 'diss-tracks', None),
    ('30-phut-cho-rap-viet-2-2009-28fd8a92d038', 'diss-tracks', None),
    ('badabingbing-264eaaa41746', 'diss-tracks', None),
    ('con-tot-56c9333e0522', 'diss-tracks', None),
    ('tan-xac-2-de3ab049fa8', 'diss-tracks', None),
    ('tan-xac-vd-diss-975b16f30837', 'diss-tracks', None),
    ('lon-roi-e0537d2f10aa', 'dsk-kollek', 1),
    ('chua-bao-gio-f69c6983c802', 'dsk-kollek', 2),
    ('dieu-thuoc-cuoi-ffe49759e798', 'dsk-kollek', 3),
    ('bad-bois-3fab31103f30', 'ket-hop', None),
    ('bai-hat-chua-dat-ten-7f9f849653e9', 'ket-hop', None),
    ('bat-hanh-148655dc581', 'ket-hop', None),
    ('bed-room-cypher-caae0291eeb7', 'ket-hop', None),
    ('binh-tinh-59f489914ceb', 'ket-hop', None),
    ('binh-tinh-c7f27d3dfe7f', 'ket-hop', None),
    ('cuoc-doi-no-3910e98dc450', 'ket-hop', None),
    ('cuoc-doi-no-b8f710f7d9d0', 'ket-hop', None),
    ('di-nhan-ad6623941b3b', 'ket-hop', None),
    ('dmm-9556418ca46b', 'ket-hop', None),
    ('doi-bo-47a5b30fe481', 'ket-hop', None),
    ('fake-g-2336890c4518', 'ket-hop', None),
    ('friends-till-we-die-bcb08d4f819f', 'ket-hop', None),
    ('ghetto-genius-4f1c86057175', 'ket-hop', None),
    ('ghetto-genius-83033e0f5c', 'ket-hop', None),
    ('high-again-7f7239d67ecd', 'ket-hop', None),
    ('high-again-fbc5cba0b2fa', 'ket-hop', None),
    ('imagine-28b0a3007f75', 'ket-hop', None),
    ('internet-gangsta-7de3baf60e96', 'ket-hop', None),
    ('juz-chill-8022092f12eb', 'ket-hop', None),
    ('khong-bao-gio-c9cf4985ffb', 'ket-hop', None),
    ('lies-e5ccfe0d3812', 'ket-hop', None),
    ('may-thang-khua-71ba1e6a147c', 'ket-hop', None),
    ('may-thang-khua-9645527f4965', 'ket-hop', None),
    ('mua-2-5b1726546b74', 'ket-hop', None),
    ('nang-2-6643eddc5803', 'ket-hop', None),
    ('nhac-dem-a52f57dd2923', 'ket-hop', None),
    ('nho-em-921168e96696', 'ket-hop', None),
    ('rapper-brother-hood-a52616c749dd', 'ket-hop', None),
    ('sd-anthem-937f3c576d9a', 'ket-hop', None),
    ('so-high-so-fly-8af365973490', 'ket-hop', None),
    ('soul-a96d28cd7d88', 'ket-hop', None),
    ('tai-vi-sao-tao-nong-8c7bd923a58e', 'ket-hop', None),
    ('tan-ka-ganja-396968a47cd5', 'ket-hop', None),
    ('the-he-tao-ef725d6fd3b3', 'ket-hop', None),
    ('thu-ngo-efde33108c02', 'ket-hop', None),
    ('van-bai-90cbec75d2a9', 'ket-hop', None),
    ('viger-4-life-ba7c9fe29829', 'ket-hop', None),
    ('vui-xuan-d4f1d1e81ee1', 'ket-hop', None),
    ('can-sa-59de05242d7d', 'nhung-ngay-o-kong', None),
    ('chay-e0df59b7d862', 'nhung-ngay-o-kong', None),
    ('con-quy-e2d7548f5e72', 'nhung-ngay-o-kong', None),
    ('doc-dao-92514674f2d5', 'nhung-ngay-o-kong', None),
    ('dot-them-mot-dieu-nua-di-ong-oi-1912a158f788', 'nhung-ngay-o-kong', None),
    ('ngay-tan-da55c033255f', 'nhung-ngay-o-kong', None),
    ('ngoi-rap-tren-doi-7aa1da26b22e', 'nhung-ngay-o-kong', None),
    ('quen-d677baf9fa76', 'nhung-ngay-o-kong', None),
    ('thay-ma-vui-toan-la-may-va-nui-a85a043340db', 'nhung-ngay-o-kong', None),
    ('thua-giay-ve-voi-480fd1b58886', 'nhung-ngay-o-kong', None),
    ('cnc-2ccd675f8fbe', 'prod-taiheo', None),
    ('cun-46dc07e7a4b7', 'prod-taiheo', None),
    ('rh-real-homie-3d51dfced2b0', 'prod-taiheo', None),
    ('u4ever-ea1b48dfad70', 'prod-taiheo', None),
    ('yaboi-e017bdc4c9e6', 'prod-taiheo', None),
    ('r-e-c-season-1-7663c03bf3d0', 'rap-elite-cypher', 1),
    ('r-e-c-2-story-telling-cba7d3136276', 'rap-elite-cypher', 2),
    ('saigon-weed-ce8e2d0f38f7', 'saigon-smoking-weed', 1),
    ('van-voi-can-sa-7ebbc9a72ad5', 'saigon-smoking-weed', 2),
    ('bay-549c162551ff', 'saigon-smoking-weed', 3),
    ('kiss-my-ass-da6a4525ab30', 'saigon-smoking-weed', 4),
    ('super-hero-1306a77b980b', 'saigon-smoking-weed', 5),
    ('nothing-lasts-forever-a1efbb854b11', 'saigon-smoking-weed', 6),
    ('khoi-bd3a5f6245cf', 'saigon-smoking-weed', 7),
    ('deo-hieu-beat-by-bac-gau-cam-9818189f0c06', 'ttnmp-vol-1', 1),
    ('hoc-beat-by-omoon-655eeaac2d0b', 'ttnmp-vol-1', 2),
    ('ai-cbfc646d9b10', 'ttnmp-vol-1', 3),
    ('im-lang-thoi-beat-by-g-r-i-o-b5b55c4857b9', 'ttnmp-vol-1', 4),
    ('co-sao-dau-beat-by-kjam68-c65fe41285d0', 'ttnmp-vol-1', 5),
    ('biet-ro-van-kho-di-9a4af98de7bd', 'ttnmp-vol-2', 1),
    ('lan-man-f45d063d50bc', 'ttnmp-vol-2', 2),
    ('khong-a01a3e42cb08', 'ttnmp-vol-2', 3),
    ('lay-49c2b4195729', 'ttnmp-vol-2', 4),
    ('sach-f00453ac4b11', 'ttnmp-vol-2', 5),
    ('van-2-b80dbac5de46', 'ttnmp-vol-3', 1),
    ('usual-suspects-f4854d52bdaf', 'ttnmp-vol-3', 2),
    ('ladidadida-eac12bece04e', 'ttnmp-vol-3', 3),
    ('lau-roi-91c44fae5f30', 'ttnmp-vol-3', 4),
    ('btfu-168c13c54e6c', 'ttnmp-vol-3', 5),
    ('f-m-7b67bc72240d', 'ttnmp-vol-3', 6),
    ('dllm-9a51a24a8d8b', 'ttnmp-vol-4', 1),
    ('tyltgm-1b5563979244', 'ttnmp-vol-4', 2),
    ('mrld-ae13e0c26d53', 'ttnmp-vol-4', 3),
    ('ddlcb-5cb683a3f9e2', 'ttnmp-vol-4', 4),
    ('intro-9f62509bfdb8', 'waking-life', 1),
    ('mama-a12571b9ea6a', 'waking-life', 2),
    ('hau-truong-90860647bfe5', 'waking-life', 3),
    ('mot-lan-nua-30957d0ac83d', 'waking-life', 4),
    ('cam-on-rap-2-7cc800d2333a', 'waking-life', 5),
    ('mua-6ec36eb9b026', 'waking-life', 6),
    ('nang-75d6e3f3e5f0', 'waking-life', 7),
    ('rewind-340b504aae15', 'waking-life', 8),
    ('vinataba-76ca78581d29', 'waking-life', 9),
    ('tac-tho-c8a0e019d13a', 'waking-life', 10),
    ('game-3ebf69ce83da', 'waking-life', 11),
]

# (content slug, archive credit, clean credit) — album/session tags moved out of artist
ARTISTS = [
    ('badabingbing-264eaaa41746', 'DSK (Beef 2015)', 'DSK'),
    ('btfu-168c13c54e6c', 'DSK (Vol 3.)', 'DSK'),
    ('binh-tinh-c7f27d3dfe7f', 'DSK verse', 'DSK'),
    ('chay-e7045368429c', 'DSK (talk)', 'DSK'),
    ('cnc-2ccd675f8fbe', 'DSK (Prod. by Taiheo)', 'DSK'),
    ('ddlcb-5cb683a3f9e2', 'DSK (Vol 4.)', 'DSK'),
    ('cuoc-doi-no-b8f710f7d9d0', 'DSK Verse', 'DSK'),
    ('dllm-9a51a24a8d8b', 'DSK (Vol 4.)', 'DSK'),
    ('doc-dao-92514674f2d5', 'DSK at Kong', 'DSK'),
    ('dot-them-mot-dieu-nua-di-ong-oi-1912a158f788', 'DSK at Kong', 'DSK'),
    ('can-sa-59de05242d7d', 'DSK at Kong', 'DSK'),
    ('lan-dau-tien-433c5e84fbdf', 'DSK at Bàng', 'DSK'),
    ('fake-g-2336890c4518', 'Andree ft. DSK (2007)', 'Andree ft. DSK'),
    ('ghetto-genius-83033e0f5c', 'DSK Verse', 'DSK'),
    ('high-again-7f7239d67ecd', 'DSK Verse', 'DSK'),
    ('may-thang-khua-71ba1e6a147c', 'DSK, Quiet Bunny, KraziNoize, Suboi (2011)', 'DSK, Quiet Bunny, KraziNoize, Suboi'),
    ('may-thang-khua-9645527f4965', 'DSK Verse', 'DSK'),
    ('mrld-ae13e0c26d53', 'DSK (Vol 4.)', 'DSK'),
    ('ladidadida-eac12bece04e', 'DSK (Vol 3.)', 'DSK'),
    ('nghi-den-tao-6ef4227acecb', 'DSK StayKong', 'DSK'),
    ('soul-a96d28cd7d88', 'Sativa & DSK (Soul One prod.)', 'Sativa & DSK'),
    ('rh-real-homie-3d51dfced2b0', 'DSK (Prod. by TaiHeo)', 'DSK'),
    ('thay-ma-vui-toan-la-may-va-nui-a85a043340db', 'DSK at Kong', 'DSK'),
    ('tyltgm-1b5563979244', 'DSK (Vol 4.)', 'DSK'),
    ('u4ever-ea1b48dfad70', 'DSK (co-prod. Taiheo)', 'DSK'),
    ('yaboi-e017bdc4c9e6', 'DSK (co-prod. TaiHeo)', 'DSK'),
    ('r-e-c-season-1-7663c03bf3d0', 'DSK (Rap Elite Cypher)', 'DSK'),
    ('r-e-c-2-story-telling-cba7d3136276', 'DSK (Rap Elite Cypher)', 'DSK'),
    ('saigon-weed-ce8e2d0f38f7', 'DSK (Saigon Smoking Weed 01)', 'DSK'),
    ('van-voi-can-sa-7ebbc9a72ad5', 'KraziNoyze ft. DSK (Saigon Smoking Weed 02)', 'KraziNoyze ft. DSK'),
    ('bay-549c162551ff', 'Krazi Noyze (Saigon Smoking Weed 03)', 'Krazi Noyze'),
    ('kiss-my-ass-da6a4525ab30', 'DSK (Saigon Smoking Weed 04)', 'DSK'),
    ('super-hero-1306a77b980b', 'KraziNoyze (Saigon Smoking Weed 05)', 'KraziNoyze'),
    ('nothing-lasts-forever-a1efbb854b11', 'DSK ft. KraziNoyze (Saigon Smoking Weed 06)', 'DSK ft. KraziNoyze'),
    ('khoi-bd3a5f6245cf', 'DSK ft. KraziNoyze (Saigon Smoking Weed 07)', 'DSK ft. KraziNoyze'),
    ('sd-anthem-937f3c576d9a', 'DSK Verse', 'DSK'),
    ('intro-9f62509bfdb8', 'DSK (Waking Life 01)', 'DSK'),
    ('hau-truong-90860647bfe5', 'DSK ft. LynkLee, BDT, Lee7 (Waking Life 03)', 'DSK ft. LynkLee, BDT, Lee7'),
    ('mama-a12571b9ea6a', 'DSK (Waking Life 02)', 'DSK'),
    ('mot-lan-nua-30957d0ac83d', 'DSK (Waking Life 04)', 'DSK'),
    ('cam-on-rap-2-7cc800d2333a', 'DSK (Waking Life 05)', 'DSK'),
    ('mua-6ec36eb9b026', 'DSK (Waking Life 06)', 'DSK'),
    ('nang-75d6e3f3e5f0', 'DSK (Waking Life 07)', 'DSK'),
    ('rewind-340b504aae15', 'DSK (Waking Life 08)', 'DSK'),
    ('vinataba-76ca78581d29', 'DSK (Waking Life 09)', 'DSK'),
    ('tac-tho-c8a0e019d13a', 'DSK (Waking Life 10)', 'DSK'),
    ('game-3ebf69ce83da', 'DSK (Waking Life 11)', 'DSK'),
]


def upgrade():
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO albums (slug, title, kind, year, position) "
            "VALUES (:slug, :title, :kind, :year, :position) "
            "ON CONFLICT (slug) DO NOTHING"
        ),
        [
            dict(slug=s, title=t, kind=k, year=y, position=p)
            for s, t, k, y, p in ALBUMS
        ],
    )
    conn.execute(
        sa.text(
            "UPDATE contents SET album_id = a.id, track_no = :no, updated_at = now() "
            "FROM albums a WHERE a.slug = :album AND contents.slug = :slug "
            "AND contents.type = 'music' AND contents.album_id IS NULL"
        ),
        [dict(slug=s, album=a, no=n) for s, a, n in TRACKS],
    )
    conn.execute(
        sa.text(
            "UPDATE contents SET body = jsonb_set(body, '{artist}', to_jsonb("
            "CAST(:new AS text))), updated_at = now() "
            "WHERE slug = :slug AND type = 'music' AND body->>'artist' = :old"
        ),
        [dict(slug=s, old=o, new=n) for s, o, n in ARTISTS],
    )


def downgrade():
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE contents SET body = jsonb_set(body, '{artist}', to_jsonb("
            "CAST(:old AS text))) "
            "WHERE slug = :slug AND type = 'music' AND body->>'artist' = :new"
        ),
        [dict(slug=s, old=o, new=n) for s, o, n in ARTISTS],
    )
    # ON DELETE SET NULL leaves track_no behind; clear it with the album link.
    conn.execute(
        sa.text(
            "UPDATE contents SET track_no = NULL, updated_at = now() "
            "FROM albums a WHERE contents.album_id = a.id AND a.slug = ANY(:slugs)"
        ),
        dict(slugs=[a[0] for a in ALBUMS]),
    )
    conn.execute(
        sa.text("DELETE FROM albums WHERE slug = ANY(:slugs)"),
        dict(slugs=[a[0] for a in ALBUMS]),
    )

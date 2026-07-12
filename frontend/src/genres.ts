/** Thể loại nhạc dùng CHUNG cho trang Nghe nhạc (bộ lọc) và editor CMS (chọn
    thể loại) — luôn VIẾT HOA toàn bộ. Sửa ở đây là đồng bộ cả hai nơi. */
export const MUSIC_GENRES = [
  'LIFE RAP',
  'LOVE RAP',
  "DISSIN'",
  'GANGSTA',
  'THỂ NGHIỆM',
  'KHÁM PHÁ',
] as const

export type MusicGenre = (typeof MUSIC_GENRES)[number]

import sqlite3

conn = sqlite3.connect('db.sqlite3')
cur = conn.cursor()

# 유저 테이블
cur.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    nickname TEXT UNIQUE NOT NULL,
    is_paid INTEGER DEFAULT 0,
    role TEXT DEFAULT 'user'
)
''')

# 질문 게시글
cur.execute('''
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    image_path TEXT,
    created_at TEXT NOT NULL,
    is_private INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
''')

# 답변
cur.execute('''
CREATE TABLE IF NOT EXISTS answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    admin_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    image_path TEXT,
    video_url TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (post_id) REFERENCES posts(id),
    FOREIGN KEY (admin_id) REFERENCES users(id)
)
''')

# 공지사항
cur.execute('''
CREATE TABLE IF NOT EXISTS announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
''')

# 영상 테이블
cur.execute('''
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    filename TEXT NOT NULL,
    thumbnail TEXT,
    uploader_id INTEGER NOT NULL,
    is_premium INTEGER DEFAULT 0,
    material_file TEXT,
    duration TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (uploader_id) REFERENCES users(id)
)
''')

# 구독코드 테이블
cur.execute('''
CREATE TABLE IF NOT EXISTS subscription_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE,
    user_id INTEGER,
    created_at TEXT,
    expires_at TEXT,
    used_count INTEGER DEFAULT 0,
    max_uses INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(id)
)
''')

conn.commit()
conn.close()
print("✅ DB 초기화 완료!")

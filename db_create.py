import sqlite3

conn = sqlite3.connect("db.sqlite3")
cursor = conn.cursor()

# users
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL,
  nickname TEXT UNIQUE NOT NULL,
  is_paid INTEGER DEFAULT 0,
  role TEXT DEFAULT 'user'
)
''')

# subscription_codes
cursor.execute('''
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

# announcements
cursor.execute('''
CREATE TABLE IF NOT EXISTS announcements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
''')

# videos
cursor.execute('''
CREATE TABLE IF NOT EXISTS videos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  description TEXT,
  filename TEXT NOT NULL,
  thumbnail TEXT,
  uploader_id INTEGER,
  is_premium INTEGER DEFAULT 0,
  material_file TEXT,
  duration TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(uploader_id) REFERENCES users(id)
)
''')

# posts (QnA 질문)
cursor.execute('''
CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  image_path TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  is_private INTEGER DEFAULT 0,
  FOREIGN KEY(user_id) REFERENCES users(id)
)
''')

# answers (QnA 답변)
cursor.execute('''
CREATE TABLE IF NOT EXISTS answers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id INTEGER,
  admin_id INTEGER,
  content TEXT NOT NULL,
  image_path TEXT,
  video_url TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(post_id) REFERENCES posts(id),
  FOREIGN KEY(admin_id) REFERENCES users(id)
)
''')

conn.commit()
conn.close()
print("✅ DB 생성 완료! db.sqlite3 파일이 준비됐습니다.")

from flask import Flask, Response, jsonify, render_template, request, redirect, session, flash, url_for
import sqlite3
from datetime import datetime
from email_utils import generate_code, send_verification_email
import os
from werkzeug.utils import secure_filename
from moviepy.editor import VideoFileClip


app = Flask(__name__)
app.secret_key = 'your_secret_key'

UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_db_connection():
    conn = sqlite3.connect('db.sqlite3')
    conn.row_factory = sqlite3.Row
    return conn

@app.template_filter('datetimeformat')
def datetimeformat(value):
    return datetime.strptime(value, '%Y-%m-%d %H:%M:%S').strftime('%Y.%m.%d %H:%M')

@app.route('/')
def home():
    db = get_db_connection()
    announcement = db.execute('SELECT * FROM announcements ORDER BY created_at DESC LIMIT 1').fetchone()
    db.close()

    if announcement is None:
        announcement = {"title": "", "content": ""}

    return render_template('home.html', announcement=announcement)


@app.route('/announcement/write', methods=['GET', 'POST'])
def write_announcement():
    if 'user' not in session or session['user']['role'] != 'superadmin':
        flash('접근 권한이 없습니다.')
        return redirect('/')

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']

        conn = get_db_connection()
        conn.execute(
            'INSERT INTO announcements (title, content, created_at) VALUES (?, ?, datetime("now"))',
            (title, content)
        )
        conn.commit()
        conn.close()

        flash('공지사항이 등록되었습니다.')
        return redirect('/')

    return render_template('announcement_write.html')



@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        action = request.form.get('action')
        conn = get_db_connection()

        if action == 'send_code':
            email = request.form.get('email')
            existing_email = conn.execute('SELECT 1 FROM users WHERE email = ?', (email,)).fetchone()
            if existing_email:
                flash('이미 가입된 이메일입니다.')
            else:
                code = generate_code()
                session['verify_email'] = email
                session['verify_code'] = code
                session['email_verified'] = False
                send_verification_email(email, code)
                flash('인증번호가 이메일로 전송되었습니다.')

        elif action == 'verify_code':
            input_code = request.form.get('verify_code')
            if input_code == session.get('verify_code'):
                session['email_verified'] = True
                flash('이메일 인증 성공!')
            else:
                flash('인증번호가 틀렸습니다.')

        elif action == 'check_nickname':
            nickname = request.form.get('nickname')
            existing_nickname = conn.execute('SELECT 1 FROM users WHERE nickname = ?', (nickname,)).fetchone()
            if existing_nickname:
                flash('이미 존재하는 닉네임입니다.')
                session['nickname_verified'] = False
            else:
                session['nickname'] = nickname
                session['nickname_verified'] = True
                flash('사용 가능한 닉네임입니다.')

        elif action == 'register':
            if not session.get('email_verified'):
                flash('이메일 인증을 완료해주세요.')
            elif not session.get('nickname_verified'):
                flash('닉네임 중복확인을 완료해주세요.')
            else:
                password = request.form.get('password')
                if len(password) < 8:
                    flash('비밀번호는 8자 이상이어야 합니다.')
                else:
                    try:
                        conn.execute(
                            'INSERT INTO users (email, password, nickname, is_paid, role) VALUES (?, ?, ?, 0, ?)',
                            (session['verify_email'], password, session['nickname'], 'user')
                        )
                        conn.commit()
                        flash('회원가입 완료! 로그인 해주세요.')
                        session.clear()
                        return redirect('/login')
                    except sqlite3.IntegrityError:
                        flash('회원가입 실패: 이메일 또는 닉네임 중복')

        conn.close()
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email, password = request.form['email'], request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email=? AND password=?', (email, password)).fetchone()
        conn.close()
        if user:
            session['user'] = dict(user)
            flash('로그인 성공')
            return redirect('/')
        flash('로그인 실패')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('로그아웃 되었습니다.')
    return redirect('/')

@app.route('/free-video')
def free_video():
    if 'user' not in session:
        flash('로그인 해주세요.')
        return redirect('/login')

    db = get_db_connection()
    videos = db.execute('''
        SELECT v.*, u.nickname FROM videos v
        JOIN users u ON v.uploader_id = u.id
        WHERE v.is_premium = 0
        ORDER BY v.created_at DESC
    ''').fetchall()
    db.close()

    return render_template('free_video.html', videos=videos)


@app.route('/premium-video')
def premium_video():
    if 'user' not in session:
        flash('로그인 해주세요.')
        return redirect('/login')

    db = get_db_connection()
    videos = db.execute('''
        SELECT v.*, u.nickname FROM videos v
        JOIN users u ON v.uploader_id = u.id
        WHERE v.is_premium = 1
        ORDER BY v.created_at DESC
    ''').fetchall()
    db.close()

    return render_template('premium_video.html', videos=videos)

@app.route('/upload_video/<video_type>', methods=['GET', 'POST'])
def upload_video(video_type):
    if 'user' not in session:
        return redirect('/login')
    if session['user']['role'] not in ['admin', 'teacher', 'superadmin']:
        flash('업로드 권한이 없습니다.')
        return redirect('/')

    is_premium = 1 if video_type == 'premium' else 0

    if request.method == 'POST':
        title = request.form['title']
        description = request.form.get('description', '')
        video_file = request.files['video']
        thumbnail = request.files.get('thumbnail')
        material = request.files.get('material')

        if not video_file:
            flash('영상 파일은 필수입니다.')
            return redirect(request.url)

        # 폴더 생성
        os.makedirs('static/videos', exist_ok=True)
        os.makedirs('static/thumbnails', exist_ok=True)
        os.makedirs('static/materials', exist_ok=True)

        # 영상 저장
        video_name = secure_filename(video_file.filename)
        video_path = os.path.join('static/videos', video_name)
        video_file.save(video_path)

        # ⏱ 영상 길이 추출 (moviepy)
        try:
            from moviepy.editor import VideoFileClip
            clip = VideoFileClip(video_path)
            duration_seconds = int(clip.duration)
            minutes = duration_seconds // 60
            seconds = duration_seconds % 60
            duration = f"{minutes:02}:{seconds:02}"
            clip.close()
        except Exception as e:
            print("⚠️ 영상 길이 추출 실패:", e)
            duration = None

        # 썸네일 저장
        thumb_name = None
        if thumbnail and thumbnail.filename:
            thumb_name = secure_filename(thumbnail.filename)
            thumb_path = os.path.join('static/thumbnails', thumb_name)
            thumbnail.save(thumb_path)

        # 자료 저장
        material_name = None
        if material and material.filename:
            material_name = secure_filename(material.filename)
            material.save(os.path.join('static/materials', material_name))

        # DB 저장
        db = get_db_connection()
        db.execute('''
            INSERT INTO videos (title, description, filename, thumbnail, uploader_id, is_premium, material_file, duration)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (title, description, video_name, thumb_name, session['user']['id'], is_premium, material_name, duration))
        db.commit()
        db.close()

        flash('업로드 완료!')
        return redirect('/premium-video' if is_premium else '/free-video')

    return render_template('upload_video.html', is_premium=is_premium)


@app.route('/video/<int:video_id>')
def watch_video(video_id):
    db = get_db_connection()
    video = db.execute('''
        SELECT v.*, u.nickname FROM videos v
        JOIN users u ON v.uploader_id = u.id
        WHERE v.id = ?
    ''', (video_id,)).fetchone()
    db.close()

    if not video:
        os.abort(404)

    user = session.get('user')
    if video['is_premium'] == 1:
        if not user or user['role'] not in ['premium', 'teacher', 'admin', 'superadmin']:
            flash('이 영상은 프리미엄 사용자만 볼 수 있습니다.')
            return redirect('/premium-video')

    return render_template('watch_video.html', video=video)


@app.route('/edit_video/<int:video_id>', methods=['GET', 'POST'])
def edit_video(video_id):
    if 'user' not in session:
        return redirect('/login')
    
    db = get_db_connection()
    video = db.execute('SELECT * FROM videos WHERE id = ?', (video_id,)).fetchone()

    if not video:
        flash('존재하지 않는 영상입니다.')
        db.close()
        return redirect('/')

    user = session['user']
    if user['role'] != 'superadmin' and user['id'] != video['uploader_id']:
        flash('수정 권한이 없습니다.')
        db.close()
        return redirect('/')

    if request.method == 'POST':
        new_title = request.form['title']
        new_desc = request.form['description']

        # 기본 값
        new_thumbnail = video['thumbnail']
        new_material = video['material_file']

        # 썸네일 처리
        if 'thumbnail' in request.files:
            thumbnail_file = request.files['thumbnail']
            if thumbnail_file and thumbnail_file.filename:
                os.makedirs('static/thumbnails', exist_ok=True)
                new_thumbnail = secure_filename(thumbnail_file.filename)
                thumbnail_path = os.path.join('static/thumbnails', new_thumbnail)
                thumbnail_file.save(thumbnail_path)

        # 자료파일 처리
        if 'material' in request.files:
            material_file = request.files['material']
            if material_file and material_file.filename:
                os.makedirs('static/materials', exist_ok=True)
                new_material = secure_filename(material_file.filename)
                material_path = os.path.join('static/materials', new_material)
                material_file.save(material_path)

        db.execute('''
            UPDATE videos
            SET title = ?, description = ?, thumbnail = ?, material_file = ?
            WHERE id = ?
        ''', (new_title, new_desc, new_thumbnail, new_material, video_id))

        db.commit()
        db.close()
        flash('영상 정보가 수정되었습니다.')
        return redirect('/premium-video' if video['is_premium'] else '/free-video')

    db.close()
    return render_template('edit_video.html', video=video)




@app.route('/delete_video/<int:video_id>', methods=['POST'])
def delete_video(video_id):
    if 'user' not in session:
        return redirect('/login')
    
    db = get_db_connection()
    video = db.execute('SELECT * FROM videos WHERE id = ?', (video_id,)).fetchone()
    if not video:
        flash('존재하지 않는 영상입니다.')
        return redirect('/')

    user = session['user']
    if user['role'] != 'superadmin' and user['id'] != video['uploader_id']:
        flash('삭제 권한이 없습니다.')
        return redirect('/')

    db.execute('DELETE FROM videos WHERE id = ?', (video_id,))
    db.commit()
    db.close()
    flash('영상이 삭제되었습니다.')
    return redirect('/premium-video' if video['is_premium'] else '/free-video')



@app.route('/qna')
def qna():
    try:
        conn = get_db_connection()
        posts = conn.execute('''
            SELECT 
                p.id, 
                p.title, 
                IFNULL(p.created_at, '') as created_at,
                p.is_private, 
                IFNULL(u.nickname, '알 수 없음') as nickname,
                EXISTS (
                    SELECT 1 FROM answers a WHERE a.post_id = p.id
                ) AS has_answer
            FROM posts p
            JOIN users u ON p.user_id = u.id
            ORDER BY p.created_at DESC
        ''').fetchall()
        conn.close()
        return render_template('qna.html', posts=posts)
    except Exception as e:
        print(f"🔥 QnA 로딩 에러: {e}")
        return "<h3>Q&A 게시판 로딩 중 오류가 발생했습니다.</h3>", 500




@app.route('/qna/write', methods=['GET', 'POST'])
def qna_write():
    if not session.get('user'):
        flash('로그인 해주세요.')
        return redirect('/login')
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        is_private = 1 if request.form.get('is_private') else 0
        image = request.files.get('image')
        image_path = ''
        if image and image.filename:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image.filename)
            image.save(image_path)
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO posts (user_id, title, content, image_path, created_at, is_private)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session['user']['id'], title, content, image.filename if image_path else '', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), is_private))
        conn.commit()
        conn.close()
        flash('질문이 등록되었습니다.')
        return redirect('/qna')
    return render_template('qna_write.html')

@app.route('/qna/<int:post_id>')
def qna_detail(post_id):
    conn = get_db_connection()
    post = conn.execute('''
        SELECT p.*, u.nickname FROM posts p 
        JOIN users u ON p.user_id = u.id 
        WHERE p.id = ?
    ''', (post_id,)).fetchone()

    if not post:
        conn.close()
        return Response('<script>alert("존재하지 않는 게시글입니다."); location.href="/qna";</script>', mimetype='text/html')

    is_private = post['is_private']
    is_owner = session.get('user') and post['user_id'] == session['user']['id']
    is_admin = session.get('user') and session['user']['role'] in ['admin', 'superadmin']
    is_superadmin = session.get('user') and session['user']['role'] == 'superadmin'

    if is_private and not (is_owner or is_admin):
        conn.close()
        return Response('<script>alert("🔒 비공개된 게시물입니다."); location.href="/qna";</script>', mimetype='text/html')

    answers = conn.execute('''
        SELECT a.*, u.nickname FROM answers a 
        JOIN users u ON a.admin_id = u.id 
        WHERE a.post_id = ?
        ORDER BY a.created_at
    ''', (post_id,)).fetchall()
    conn.close()

    return render_template(
        'qna_detail.html',
        post=post,
        answers=answers,
        is_owner=is_owner,
        is_admin=is_admin,
        is_superadmin=is_superadmin
    )

@app.route('/qna/<int:post_id>/edit', methods=['GET', 'POST'])
def qna_edit(post_id):
    if not session.get('user'):
        flash('로그인이 필요합니다.')
        return redirect('/login')

    conn = get_db_connection()
    post = conn.execute('SELECT * FROM posts WHERE id = ?', (post_id,)).fetchone()

    if not post:
        conn.close()
        flash('존재하지 않는 게시글입니다.')
        return redirect('/qna')

    is_owner = post['user_id'] == session['user']['id']
    is_admin = session['user']['role'] in ['admin', 'superadmin']

    if not (is_owner or is_admin):
        conn.close()
        flash('수정 권한이 없습니다.')
        return redirect('/qna')

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        is_private = 1 if request.form.get('is_private') else 0

        image = request.files.get('image')
        image_path = post['image_path']  # 기본값: 기존 이미지 유지

        if image and image.filename:
            image_path = image.filename
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], image.filename))

        conn.execute('''
            UPDATE posts SET title = ?, content = ?, image_path = ?, is_private = ?
            WHERE id = ?
        ''', (title, content, image_path, is_private, post_id))
        conn.commit()
        conn.close()
        flash('수정이 완료되었습니다.')
        return redirect(f'/qna/{post_id}')

    conn.close()
    return render_template('qna_post_edit.html', post=post)



@app.route('/qna/<int:post_id>/answer', methods=['POST'])
def qna_answer(post_id):
    if not session.get('user') or session['user']['role'] not in ['admin', 'superadmin']:
        flash('관리자만 답변할 수 있습니다.')
        return redirect('/qna')
    content = request.form['content']
    image = request.files.get('image')
    video_url = request.form['video_url']
    image_path = ''
    if image and image.filename:
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], image.filename)
        image.save(image_path)
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO answers (post_id, admin_id, content, image_path, video_url, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (post_id, session['user']['id'], content, image.filename if image_path else '', video_url, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    flash('답변이 등록되었습니다.')
    return redirect(f'/qna/{post_id}')

@app.route('/qna/<int:post_id>/delete', methods=['POST'])
def qna_delete(post_id):
    if not session.get('user'):
        flash('로그인이 필요합니다.')
        return redirect('/login')
    conn = get_db_connection()
    post = conn.execute('SELECT * FROM posts WHERE id = ?', (post_id,)).fetchone()
    if not post:
        flash('존재하지 않는 글입니다.')
        conn.close()
        return redirect('/qna')
    is_owner = post['user_id'] == session['user']['id']
    is_superadmin = session['user']['role'] == 'superadmin'
    if not (is_owner or is_superadmin):
        flash('삭제 권한이 없습니다.')
        conn.close()
        return redirect(f'/qna/{post_id}')
    conn.execute('DELETE FROM posts WHERE id = ?', (post_id,))
    conn.commit()
    conn.close()
    flash('글이 삭제되었습니다.')
    return redirect('/qna')

@app.route("/qna/<int:post_id>/answer/<int:answer_id>/edit", methods=["GET", "POST"])
def edit_answer(post_id, answer_id):
    if "user" not in session:
        return redirect("/login")

    db = get_db_connection()
    answer = db.execute('''
        SELECT * FROM answers
        WHERE id = ?
    ''', (answer_id,)).fetchone()

    if not answer or answer["post_id"] != post_id:
        db.close()
        return "답변을 찾을 수 없습니다.", 404

    if answer["admin_id"] != session["user"]["id"]:
        db.close()
        return "권한이 없습니다.", 403

    if request.method == "POST":
        action = request.form.get("action")

        if action == "delete":
            db.execute("DELETE FROM answers WHERE id = ?", (answer_id,))
            db.commit()
            db.close()
            flash("답변이 삭제되었습니다.")
            return redirect(f"/qna/{post_id}")

        elif action == "update":
            content = request.form["content"]
            video_url = request.form.get("video_url", "")
            image_file = request.files.get("image")

            if image_file and image_file.filename:
                image_filename = secure_filename(image_file.filename)
                image_path = os.path.join(app.config["UPLOAD_FOLDER"], image_filename)
                image_file.save(image_path)
            else:
                image_filename = answer["image_path"]

            db.execute("""
                UPDATE answers 
                SET content = ?, video_url = ?, image_path = ?
                WHERE id = ?
            """, (content, video_url, image_filename, answer_id))
            db.commit()
            db.close()
            flash("답변이 수정되었습니다.")
            return redirect(f"/qna/{post_id}")

    db.close()
    return render_template("qna_edit.html", answer=answer, post_id=post_id)




@app.route('/mypage')
def mypage():
    if 'user' not in session:
        flash('로그인 해주세요.')
        return redirect('/login')

    conn = get_db_connection()
    current_nickname = conn.execute('SELECT nickname FROM users WHERE id = ?', (session['user']['id'],)).fetchone()['nickname']

    users = []
    if session['user']['role'] == 'superadmin':
        users = conn.execute('SELECT id, email, nickname, role, is_paid FROM users').fetchall()

    conn.close()
    return render_template('mypage.html',
                           current_nickname=current_nickname,
                           users=users)


@app.route('/mypage/set_admin', methods=['POST'])
def set_admin():
    if 'user' not in session or session['user']['role'] != 'superadmin':
        return redirect('/')

    user_id = request.form['user_id']
    new_role = request.form['new_role']
    conn = get_db_connection()

    if new_role == 'teacher':
        conn.execute('UPDATE users SET role = ?, is_paid = ? WHERE id = ?', ('admin', 0, user_id))
    elif new_role == 'premium':
        conn.execute('UPDATE users SET role = ?, is_paid = ? WHERE id = ?', ('user', 1, user_id))
    elif new_role == 'student':
        conn.execute('UPDATE users SET role = ?, is_paid = ? WHERE id = ?', ('user', 0, user_id))

    conn.commit()
    conn.close()
    flash('권한이 변경되었습니다.')
    return redirect('/mypage')


@app.route("/mypage/apply_nickname", methods=["POST"])
def apply_nickname():
    if "user" not in session:
        return jsonify(success=False, message="로그인이 필요합니다."), 401

    nickname = request.form.get("nickname", "").strip()
    if not nickname:
        return jsonify(success=False, message="닉네임을 입력해주세요."), 400

    conn = get_db_connection()
    existing = conn.execute(
        "SELECT 1 FROM users WHERE nickname = ? AND id != ?",
        (nickname, session["user"]["id"])
    ).fetchone()

    if existing:
        conn.close()
        return jsonify(success=False, message="이미 사용 중인 닉네임입니다."), 409

    conn.execute("UPDATE users SET nickname = ? WHERE id = ?", (nickname, session["user"]["id"]))
    conn.commit()
    conn.close()

    session["user"]["nickname"] = nickname
    return jsonify(success=True, message="닉네임이 성공적으로 변경되었습니다.")


@app.route("/mypage/delete_account", methods=["POST"])
def delete_account():
    if "user" not in session:
        return redirect("/login")

    # 총관리자 계정 삭제 방지
    if session["user"]["email"] == "jaewon1228@snu.ac.kr":
        flash("⚠️ 총관리자 계정은 삭제할 수 없습니다.")
        return redirect("/mypage")

    user_id = session["user"]["id"]
    db = get_db_connection()
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    session.clear()
    return redirect("/")

@app.route('/mypage/delete_user', methods=['POST'])
def delete_user_by_admin():
    if 'user' not in session or session['user']['role'] != 'superadmin':
        return redirect('/login')

    user_id = request.form.get('user_id')
    if not user_id:
        return redirect('/mypage')

    conn = get_db_connection()
    conn.execute('DELETE FROM users WHERE id = ? AND role != ?', (user_id, 'superadmin'))
    conn.commit()
    conn.close()
    flash('사용자를 탈퇴시켰습니다.')
    return redirect('/mypage')



@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if not session.get('user') or session['user']['role'] not in ['admin', 'superadmin']:
        flash('접근 권한이 없습니다.')
        return redirect('/')

    conn = get_db_connection()

    if request.method == 'POST':
        if session['user']['role'] == 'superadmin':
            target_id = request.form.get('target_id')
            action = request.form.get('action')
            if action == 'make_admin':
                conn.execute("UPDATE users SET role = 'admin' WHERE id = ?", (target_id,))
            elif action == 'revoke_admin':
                conn.execute("UPDATE users SET role = 'user' WHERE id = ?", (target_id,))
            conn.commit()

    users = conn.execute("SELECT id, email, is_paid, role FROM users").fetchall()
    codes = conn.execute('''
        SELECT c.*, u.email FROM codes c 
        JOIN users u ON c.user_id = u.id
        ORDER BY created_at DESC
    ''').fetchall()
    conn.close()
    return render_template('admin.html', users=users, codes=codes)

@app.route('/teachers')
def teacher_list():
    db = get_db_connection()
    teachers = db.execute('''
        SELECT id, nickname, bio, profile_image FROM users
        WHERE role IN ('admin', 'teacher', 'superadmin') AND bio IS NOT NULL AND bio != ''
        ORDER BY id DESC
    ''').fetchall()
    db.close()
    return render_template('teacher_list.html', teachers=teachers)

@app.route('/teacher/<int:user_id>')
def teacher_profile(user_id):
    db = get_db_connection()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    db.close()

    if not user:
        return "<h3>존재하지 않는 사용자입니다.</h3>", 404

    return render_template('teacher_profile.html', user=user)



@app.route('/teacher/profile/edit', methods=['GET', 'POST'])
def edit_teacher_profile():
    if 'user' not in session or session['user']['role'] not in ['admin', 'teacher', 'superadmin']:
        flash('접근 권한이 없습니다.')
        return redirect('/')

    user_id = session['user']['id']
    db = get_db_connection()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

    if request.method == 'POST':
        bio = request.form['bio']
        image = request.files.get('image')
        filename = user['profile_image']

        if image and image.filename:
            os.makedirs('static/profiles', exist_ok=True)
            filename = secure_filename(image.filename)
            image.save(os.path.join('static/profiles', filename))

        db.execute('UPDATE users SET bio = ?, profile_image = ? WHERE id = ?', (bio, filename, user_id))
        db.commit()
        db.close()

        flash('프로필이 업데이트되었습니다.')
        return redirect('/teachers')  # ✅ 목록으로 이동

    db.close()
    return render_template('edit_teacher_profile.html', user=user)

@app.route('/teacher/profile/delete', methods=['POST'])
def delete_teacher_profile():
    if 'user' not in session:
        flash('로그인이 필요합니다.')
        return redirect('/login')

    user_id = session['user']['id']
    db = get_db_connection()

    # 총관리자는 삭제 불가
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if user['email'] == 'jaewon1228@snu.ac.kr':
        db.close()
        flash('총관리자 계정은 삭제할 수 없습니다.')
        return redirect(f'/teacher/{user_id}')

    db.execute('UPDATE users SET bio = NULL, profile_image = NULL WHERE id = ?', (user_id,))
    db.commit()
    db.close()

    flash('선생님 소개가 삭제되었습니다.')
    return redirect('/teachers')



def initialize_superadmin():
    conn = get_db_connection()
    existing = conn.execute("SELECT 1 FROM users WHERE email = ?", ("jaewon1228@snu.ac.kr",)).fetchone()
    if not existing:
        conn.execute('''
            INSERT INTO users (email, password, nickname, is_paid, role)
            VALUES (?, ?, ?, ?, ?)
        ''', ("jaewon1228@snu.ac.kr", "wodnjs1228@", "총관리자", 1, "superadmin"))
        conn.commit()
        print("[초기화] 총관리자 계정이 생성되었습니다.")
    else:
        print("[확인] 총관리자 계정이 이미 존재합니다.")
    conn.close()

def initialize_database():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    ''')
    conn.commit()
    conn.close()

if __name__ == '__main__':
    initialize_database()
    initialize_superadmin()
    app.run(host='0.0.0.0', port=5000, debug=True)

from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash
from datetime import datetime
from datetime import datetime
from flask import jsonify, request
import pytz
from datetime import datetime
from datetime import timezone         
from flask_login import UserMixin
tz_bkk = pytz.timezone("Asia/Bangkok")
from flask_login import LoginManager, login_required, login_user, logout_user, current_user
from datetime import timedelta  # เพิ่มการ import timedelta
from flask_socketio import SocketIO, emit, join_room
from markupsafe import escape






# (ในไฟล์ app.py)





# app.py (หรือตำแหน่งที่ตั้ง config)
from flask_mail import Mail, Message
from flask_login import (
    LoginManager,          # ตัวจัดการล็อกอิน
    UserMixin,             # mixin ให้โมเดล User
    login_required,
    login_user,
    logout_user,
    current_user
)





import re                                          # ← ถ้ายังไม่ได้ import

# Regex เบื้องต้น: ยอมรับ 10-15 หลัก จะมี +, ช่องว่าง, - ก็ได้
PHONE_PATTERN = re.compile(r'^\+?[\d\s\-]{10,15}$')






# -------------------- 1)  ตั้งค่าคงที่ (ไฟล์เดียวกัน แต่ไว้เหนือทุก route) --------------------
TITLES = [
    "งคบ รับเรื่อง",
    "อยู่ระหว่างประชุมกลั่นกรองผลงานทางวิชาการ",
    "เข้าที่ประชุมกลั่นกรองเรียบร้อยแล้ว",
    "อยู่ระหว่างการประเมินการสอนและเอกสารประกอบการสอน",
    "ผ่านการประเมินการสอนและเอกสารประกอบการสอน",
    "อยู่ระหว่างเข้าที่ประชุม ก.พ.ว.",
    "ประชุม ก.พ.ว.เรียบร้อยแล้ว",
    "อยู่ระหว่างทาบทามผู้ทรงคุณวุฒิ",
    "ผลการประเมิน",
    "อยู่ระหว่างการประชุม ค.ก.ก ประเมินผลงานทางวิชาการ(กรณีไม่ผ่าน)",
    "ผ่านการประเมินเป็นเอกฉันท์",
    "ประชุม ก.พ.อ.",
    "ประชุมสภามหาวิทยาลัย",
]

SHOW_TIME_STEPS = {1, 3, 5, 7, 9, 12, 13}


def ensure_workflow(user_id):
    # ถ้ามีแล้วก็ข้าม
    if WorkflowStep.query.filter_by(user_id=user_id).first():
        return

    for no, title in enumerate(TITLES, 1):
        db.session.add(
            WorkflowStep(
                user_id    = user_id,
                order_no   = no,
                title      = title,
                is_visible = False if 10 <= no <= 13 else True
            )
        )
    db.session.commit()





app = Flask(__name__, template_folder='templates')
app.secret_key = 'your_secret_key_here'
# ⬇️  สร้าง LoginManager แล้วผูกกับ app
login_manager = LoginManager(app)
login_manager.login_view = "user_login"  # ใช้ชื่อ endpoint ไม่ใช่ชื่อไฟล์
login_manager.login_message_category = "warning"

app.permanent_session_lifetime = timedelta(days=365)  # ตั้งให้ session อยู่ได้นาน 1 ปี
app.session_cookie_name = 'your_session_cookie_name'  # ตั้งชื่อคุกกี้ session









BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'data.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)





class AcademicRequest(db.Model):
    __tablename__ = "academic_request"

    id                 = db.Column(db.Integer, primary_key=True)
    name               = db.Column(db.String(100), nullable=False)
    position_requested = db.Column(db.String(100), nullable=False)
    reason             = db.Column(db.Text,        nullable=False)
    submitted_at       = db.Column(db.DateTime,    default=datetime.utcnow)
    user_id            = db.Column(
        db.Integer,
        db.ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False
    )

# ──────────────────────────────
#  WorkflowStep
# ──────────────────────────────
class WorkflowStep(db.Model):
    __tablename__ = "workflow_step"

    id        = db.Column(db.Integer, primary_key=True)
    user_id   = db.Column(
        db.Integer,
        db.ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False
    )
    order_no  = db.Column(db.Integer)           # 1-13
    title     = db.Column(db.String(150))
    is_done   = db.Column(db.Boolean,  default=False)
    done_at   = db.Column(db.DateTime)
    comment   = db.Column(db.Text)
    is_visible = db.Column(db.Boolean, default=True)

    # ▼ ExpertVote ลูก ๆ ของแต่ละขั้น
    experts = db.relationship(
        "ExpertVote",
        backref="step",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

# ──────────────────────────────
#  ExpertVote
# ──────────────────────────────
class ExpertVote(db.Model):
    __tablename__ = "expert_vote"

    id       = db.Column(db.Integer, primary_key=True)
    step_id  = db.Column(
        db.Integer,
        db.ForeignKey("workflow_step.id", ondelete="CASCADE"),
        nullable=False
    )
    idx      = db.Column(db.Integer)   # 0-2  (ผู้ทรง 1-3)
    approved = db.Column(db.Boolean)   # True / False / None

# ──────────────────────────────
#  User
# ──────────────────────────────
class User(db.Model, UserMixin):
    __tablename__ = "user"

    id        = db.Column(db.Integer, primary_key=True)
    username  = db.Column(db.String(80),  unique=True, nullable=False)
    password  = db.Column(db.String(128), nullable=False)   # เก็บ hash ได้ยาว ๆ
    full_name = db.Column(db.String(150), nullable=False)
    first_name = db.Column(db.String(80))
    last_name  = db.Column(db.String(80))
    faculty    = db.Column(db.String(100), nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    role       = db.Column(db.String(20),  default="user")
    phone      = db.Column(db.String(20))   # 🆕 เพิ่มบรรทัดนี้
    position = db.Column(db.String(100), nullable=True)

    # ▼ ความสัมพันธ์ (มี cascade)
    requests = db.relationship(
        "AcademicRequest",
        backref="user",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    workflow_steps = db.relationship(
        "WorkflowStep",
        backref="user",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    contact_messages = db.relationship(
        "ContactMessage",
        back_populates="user",
        cascade="all, delete-orphan", # <-- This is the crucial instruction
        lazy="dynamic"
    )
     
     


#ข้อความคอนเเท้คค

class ContactMessage(db.Model):
    __tablename__ = "contact_message"

    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Foreign Key ไปยัง user (เหมือนเดิม)
    user_id = db.Column(db.Integer,
                        db.ForeignKey("user.id", ondelete="CASCADE"),
                        nullable=False)

    # Relationship กับ replies (เหมือนเดิม)
    replies = db.relationship(
        'ContactReply',
        backref='contact',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )

    # Relationship กับ User (แก้ไขแล้ว)
    # ⬇️ ⬇️ ⬇️ ⬇️ ⬇️ ⬇️
    # เปลี่ยนจาก backref มาใช้ back_populates
    # เพื่อเชื่อมกลับไปที่ attribute ชื่อ 'contact_messages' ใน User model
    user = db.relationship("User", back_populates="contact_messages")
    
class ContactReply(db.Model):
    __tablename__ = "contact_reply"

    id          = db.Column(db.Integer, primary_key=True)
    contact_id  = db.Column(                  # FK ไป ContactMessage
        db.Integer, db.ForeignKey("contact_message.id", ondelete="CASCADE"),
        nullable=False
    )
    body        = db.Column(db.Text, nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    # (ถ้าอยากเก็บว่าใครตอบ) ➜ FK ไป User
    admin_id    = db.Column(db.Integer, db.ForeignKey("user.id"))
    admin       = db.relationship("User", lazy="joined")



def recalc_after_vote(user_id):
    s9  = WorkflowStep.query.filter_by(user_id=user_id, order_no=9).first()
    s10 = WorkflowStep.query.filter_by(user_id=user_id, order_no=10).first()
    s11 = WorkflowStep.query.filter_by(user_id=user_id, order_no=11).first()
    s12 = WorkflowStep.query.filter_by(user_id=user_id, order_no=12).first()
    s13 = WorkflowStep.query.filter_by(user_id=user_id, order_no=13).first()

    # ----- โหวตยังไม่ครบ 3 -----
    if s9.experts.count() < 3 or any(v.approved is None for v in s9.experts):
        for st in (s10, s11, s12, s13):
            st.is_visible = False
        db.session.commit()
        return

    votes = [v.approved for v in s9.experts]          # [True, False, True] …

    if all(votes):                                    # ✅ ผ่าน 3/3
        s10.is_visible = False
        s11.is_visible = True
        s12.is_visible = False
    else:                                             # ❌ มีไม่ผ่าน
        s10.is_visible = True
        s11.is_visible = False
        s12.is_visible = True

    s13.is_visible = True                             # สภา ม.
    db.session.commit()


def create_default_steps(user_id):
    for no, title in enumerate(TITLES, 1):
        db.session.add(WorkflowStep(
            user_id    = user_id,
            order_no   = no,
            title      = title,
            is_visible = False if 10 <= no <= 13 else True
        ))
    db.session.commit()
    
#ตัวเปิดช่อง10-13
@app.post('/expert_vote/<int:step_id>/<int:idx>')
def expert_vote(step_id, idx):
    ok   = bool(request.get_json().get('approved'))

    vote = ExpertVote.query.filter_by(step_id=step_id, idx=idx).first()
    if not vote:
        vote = ExpertVote(step_id=step_id, idx=idx)
        db.session.add(vote)
    vote.approved = ok
    db.session.commit()

    recalc_after_vote(vote.step.user_id)
    return jsonify(success=True)

@app.post('/expert_toggle/<int:step_id>/<int:idx>')
def expert_toggle(step_id, idx):
    done = bool(request.get_json().get('done'))
    # … (บันทึกว่าผู้ทรง idx ส่งงานแล้ว) …
    return jsonify(success=True)

@app.template_filter("th_time")
def th_time(dt):
    return dt.astimezone(bangkok).strftime("%d/%m/%Y %H:%M")


# === ROUTES ===
@app.route('/')
def index():
    return render_template('index.html')


#ติกผู้ทรง3คน
@app.post("/toggle_expert/<int:step_id>/<int:index>")
def toggle_expert(step_id, index):
    # index = 0,1,2  (แทนผู้ทรงคนที่ 1-3)
    data   = request.get_json()
    done   = bool(data.get("done"))

    state  = EXPERT_STATE.setdefault(step_id, [False, False, False])
    state[index] = done

    return jsonify(success=True)



socketio = SocketIO(app, async_mode='eventlet')   # หรือ 'gevent'

@socketio.on('join')
def on_join(data):
    join_room(data['room'])

@socketio.on('comment_changed')
def save_comment(payload):
    step_id = payload['step_id']
    text    = payload['text'].strip()

    step = WorkflowStep.query.get(step_id)
    if not step:                 # guard
        return

    step.comment = text
    db.session.commit()

    # กระจายให้ทุก client ใน room เดียวกัน
    emit('comment_update', {
        'step_id': step_id,
        'text'   : text,
    }, room = payload['room'], include_self=False)






@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))



#การติกสถานะ
@app.post("/toggle_step/<int:step_id>")
def toggle_step(step_id):
    data = request.get_json()
    done = bool(data.get("done"))
    
    comment = data.get("comment")

    step = WorkflowStep.query.get_or_404(step_id)
    step.is_done = done

    # ส่วนนี้เหมือนเดิม: บันทึกเวลาเป็น UTC
    if done and step.order_no in {1, 3, 5, 7, 9, 12, 13}:
        step.done_at = datetime.utcnow()
    else:
        step.done_at = None

    db.session.commit()
    step.comment = comment

    # ▼▼▼ แก้ไขส่วนนี้ทั้งหมด ▼▼▼
    formatted_time = ""
    if step.done_at:
        # 1. แปลงเวลา UTC จากฐานข้อมูลให้เป็นเวลาโซนกรุงเทพฯ
        local_time = step.done_at.replace(tzinfo=timezone.utc).astimezone(bangkok_tz)
        
        # 2. จัดรูปแบบเวลาที่แปลงแล้วให้เป็น string
        formatted_time = local_time.strftime("%d/%m/%Y %H:%M")
    
    # 3. ส่งเวลาที่จัดรูปแบบถูกต้องแล้วกลับไปให้ JavaScript
    return jsonify(
        success=True,
        done_at=formatted_time 
    )
    # ▲▲▲ จบส่วนที่แก้ไข ▲▲▲




# ───────────────────────────────────────
#  เข้าสู่ระบบแอดมิน
# ───────────────────────────────────────
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # ✅ อนุญาตเฉพาะ admin/admin999
        if username == 'admin' and password == 'admin999':
            session.clear()

            # ✨ 1) ดึง record แอดมินจาก DB (หรือสร้างถ้าไม่เจอ) ✨
            admin_user = User.query.filter_by(username='admin').first()
            if not admin_user:
                admin_user = User(
                    username = 'admin',
                    full_name = 'Admin',
                    password = 'admin999',
                    role = 'admin',
                    email = 'admin@example.com',
                    faculty = '-'
                )
                db.session.add(admin_user)
                db.session.commit()
            
            login_user(admin_user, remember=True)
            

            # ✨ 2) เก็บ user_id, role, flag ลง session ✨
            session['user_id']  = admin_user.id      # ← สำคัญมาก
            session['username'] = 'admin'
            session['role']     = 'admin'
            session['admin']    = True

            return redirect(url_for('admin_dashboard'))

        flash("❌ เฉพาะผู้ดูแลระบบเท่านั้นที่เข้าสู่ระบบนี้ได้", "danger")

    return render_template('admin_login.html')







@app.template_filter('nl2br')
def nl2br(s):
    """Converts newlines in a string to HTML line breaks."""
    # 1. ป้องกัน XSS โดยการแปลงอักขระพิเศษเป็น HTML entities
    escaped_s = escape(s)
    # 2. แทนที่ \n ด้วย <br> และคืนค่าเป็น Markup ที่ปลอดภัย
    return escaped_s.replace('\n', '<br>\n')


@app.route('/manage_users')
def manage_users():
    # เช็ค Session ว่าเป็น Admin หรือไม่
    if 'role' not in session or session['role'] not in ['admin', ]:
        flash("❌ คุณไม่มีสิทธิ์เข้าถึงหน้านี้!", "danger")
        return redirect(url_for('admin_login'))  # ถ้าไม่ใช่ admin, ให้ไปหน้า login

    # ดึงข้อมูลผู้ใช้ทั้งหมด
    users = User.query.all()
    
    # ส่งข้อมูลไปยังเทมเพลต
    return render_template('manage_users.html', users=users)


@app.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
def edit_user(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        user.first_name = request.form['first_name']
        user.last_name  = request.form['last_name']
        user.full_name  = f"{user.first_name} {user.last_name}".strip()
        user.email      = request.form['email']
        user.faculty    = request.form['faculty']

        new_password     = request.form.get('password')
        current_password = request.form.get('current_password')

        # ถ้ามีการเปลี่ยนรหัสผ่าน
        if new_password:
            if not current_password:
                flash("❌ กรุณากรอกรหัสผ่านปัจจุบันก่อนเปลี่ยนรหัสผ่าน", "danger")
                return redirect(url_for('edit_user', user_id=user.id))

            if current_password != user.password:
                flash("❌ รหัสผ่านเดิมไม่ถูกต้อง", "danger")
                return redirect(url_for('edit_user', user_id=user.id))

            user.password = new_password  # ยังเป็น plain text อยู่

        db.session.commit()
        flash("✅ แก้ไขข้อมูลผู้ใช้เรียบร้อยแล้ว", "success")
        return redirect(url_for('manage_users'))

    return render_template('edit_user.html', user=user)






@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        username    = request.form.get('username')
        email       = request.form.get('email')
        password    = request.form.get('password')
        role        = request.form.get('role', 'user')
        first_name  = request.form.get('first_name')
        last_name   = request.form.get('last_name')
        faculty     = request.form.get('faculty')
        position = request.form.get('position')
        phone = request.form.get('phone')
        
        full_name   = f"{first_name} {last_name}".strip()  # 🟢 สำคัญมาก

        # เช็กซ้ำว่าไม่มี user/email ซ้ำ
        if User.query.filter_by(username=username).first():
            flash("❌ ชื่อผู้ใช้นี้ถูกใช้ไปแล้ว!", "danger")
            return redirect(url_for('add_user'))
        if User.query.filter_by(email=email).first():
            flash("❌ อีเมลนี้ถูกใช้ไปแล้ว!", "danger")
            return redirect(url_for('add_user'))

        new_user = User(
            username   = username,
            email      = email,
            password   = password,
            role       = role,
            first_name = first_name,
            last_name  = last_name,
            full_name  = full_name,  # ✅ ต้องมี!
            position=    position,
            phone=       phone,
            faculty    = faculty
            
            
        )
        db.session.add(new_user)
        db.session.commit()

        flash("✅ เพิ่มผู้ใช้สำเร็จ!", "success")
        return redirect(url_for('manage_users'))

    return render_template('add_user.html')




#ลบผู้ใช้

@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    # 🔐 อนุญาตเฉพาะแอดมิน
    if session.get('role') != 'admin':
        flash("❌ คุณไม่มีสิทธิ์ลบผู้ใช้", "danger")
        return redirect(url_for('manage_users'))

    user = User.query.get_or_404(user_id)
    db.session.delete(user)          # cascade ลบลูกหลานทั้งหมด
    db.session.commit()
    flash(f"🗑️ ลบผู้ใช้ {user.username} แล้ว", "success")
    return redirect(url_for('manage_users'))







#ผู้ใช้ติดต่อ
# -----  contact (user side)  ---------------------------------
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        message = request.form['message'].strip()

        if not message:
            flash("❌ กรุณากรอกข้อความ", "danger")
            return redirect(url_for('contact'))

        db.session.add(ContactMessage(
            subject   = subject or "(ไม่มีหัวข้อ)",
            message   = message,
            user_id   = session.get('user_id')          # ถ้ามีระบบล็อกอิน
        ))
        db.session.commit()
        flash("✅ ส่งข้อความเรียบร้อย!", "success")
        return redirect(url_for('contact'))

    return render_template('contact.html')



@app.template_filter("th_time")
def th_time(dt, fmt="%d/%m/%Y %H:%M"):
    if not dt:
        return ""
    if dt.tzinfo is None:           # ← ถ้าเจอค่า naive
        dt = dt.replace(tzinfo=timezone.utc)
    th = pytz.timezone("Asia/Bangkok")
    return dt.astimezone(th).strftime(fmt)



#ดึงชื่อผู้ใช้มาที่มีชื่อนามสกุล
@app.route("/user_overview")
def user_overview():
    # ดึงเฉพาะ user ที่กรอกทั้ง first_name และ last_name
    users = (
    db.session.query(User)
    .filter(User.full_name.isnot(None), User.full_name != '')
    .all()
)

    # (ถ้ามี dict latest_status / progress ก็เตรียมตรงนี้ได้เหมือนเดิม)
    return render_template("user_overview.html", users=users)
# --- 1. เพิ่ม MAP สำหรับตำแหน่ง ---
POSITION_MAP = {
    'lecturer': 'อาจารย์',
    'assistant_professor': 'ผู้ช่วยศาสตราจารย์',
    'associate_professor': 'รองศาสตราจารย์',
    'professor': 'ศาสตราจารย์'
}

# --- 2. สร้างตัวกรอง (Filter) สำหรับ Template ---
# (นี่คือฟังก์ชันที่ HTML ของคุณเรียกหา)
@app.template_filter("position_th")
def position_th(code):
    """แปลงรหัสตำแหน่ง ➜ ชื่อภาษาไทย"""
    return POSITION_MAP.get(code, "ไม่ระบุตำแหน่ง")






@app.route('/admin/contact')
def admin_contact():
    if 'admin' not in session or not session.get('admin'):
        flash("❌ คุณไม่มีสิทธิ์เข้าถึงหน้านี้", "danger")
        return redirect(url_for('admin_login'))  # ถ้าไม่ใช่แอดมิน ให้ไปหน้า login

    messages = ContactMessage.query.all()
    return render_template('admin_contact.html', messages=messages,pytz=pytz)


# ───────────────────────────────────────────────────────────
#  helper: แปลงดัชนีขั้น → ชื่อ & สี badge
# ───────────────────────────────────────────────────────────
TITLES = [
    "งคบ รับเรื่อง",
    "อยู่ระหว่างประชุมกลั่นกรองผลงานทางวิชาการ",
    "เข้าที่ประชุมกลั่นกรองเรียบร้อยแล้ว",
    "อยู่ระหว่างการประเมินการสอนและเอกสารประกอบการสอน",
    "ผ่านการประเมินการสอนและเอกสารประกอบการสอน",
    "อยู่ระหว่างเข้าที่ประชุม ก.พ.ว.",
    "ประชุม ก.พ.ว.เรียบร้อยแล้ว",
    "อยู่ระหว่างทาบทามผู้ทรงคุณวุฒิ",
    "ผลการประเมิน",
    "อยู่ระหว่างการประชุม ค.ก.ก ประเมินผลงานทางวิชาการ(กรณีไม่ผ่าน)",
    "ผ่านการประเมินเป็นเอกฉันท์",
    "ประชุม ก.พ.อ.",
    "ประชุมสภามหาวิทยาลัย",
]

def status_label(idx: int) -> str:
    """รับดัชนี 0-12 แล้วคืนชื่อขั้น ถ้า idx < 0 = ยังไม่ได้เริ่ม"""
    return TITLES[idx] if 0 <= idx < len(TITLES) else "ยังไม่ได้เริ่ม"

def status_color(idx: int) -> str:
    """คืนคลาส bootstrap สำหรับ badge สีแต่ละขั้น"""
    palette = [
        "bg-secondary text-white",
        "bg-info text-dark",
        "bg-primary text-white",
        "bg-warning text-dark",
        "bg-success text-white",
        "bg-primary text-white",
        "bg-success text-white",
        "bg-info text-dark",
        "bg-success text-white",
        "bg-warning text-dark",
        "bg-success text-white",
        "bg-primary text-white",
        "bg-primary text-white",
    ]
    return palette[idx] if 0 <= idx < len(palette) else "bg-light text-dark"


from types import SimpleNamespace
from sqlalchemy import func

def query_user_approvals():
    """
    ดึงผู้ใช้ทุกคน + ขั้นล่าสุดที่ *ทำเสร็จแล้ว* (is_done=True)

    ถ้าผู้ใช้ยังไม่ทำขั้นไหนเลย → latest_step=-1  , latest_time=None
    """
    # sub-query: หา order_no สูงสุด (ขั้นล่าสุด) ที่ทำเสร็จของแต่ละ user
    latest_sub = (
        db.session.query(
            WorkflowStep.user_id,
            func.max(WorkflowStep.order_no).label("max_order")
        )
        .filter(WorkflowStep.is_done.is_(True))
        .group_by(WorkflowStep.user_id)
        .subquery()
    )

    # join กับ User + WorkflowStep อีกที เพื่อได้วันที่ / ชื่อขั้น
    rows = (
        db.session.query(
            User.id, User.username, User.full_name, User.faculty,
            User.email, User.phone,
            WorkflowStep.order_no, WorkflowStep.done_at
        )
        .outerjoin(latest_sub, latest_sub.c.user_id == User.id)
        .outerjoin(
            WorkflowStep,
            (WorkflowStep.user_id == User.id) &
            (WorkflowStep.order_no == latest_sub.c.max_order)
        )
        .order_by(User.username.asc())
        .all()
    )

    # แปลงเป็นโครงสร้างที่ template ใช้สะดวก
    data = []
    for uid, uname, fname, fac, email, phone, step_no, done_at in rows:
        # ถ้า user ยังไม่มีขั้นใดเสร็จ step_no จะเป็น None
        latest_step = (step_no - 1) if step_no else -1       # zero-index
        data.append(
            SimpleNamespace(
                id           = uid,
                username     = uname,
                full_name    = fname or "-",
                department   = FACULTY_MAP.get(fac, "ไม่ระบุคณะ"),
                email        = email,
                phone        = phone or "-",
                latest_step  = latest_step,
                latest_time  = done_at
            )
        )
    return data
def to_thai_timezone(utc_dt):
    """ฟังก์ชันสำหรับแปลง datetime object ที่เป็น UTC ให้เป็นเวลาไทย"""
    if not utc_dt:
        return None
    
    thai_tz = pytz.timezone('Asia/Bangkok')
    
    if utc_dt.tzinfo is None:
        utc_dt = pytz.utc.localize(utc_dt)
        
    return utc_dt.astimezone(thai_tz)

# 4. ลงทะเบียนฟังก์ชันให้เป็น filter ของ Jinja2
# **บรรทัดนี้สำคัญมาก!**
app.jinja_env.filters['thai_time'] = to_thai_timezone

@app.route("/reports")

def reports():
    users = query_user_approvals()        # 🟢 ใช้ฟังก์ชันใหม่
    return render_template(
        "reports.html",
        users=users,
        status_titles=TITLES,
        status_label=status_label,
        status_color=status_color,
    )

def to_thai_timezone(utc_dt):
    # ... (โค้ดฟังก์ชันแปลงเวลา) ...
    if not utc_dt or not isinstance(utc_dt, datetime):
        return None 
    thai_tz = pytz.timezone('Asia/Bangkok')
    if utc_dt.tzinfo is None:
        utc_dt = pytz.utc.localize(utc_dt)
    return utc_dt.astimezone(thai_tz)

# 🛑 ต้องมีบรรทัดนี้: ลงทะเบียนฟิลเตอร์
app.jinja_env.filters['thai_time'] = to_thai_timezone




# ---------- สร้างฟังก์ชันแปลงคณะ ----------
FACULTY_MAP = {
    "engineering-industrial-tech": "วิศวกรรมศาสตร์และเทคโนโลยีอุตสาหกรรม",
    "science-health-tech":        "วิทยาศาสตร์และเทคโนโลยีสุขภาพ",
    "agri-tech":                  "เทคโนโลยีการเกษตร",
    "liberal-arts":               "ศิลปศาสตร์",
    "edu-innovation":             "ศึกษาศาสตร์และนวัตกรรมการศึกษา",
    "management-science":         "บริหารศาสตร์",
}

@app.template_filter("faculty_th")
def faculty_th(code):
    """แปลงรหัสคณะ ➜ ชื่อภาษาไทย"""
    return FACULTY_MAP.get(code, "ไม่ระบุคณะ")



@app.route('/user/login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            # บันทึก session
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role

            # 🔁 ไปหน้า dashboard
            return redirect(url_for('user_dashboard'))
        
        return "❌ ชื่อผู้ใช้หรือรหัสผ่านผิด กรุณาลองใหม่"

    return render_template('user_login.html')  # ใช้ template ให้ถูกต้อง

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))  # ดึงข้อมูลผู้ใช้จากฐานข้อมูลโดยใช้ ID

# (สันนิษฐานว่าคุณ import db, User, session, render_template, redirect, url_for ไว้แล้ว)

# --- 1. ย้าย MAP ของคุณออกมาไว้นอกฟังก์ชัน ---
# (นี่คือ faculty_map เดิมของคุณ ย้ายออกมาและเปลี่ยนเป็นตัวพิมพ์ใหญ่)
FACULTY_MAP = {
    "engineering-industrial-tech": "วิศวกรรมศาสตร์และเทคโนโลยีอุตสาหกรรม",
    "science-health-tech": "วิทยาศาสตร์และเทคโนโลยีสุขภาพ",
    "agri-tech": "เทคโนโลยีการเกษตร",
    "liberal-arts": "ศิลปศาสตร์",
    "edu-innovation": "ศึกษาศาสตร์และนวัตกรรมการศึกษา",
    "management-science": "บริหารศาสตร์"
}

# --- 2. สร้าง MAP สำหรับตำแหน่งใหม่ (วางไว้ใกล้กัน) ---
POSITION_MAP = {
    'lecturer': 'อาจารย์',
    'assistant_professor': 'ผู้ช่วยศาสตราจารย์',
    'associate_professor': 'รองศาสตราจารย์',
    'professor': 'ศาสตราจารย์'
}


@app.route('/dashboard')
def user_dashboard():
    user_id = session.get('user_id')
    if user_id:
        user = User.query.get(user_id)

        # --- ส่วนเดิมของคุณ (ยังทำงานเหมือนเดิม) ---
        name_parts = user.full_name.strip().split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        # --- ส่วนเดิมของคุณ (ปรับปรุงเล็กน้อย) ---
        # ใช้ FACULTY_MAP ที่อยู่ข้างนอกฟังก์ชัน
        faculty_th = FACULTY_MAP.get(user.faculty, "ไม่ระบุคณะ")

        # --- 3. ส่วนใหม่ที่เพิ่มเข้ามา ---
        # ดึงข้อมูลตำแหน่งจากฐานข้อมูล แล้วแปลเป็นภาษาไทย
        position_th = POSITION_MAP.get(user.position, "ไม่ระบุตำแหน่ง")

        # --- 4. เพิ่ม position เข้าไปใน render_template ---
        return render_template(
            'user_dashboard.html',
            username=user.username,
            first_name=first_name,      # ส่วนเดิม
            last_name=last_name,        # ส่วนเดิม
            faculty=faculty_th,         # ส่วนเดิม
            position=position_th        # <-- ส่วนที่เพิ่มใหม่
        )

    # (ส่วนเดิมของคุณ)
    return redirect(url_for('user_login'))



#เปลี่ยนรหัส user
@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        old_password = request.form['old_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        # ✅ ตรวจสอบว่ารหัสผ่านเก่าถูกต้อง
        if user.password != old_password:
            flash("❌ รหัสผ่านเดิมไม่ถูกต้อง!", "danger")
            return redirect(url_for('change_password'))

        # ✅ ตรวจสอบว่ารหัสผ่านใหม่ตรงกัน
        if new_password != confirm_password:
            flash("❌ รหัสผ่านใหม่และยืนยันรหัสผ่านไม่ตรงกัน!", "danger")
            return redirect(url_for('change_password'))

        # ✅ อัปเดตรหัสผ่านใหม่
        user.password = new_password
        db.session.commit()

        flash("✅ เปลี่ยนรหัสผ่านสำเร็จ!", "success")
        return redirect(url_for('user_dashboard'))

    return render_template('change_password.html')




# routes.py
# ❗️ อย่าลืม import emit จาก flask_socketio ไว้ที่ด้านบนของไฟล์ด้วย
# ❗️ อย่าลืม import ที่จำเป็นไว้ด้านบนของไฟล์
# ❗️ อย่าลืม import ที่จำเป็นไว้ด้านบนของไฟล์
from flask_socketio import emit
import time

@app.route("/step_comment/<int:step_id>", methods=["POST"])
@login_required
def step_comment(step_id):
    data = request.get_json() or {}
    text = (data.get("comment") or "").strip()

    step = WorkflowStep.query.get_or_404(step_id)
    step.comment = text
    db.session.commit()

    # --- ▼▼▼ เริ่มกระบวนการสืบสวนหา User ID ▼▼▼ ---
    print(f"\n--- 📝 DEBUGGING REAL-TIME COMMENT FOR STEP {step.id} ---")
    user = None

    # วิธีที่ 1: หาจากความสัมพันธ์โดยตรง (step.user)
    if hasattr(step, 'user') and step.user:
        user = step.user
        print(f"  [1] พบผู้ใช้โดยตรงผ่าน step.user -> User ID: {user.id}")
    else:
        print("  [1] ไม่พบความสัมพันธ์ 'user' ใน 'WorkflowStep' โดยตรง")

    # --- ตรวจสอบผลลัพธ์และส่งสัญญาณ ---
    if user:
        room_name = f'timeline-{user.id}'
        data_to_send = {'step_id': step.id, 'text': text}
        socketio.emit('comment_update', data_to_send, room=room_name)
        print(f"✅ SUCCESS: ส่งอัปเดตไปยังห้อง '{room_name}' เรียบร้อย")
    else:
        print(f"❌ FAILED: ไม่สามารถหาผู้ใช้สำหรับ Step {step.id} ได้! ข้ามการส่งอัปเดตเรียลไทม์")
    
    print("--- END DEBUG ---")
    # --- ▲▲▲ จบกระบวนการสืบสวน ▲▲▲ ---

    return jsonify(success=True)










@app.route('/status')
def status():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('user_login'))

    user = User.query.get_or_404(user_id)

    # สร้าง workflow ขั้นตอนถ้ายังไม่มี
    ensure_workflow(user.id)
    # อัปเดต visibility ตามโหวตขั้น 9
    recalc_after_vote(user.id)

    # ดึงขั้นตอนที่ is_visible=True
    steps = (WorkflowStep.query
             .filter_by(user_id=user.id, is_visible=True)
             .order_by(WorkflowStep.order_no)
             .all())

    # เติมคุณสมบัติ show_time
    for st in steps:
        st.show_time = st.order_no in SHOW_TIME_STEPS
        
    position_th = POSITION_MAP.get(user.position, "ไม่ระบุตำแหน่ง")

    # แปลงชื่อคณะ
    faculty_map = {
        "engineering-industrial-tech": "วิศวกรรมศาสตร์และเทคโนโลยีอุตสาหกรรม",
        "science-health-tech":        "วิทยาศาสตร์และเทคโนโลยีสุขภาพ",
        "agri-tech":                  "เทคโนโลยีการเกษตร",
        "liberal-arts":               "ศิลปศาสตร์",
        "edu-innovation":             "ศึกษาศาสตร์และนวัตกรรมการศึกษา",
        "management-science":         "บริหารศาสตร์",
    }
    faculty_th = faculty_map.get(user.faculty, "ไม่ระบุคณะ")

    return render_template(
        "status.html",
        username=user.username,
        user=user,
        position=position_th,
        first_name=user.first_name,
        last_name=user.last_name,
        faculty=faculty_th,       
        email=user.email,
        role=user.role,
        phone=user.phone,
        
        steps=steps   # ส่ง list[WorkflowStep] ที่มี st.show_time แล้ว
    )

bangkok_tz = pytz.timezone("Asia/Bangkok")

# Template Filter สำหรับแปลงเวลาในไฟล์ HTML
@app.template_filter("th_time")
def th_time(dt, fmt="%d/%m/%Y %H:%M"):
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    # ▼▼▼ หัวใจของการแปลงเวลาอยู่ตรงนี้ ▼▼▼
    return dt.astimezone(bangkok_tz).strftime(fmt)








@app.route('/help')
def help():
    return render_template('help.html')

from datetime import datetime

SHOW_TIME_STEPS = {1, 3, 5, 7, 9, 12, 13}   # ขั้นที่ต้องโชว์เวลา



@app.route("/timeline/<int:user_id>", endpoint="timeline")
def timeline(user_id):
    user = User.query.get_or_404(user_id)

    # ---------- สร้างขั้นถ้ายังไม่มี ----------
    ensure_workflow(user.id)

    # ---------- คำนวณสถานะ visibility ใหม่ ตามโหวตขั้น 9 ----------
    recalc_after_vote(user.id)   # <- เติมบรรทัดนี้ เข้าไปก่อน query

    # ---------- ดึงเฉพาะขั้นที่อนุญาตให้โชว์ ----------
    steps = (WorkflowStep.query
             .filter_by(user_id=user.id, is_visible=True)
             .order_by(WorkflowStep.order_no)
             .all())

    # ★★ เติมคุณสมบัติชั่วคราวให้แต่ละ step ★★
    for st in steps:
        st.show_time = st.order_no in SHOW_TIME_STEPS  # True / False

    # ---------- ชื่อคณะภาษาไทย ----------
    FAC_MAP = {
        "engineering-industrial-tech": "วิศวกรรมศาสตร์และเทคโนโลยีอุตสาหกรรม",
        "science-health-tech": "วิทยาศาสตร์และเทคโนโลยีสุขภาพ",
        "agri-tech": "เทคโนโลยีการเกษตร",
        "liberal-arts": "ศิลปศาสตร์",
        "edu-innovation": "ศึกษาศาสตร์และนวัตกรรมการศึกษา",
        "management-science": "บริหารศาสตร์"
    }
    
    
    POSITION_MAP = {
    'lecturer': 'อาจารย์',
    'assistant_professor': 'ผู้ช่วยศาสตราจารย์',
    'associate_professor': 'รองศาสตราจารย์',
    'professor': 'ศาสตราจารย์'
}
    
    position_th = POSITION_MAP.get(user.position, "ไม่ระบุตำแหน่ง")
    faculty_th = FAC_MAP.get(user.faculty, "ไม่ระบุคณะ")

    return render_template(
        "timeline.html",
        user=user,
        position_th=position_th,
        faculty_th=faculty_th,
        steps=steps,    # ตอนนี้ DB ถูกกรอง is_visible มาแล้ว
    )
    




@app.route('/admin_dashboard')
def admin_dashboard():
    return render_template('admin_dashboard.html')





@app.route('/register', methods=['GET', 'POST'])
def register_user():
    if request.method == 'POST':
        
        print("DEBUG FORM:", request.form.to_dict())
        # ----- ดึงค่าจากฟอร์ม -----
        username   = request.form['username'].strip()
        raw_pass   = request.form['password']         #  ❗ ใช้เหมือนเดิม
        email      = request.form['email'].lower().strip()
        first_name = request.form['first_name'].strip()
        last_name  = request.form['last_name'].strip()
        faculty    = request.form['faculty']
        phone = request.form.get('phone', '').strip()   # ปลอดภัย ไม่โยน KeyError
        position = request.form.get('position')


        # ----- ตรวจซ้ำ -----
        if User.query.filter_by(username=username).first():
            return "❌ ชื่อผู้ใช้นี้มีอยู่แล้ว"
        if User.query.filter_by(email=email).first():
            return "❌ อีเมลนี้มีอยู่แล้ว"
        if User.query.filter_by(phone=phone).first():
            return "❌ เบอร์โทรนี้มีอยู่แล้ว"

        # ----- ตรวจรูปแบบเบอร์ -----
        if not PHONE_PATTERN.match(phone):
            return "❌ เบอร์โทรไม่ถูกต้อง (ต้องขึ้นต้น 0 และยาว 9–10 หลัก)"

        # ----- สร้าง record -----
        new_user = User(
            username   = username,
            password   = raw_pass,                      # ใช้ดิบเหมือนเดิม
            first_name = first_name,
            last_name  = last_name,
            full_name  = f"{first_name} {last_name}".strip(),
            faculty    = faculty,
            email      = email,
            phone      = phone,   
            position   = position,
            role       = 'user'
            
        )

        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('user_login'))

    # ----- GET -----
    return render_template('register_user.html')


#ตัวพวกออปชั่นข้อความ
# app.py  หรือ blueprint admin.py


# ----------------------------
#  /admin/contact/reply
# ----------------------------
@app.route('/admin/contact/reply', methods=['GET', 'POST'])
def reply_contact():
    if not session.get("admin"):
        flash("คุณไม่มีสิทธิ์", "danger")
        return redirect(url_for("admin_login", next=request.path))

    # ---------- POST ----------
    if request.method == "POST":
        msg_id = request.form["msg_id"]
        body   = request.form["body"].strip()

        # ✅ ดึงรหัสผู้ดูแลจาก session (หรือ current_user.id ก็ได้ถ้าใช้ Flask-Login)
        admin_id = session.get('user_id')          # <----- สำคัญ!

        db.session.add(ContactReply(
            contact_id = msg_id,
            body       = body,
            admin_id   = admin_id                  # <----- บันทึกลง DB
        ))
        db.session.commit()

        flash("บันทึกตอบกลับแล้ว", "success")
        return redirect(url_for("reply_contact", msg_id=msg_id))

    # ---------- GET ----------
    msg_id  = request.args.get("msg_id", type=int)
    msg     = ContactMessage.query.get_or_404(msg_id)
    replies = (msg.replies
                  .order_by(ContactReply.created_at.asc())
                  .all())
    return render_template("admin_reply.html", msg=msg, replies=replies)




@app.route('/user/reply/<int:msg_id>', methods=['POST'])
def user_reply(msg_id):
    if 'user_id' not in session:
        flash("❌ กรุณาล็อกอินก่อน", "danger")
        return redirect(url_for('user_login'))

    msg = ContactMessage.query.get_or_404(msg_id)

    # ป้องกันไม่ให้ตอบของคนอื่น
    if msg.user_id != session['user_id']:
        flash("❌ คุณไม่มีสิทธิ์ตอบกลับข้อความนี้", "danger")
        return redirect(url_for('user_replies'))

    body = request.form.get('body', '').strip()
    if not body:
        flash("❌ กรุณากรอกข้อความ", "danger")
        return redirect(url_for('user_replies'))

    db.session.add(ContactReply(contact_id=msg.id, body=body))
    db.session.commit()

    flash("✅ ส่งตอบกลับแล้ว", "success")
    return redirect(url_for('user_replies'))





##ลบผู้ใช้
# ─── decorator ง่าย ๆ ───
from functools import wraps
def admin_only(f):
    @wraps(f)
    def wrap(*a, **kw):
        if session.get('admin'):
            return f(*a, **kw)
        flash('คุณไม่มีสิทธิ์', 'danger')
        return redirect(url_for('admin_login', next=request.path))
    return wrap


@app.route('/admin/contact/<int:msg_id>/delete', methods=['POST'])
@admin_only               # หรือ @login_required ถ้ากลับไปใช้ Flask-Login
def delete_contact(msg_id):
    msg = ContactMessage.query.get_or_404(msg_id)

    db.session.delete(msg)
    db.session.commit()

    flash("🗑️ ลบข้อความแล้ว", "success")

    # 🟢 ต้องมี return เสมอ
    return redirect(url_for('admin_contact'))




@app.route('/user/replies')
def user_replies():
    # ตรวจสอบว่า session มีข้อมูล user_id หรือไม่
    if not session.get('user_id'):
        flash("❌ กรุณาล็อกอินก่อน", "danger")
        return redirect(url_for('user_login'))  # เปลี่ยนเส้นทางไปหน้า login

    # ดึงข้อความที่ผู้ใช้ส่ง
    msgs = (ContactMessage.query
            .filter_by(user_id=session['user_id'])  # ใช้ session['user_id'] แทน current_user.id
            .order_by(ContactMessage.created_at.desc())
            .all())

    # ส่งข้อมูลไปยัง template
    return render_template(
        'user_replies.html',
        msgs=msgs,
        ContactReply=ContactReply
    )







# app.py
@app.after_request
def add_no_cache_headers(resp):
    resp.headers['Cache-Control'] = (
        'no-store, no-cache, must-revalidate, max-age=0')
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp






@app.route('/admin_logout')
def admin_logout():
    session.clear()
    try:
        logout_user()
    except Exception:
        pass
    return redirect(url_for('admin_login'))





@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('user_login'))





if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # ▼▼▼ ต้องเหลือแค่บรรทัดนี้ เพื่อเปิดโหมดเรียลไทม์ ▼▼▼
    socketio.run(app, debug=True)
    

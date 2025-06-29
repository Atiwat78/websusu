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
from datetime import timezone         # ← เพิ่มบรรทัดนี้













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







app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # 🔐 ใส่ค่านี้หลัง app = Flask(...)


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'data.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)



class AcademicRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    position_requested = db.Column(db.String(100), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    first_name = db.Column(db.String(80))
    last_name  = db.Column(db.String(80))
    faculty = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    role = db.Column(db.String(20), default='user')
    requests = db.relationship('AcademicRequest', backref='user')  # relationship ใช้ชื่อ class ที่อยู่ข้างบน
    
class WorkflowStep(db.Model):
    id        = db.Column(db.Integer, primary_key=True)
    user_id   = db.Column(db.Integer, db.ForeignKey('user.id'))
    order_no  = db.Column(db.Integer)         # 1-13
    title     = db.Column(db.String(150))
    is_done   = db.Column(db.Boolean, default=False)
    done_at   = db.Column(db.DateTime)
    comment   = db.Column(db.Text)
    is_visible = db.Column(db.Boolean, default=True)   
    
    
class ExpertVote(db.Model):
    __tablename__ = "expert_vote"

    id       = db.Column(db.Integer, primary_key=True)
    step_id  = db.Column(db.Integer, db.ForeignKey("workflow_step.id"))
    idx      = db.Column(db.Integer)      # 0-2  (ผู้ทรง 1-3)
    approved = db.Column(db.Boolean)      # True/False/None
    step     = db.relationship("WorkflowStep",
                               backref=db.backref("experts", lazy="dynamic"))


    


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



#การติกสถานะ
@app.post("/toggle_step/<int:step_id>")
def toggle_step(step_id):
    data = request.get_json()
    done = bool(data.get("done"))

    step = WorkflowStep.query.get_or_404(step_id)
    step.is_done = done

    # ถ้า step นี้ต้องโชว์เวลา
    if done and step.order_no in {1,3,5,7,9,12,13}:
        step.done_at = datetime.utcnow()      # หรือ datetime.now()
    else:
        step.done_at = None

    db.session.commit()

    return jsonify(
        success=True,
        done_at = step.done_at.strftime("%d/%m/%Y %H:%M") if step.done_at else ""
    )




# เข้าสู่ระบบแอดมิน
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # ✅ อนุญาตเฉพาะ admin/admin999
        if username == 'admin' and password == 'admin999':
            session.clear()
            session['username'] = 'admin'
            session['admin'] = True
            session['role']     = 'admin'
            return redirect(url_for('admin_dashboard'))

        flash("❌ เฉพาะผู้ดูแลระบบเท่านั้นที่เข้าสู่ระบบนี้ได้", "danger")

    return render_template('admin_login.html')


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
        user.email      = request.form['email']
        user.faculty    = request.form['faculty']
        db.session.commit()
        flash("✅ แก้ไขผู้ใช้เรียบร้อยแล้ว", "success")
        return redirect(url_for('manage_users'))

    return render_template('edit_user.html', user=user)




@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')  # ✅ สำคัญ! ต้องมีบรรทัดนี้
        password = request.form.get('password')
        role = request.form.get('role', 'user')

        # เช็กซ้ำว่าไม่มี user/email ซ้ำ
        existing_user = User.query.filter_by(username=username).first()
        existing_email = User.query.filter_by(email=email).first()

        if existing_user:
            flash("❌ ชื่อผู้ใช้นี้ถูกใช้ไปแล้ว!", "danger")
            return redirect(url_for('add_user'))
        if existing_email:
            flash("❌ อีเมลนี้ถูกใช้ไปแล้ว!", "danger")
            return redirect(url_for('add_user'))

        # ✅ ต้องใส่ email ตรงนี้ด้วย
        new_user = User(username=username, email=email, password=password, role=role)
        db.session.add(new_user)
        db.session.commit()

        flash("✅ เพิ่มผู้ใช้สำเร็จ!", "success")
        return redirect(url_for('manage_users'))

    return render_template('add_user.html')




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







@app.route('/admin/contact')
def admin_contact():
    if 'admin' not in session or not session.get('admin'):
        flash("❌ คุณไม่มีสิทธิ์เข้าถึงหน้านี้", "danger")
        return redirect(url_for('admin_login'))  # ถ้าไม่ใช่แอดมิน ให้ไปหน้า login

    messages = ContactMessage.query.all()
    return render_template('admin_contact.html', messages=messages)





@app.route('/reports')
def reports():
    if 'admin' not in session:
        flash("❌ คุณไม่มีสิทธิ์เข้าถึงหน้านี้!", "danger")
        return redirect(url_for('admin_login'))
    return render_template(
        'reports.html',
      
    )

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

    return render_template('user_login.html')





@app.route('/dashboard')
def user_dashboard():
    user_id = session.get('user_id')
    if user_id:
        user = User.query.get(user_id)

        name_parts = user.full_name.strip().split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        faculty_map = {
            "engineering-industrial-tech": "วิศวกรรมศาสตร์และเทคโนโลยีอุตสาหกรรม",
            "science-health-tech": "วิทยาศาสตร์และเทคโนโลยีสุขภาพ",
            "agri-tech": "เทคโนโลยีการเกษตร",
            "liberal-arts": "ศิลปศาสตร์",
            "edu-innovation": "ศึกษาศาสตร์และนวัตกรรมการศึกษา",
            "management-science": "บริหารศาสตร์"
        }

        faculty_th = faculty_map.get(user.faculty, "ไม่ระบุคณะ")

        return render_template(
            'user_dashboard.html',
            username=user.username,
            first_name=first_name,
            last_name=last_name,
            faculty=faculty_th
        )
    return redirect(url_for('login'))


@app.route('/status')
def status():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('user_login'))

    user = User.query.get(user_id)

    name_parts = user.full_name.strip().split(" ", 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    faculty_map = {
        "engineering-industrial-tech": "วิศวกรรมศาสตร์และเทคโนโลยีอุตสาหกรรม",
        "science-health-tech": "วิทยาศาสตร์และเทคโนโลยีสุขภาพ",
        "agri-tech": "เทคโนโลยีการเกษตร",
        "liberal-arts": "ศิลปศาสตร์",
        "edu-innovation": "ศึกษาศาสตร์และนวัตกรรมการศึกษา",
        "management-science": "บริหารศาสตร์"
    }

    faculty_th = faculty_map.get(user.faculty, "ไม่ระบุคณะ")

    # 🔁 timeline steps - mock data
    steps = [
        {"title": "ยื่นคำร้อง", "is_done": True, "show_time": True, "done_at": datetime(2025, 6, 20, 9, 0)},
        {"title": "คณะพิจารณา", "is_done": True, "show_time": True, "done_at": datetime(2025, 6, 22, 14, 30)},
        {"title": "ส่งให้กรรมการ", "is_done": False, "show_time": False, "done_at": None},
    ]

    return render_template("status.html",
        username=user.username,
        first_name=first_name,
        last_name=last_name,
        faculty=faculty_th,
        email=user.email,
        role=user.role,
        steps=steps
    )


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
    faculty_th = FAC_MAP.get(user.faculty, "ไม่ระบุคณะ")

    return render_template(
        "timeline.html",
        user=user,
        faculty_th=faculty_th,
        steps=steps,    # ตอนนี้ DB ถูกกรอง is_visible มาแล้ว
    )
    



   
   
   










@app.route('/admin_dashboard')
def admin_dashboard():
    return render_template('admin_dashboard.html')


@app.route('/register', methods=['GET', 'POST'])
def register_user():
    if request.method == 'POST':
        # ---------- ดึงค่าจากฟอร์ม ----------
        username   = request.form['username']
        raw_pass   = request.form['password']      # ← เอาไปเก็บตรง ๆ
        email      = request.form['email']
        first_name = request.form['first_name']
        last_name  = request.form['last_name']
        faculty    = request.form['faculty']

        # ---------- ตรวจซ้ำ ----------
        if User.query.filter_by(username=username).first():
            return "❌ ชื่อผู้ใช้นี้มีอยู่แล้ว กรุณาใช้ชื่ออื่น"
        if User.query.filter_by(email=email).first():
            return "❌ อีเมลนี้มีอยู่แล้ว กรุณาใช้อีเมลอื่น"

        # ---------- สร้าง record ----------
        new_user = User(
            username   = username,
            password   = raw_pass,                     # ⬅ เก็บดิบ ๆ
            first_name = first_name,
            last_name  = last_name,
            full_name  = f"{first_name} {last_name}".strip(),
            faculty    = faculty,
            email      = email,
            role       = 'user'
        )

        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('user_login'))

    # ---------- GET ----------
    return render_template('register_user.html')











@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('user_login'))





if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
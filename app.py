"""美术生文化课特训 v1 — 艺术生专属文化课提分神器 | 完全离线"""
import sqlite3, json, os, random, re, hashlib
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, jsonify, g, session, send_from_directory

app = Flask(__name__)
# 持久化 secret_key，重启不丢登录
_keyfile = os.path.join(os.path.dirname(__file__), '.session_key')
if os.path.exists(_keyfile):
    with open(_keyfile) as f: app.secret_key = f.read()
else:
    app.secret_key = os.urandom(24).hex()
    with open(_keyfile, 'w') as f: f.write(app.secret_key)

# 记住登录 30 天
from datetime import timedelta as td
app.config['PERMANENT_SESSION_LIFETIME'] = td(days=30)
DB = os.path.join(os.path.dirname(__file__), 'study.db')

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db

@app.teardown_appcontext
def close_db(e):
    db = g.pop('db', None)
    if db: db.close()

def q(sql, params=(), one=False):
    cur = get_db().execute(sql, params)
    return cur.fetchone() if one else cur.fetchall()

def ex(sql, params=()):
    db = get_db()
    cur = db.execute(sql, params)
    db.commit()
    return cur.lastrowid

SCHEMA = """
CREATE TABLE IF NOT EXISTS subjects (id INTEGER PRIMARY KEY, name TEXT, icon TEXT, color TEXT);
CREATE TABLE IF NOT EXISTS knowledge_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER, name TEXT, unit TEXT, semester TEXT,
    FOREIGN KEY(subject_id) REFERENCES subjects(id)
);
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kp_id INTEGER, subject_id INTEGER,
    question_text TEXT NOT NULL, answer TEXT NOT NULL,
    accept_answers TEXT, hint TEXT, difficulty INTEGER DEFAULT 1,
    FOREIGN KEY(kp_id) REFERENCES knowledge_points(id)
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE, xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1, streak INTEGER DEFAULT 0,
    max_streak INTEGER DEFAULT 0, last_active_date DATE,
    total_correct INTEGER DEFAULT 0, total_attempts INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS answers_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
    question_id INTEGER, kp_id INTEGER, correct INTEGER,
    user_answer TEXT, xp_earned INTEGER, answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS daily_challenges (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
    challenge_date DATE, subject_id INTEGER, target_count INTEGER DEFAULT 10,
    completed_count INTEGER DEFAULT 0, claimed INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS kp_progress (
    user_id INTEGER, kp_id INTEGER, correct INTEGER DEFAULT 0,
    total INTEGER DEFAULT 0, mastery REAL DEFAULT 0,
    PRIMARY KEY(user_id, kp_id)
);
"""

LEVEL_THRESHOLDS = [0,100,250,500,850,1300,1900,2700,3800,5200,7000,9200,12000,15500,20000,26000,34000,44000,57000,73000]
LEVEL_NAMES = ["铅笔","画板","调色盘","素描","水粉","油画","创作","个展","画廊","收藏家","艺术顾问","策展人","博物馆","艺术节","双年展","威尼斯","文艺复兴","印象派","现代艺术","艺术大师"]

def calc_level(xp):
    for i, t in enumerate(LEVEL_THRESHOLDS):
        if xp < t: return (i, LEVEL_NAMES[i-1] if i>0 else LEVEL_NAMES[0])
    return (len(LEVEL_THRESHOLDS), LEVEL_NAMES[-1])

def calc_xp(diff, streak, correct):
    if not correct: return 0
    return {1:10,2:20,3:35}[diff] + min(streak,10)*2

with app.app_context():
    get_db().executescript(SCHEMA)
    # Ensure subjects exist
    for sid, nm, ic, cl in [
        (1,'语文','📖','#e74c3c'),(2,'数学','📐','#3498db'),
        (3,'英语','🌍','#2ecc71'),(4,'政治','⚖️','#f39c12'),
        (5,'历史','📜','#9b59b6'),(6,'地理','🌏','#1abc9c')
    ]:
        ex("INSERT OR IGNORE INTO subjects (id,name,icon,color) VALUES (?,?,?,?)", [sid,nm,ic,cl])
    get_db().commit()

# ═══════════════════════ PWA ═══════════════════════
@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json',
        mimetype='application/manifest+json')

@app.route('/sw.js')
def sw():
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')

@app.route('/app-release.apk')
def download_apk():
    """从 static 目录下载最新 APK（国内安卓手机可直接安装）"""
    return send_from_directory('static', '上瘾学习-offline-v1.apk',
        mimetype='application/vnd.android.package-archive',
        as_attachment=True, download_name='上瘾学习-offline-v1.apk')

# ═══════════════════════ ROUTES ═══════════════════════
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/register', methods=['POST'])
def api_register():
    name = request.json.get('username','').strip()
    if not name or len(name)>20: return jsonify({'error':'昵称1-20字'}),400
    # 已存在 → 直接登录
    u = q("SELECT * FROM users WHERE username=?",[name],one=True)
    if u:
        session.permanent = True
        session['uid']=u['id']; session['username']=u['username']
        lv,ln = calc_level(u['xp'])
        return jsonify({'id':u['id'],'username':u['username'],'xp':u['xp'],'level':lv,'level_name':ln})
    try:
        uid = ex("INSERT INTO users (username) VALUES (?)",[name])
        lv,ln = calc_level(0)
        session.permanent = True
        session['uid']=uid; session['username']=name
        return jsonify({'id':uid,'username':name,'xp':0,'level':lv,'level_name':ln})
    except: return jsonify({'error':'昵称已存在'}),409

@app.route('/api/me')
def api_me():
    uid = session.get('uid')
    if not uid: return jsonify({'logged_in':False})
    u = q("SELECT * FROM users WHERE id=?",[uid],one=True)
    if not u: return jsonify({'logged_in':False})
    lv,ln = calc_level(u['xp'])
    today = date.today().isoformat()
    ch = q("SELECT * FROM daily_challenges WHERE user_id=? AND challenge_date=?",[uid,today],one=True)
    return jsonify({
        'logged_in':True,'id':u['id'],'username':u['username'],
        'xp':u['xp'],'level':lv,'level_name':ln,
        'xp_next':LEVEL_THRESHOLDS[lv] if lv<len(LEVEL_THRESHOLDS) else None,
        'xp_current':LEVEL_THRESHOLDS[lv-1] if lv>0 else 0,
        'streak':u['streak'],'max_streak':u['max_streak'],
        'total_correct':u['total_correct'],'total_attempts':u['total_attempts'],
        'daily_challenge':dict(ch) if ch else None
    })

@app.route('/api/subjects')
def api_subjects():
    return jsonify([dict(r) for r in q("SELECT * FROM subjects ORDER BY id")])

@app.route('/api/knowledge-points')
def api_knowledge_points():
    sid = request.args.get('subject_id','')
    semester = request.args.get('semester','')
    base = """SELECT kp.*, s.name as subject_name, s.icon, s.color,
              COUNT(q.id) as question_count
              FROM knowledge_points kp
              JOIN subjects s ON kp.subject_id=s.id
              LEFT JOIN questions q ON q.kp_id=kp.id"""
    conds = ["1=1"]; params = []
    if sid: conds.append("kp.subject_id=?"); params.append(sid)
    if semester: conds.append("kp.semester=?"); params.append(semester)
    rows = q(f"{base} WHERE {' AND '.join(conds)} GROUP BY kp.id ORDER BY s.id, kp.unit, kp.name", params)
    # Add user progress
    uid = session.get('uid')
    result = []
    for r in rows:
        d = dict(r)
        if uid:
            p = q("SELECT * FROM kp_progress WHERE user_id=? AND kp_id=?",[uid,r['id']],one=True)
            d['mastery'] = round(p['mastery'],1) if p else 0
            d['done'] = p['correct'] if p else 0
            d['total_done'] = p['total'] if p else 0
        else:
            d['mastery'] = 0; d['done'] = 0; d['total_done'] = 0
        result.append(d)
    return jsonify(result)

@app.route('/api/questions')
def api_questions():
    kp_id = request.args.get('kp_id','')
    subject_id = request.args.get('subject_id','')
    count = int(request.args.get('count',10))
    diff = request.args.get('difficulty','')
    base = "SELECT q.*, kp.name as kp_name, s.name as subject_name FROM questions q JOIN knowledge_points kp ON q.kp_id=kp.id JOIN subjects s ON q.subject_id=s.id WHERE 1=1"
    params = []
    if kp_id: base += " AND q.kp_id=?"; params.append(kp_id)
    if subject_id: base += " AND q.subject_id=?"; params.append(subject_id)
    if diff: base += " AND q.difficulty=?"; params.append(int(diff))
    rows = q(base + " ORDER BY RANDOM() LIMIT ?", params + [count])
    return jsonify([dict(r) for r in rows])

@app.route('/api/answer', methods=['POST'])
def api_answer():
    uid = session.get('uid')
    if not uid: return jsonify({'error':'请先注册'}),401
    d = request.json
    qid, user_ans = d['question_id'], d['answer'].strip().upper()
    question = q("SELECT * FROM questions WHERE id=?",[qid],one=True)
    if not question: return jsonify({'error':'题目不存在'}),404
    # Choice mode: compare against correct_option
    is_correct = (user_ans == question['correct_option'].strip().upper()) if (question['correct_option'] and question['correct_option'].strip()) else (user_ans.lower() == question['answer'].strip().lower())

    user = q("SELECT * FROM users WHERE id=?",[uid],one=True)
    today = date.today(); yesterday = today - timedelta(days=1)
    streak = user['streak']
    if user['last_active_date']:
        last = date.fromisoformat(user['last_active_date'])
        if last == yesterday: streak += (1 if is_correct else 0)
        elif last != today: streak = (1 if is_correct else 0)
    else: streak = (1 if is_correct else 0)
    max_streak = max(user['max_streak'], streak)
    xp_e = calc_xp(question['difficulty'], streak, is_correct)

    ex("""UPDATE users SET xp=xp+?, streak=?, max_streak=?,
          last_active_date=?, total_attempts=total_attempts+1,
          total_correct=total_correct+? WHERE id=?""",
       [xp_e, streak, max_streak, today.isoformat(), 1 if is_correct else 0, uid])
    ex("INSERT INTO answers_log (user_id,question_id,kp_id,correct,user_answer,xp_earned) VALUES (?,?,?,?,?,?)",
       [uid, qid, question['kp_id'], 1 if is_correct else 0, user_ans, xp_e])

    # KP progress
    kp = q("SELECT * FROM kp_progress WHERE user_id=? AND kp_id=?",[uid,question['kp_id']],one=True)
    if kp:
        new_total = kp['total']+1; new_correct = kp['correct']+(1 if is_correct else 0)
        ex("UPDATE kp_progress SET correct=?, total=?, mastery=? WHERE user_id=? AND kp_id=?",
           [new_correct, new_total, round(new_correct/new_total*100,1), uid, question['kp_id']])
    else:
        ex("INSERT INTO kp_progress (user_id,kp_id,correct,total,mastery) VALUES (?,?,?,?,?)",
           [uid, question['kp_id'], 1 if is_correct else 0, 1, 100 if is_correct else 0])

    # Daily challenge
    chal = q("SELECT * FROM daily_challenges WHERE user_id=? AND challenge_date=?",[uid,today.isoformat()],one=True)
    if not chal:
        subj = random.choice([1,2,3,4,5,6])
        ex("INSERT INTO daily_challenges (user_id,challenge_date,subject_id,target_count) VALUES (?,?,?,?)",
           [uid,today.isoformat(),subj,10])
    if is_correct:
        ex("UPDATE daily_challenges SET completed_count=completed_count+1 WHERE user_id=? AND challenge_date=?",
           [uid,today.isoformat()])

    user2 = q("SELECT * FROM users WHERE id=?",[uid],one=True)
    lv,ln = calc_level(user2['xp']); old_lv,_ = calc_level(user['xp'])
    return jsonify({
        'correct':is_correct,'correct_answer':question['answer'],
        'xp_earned':xp_e,'streak':streak,'max_streak':max_streak,
        'level':lv,'level_name':ln,'level_up':lv>old_lv,
        'total_xp':user2['xp'],
        'xp_next':LEVEL_THRESHOLDS[lv] if lv<len(LEVEL_THRESHOLDS) else None,
        'xp_current':LEVEL_THRESHOLDS[lv-1] if lv>0 else 0
    })

@app.route('/api/leaderboard')
def api_leaderboard():
    rows = q("""SELECT username, xp, level, streak, total_correct, total_attempts,
                ROUND(CAST(total_correct AS FLOAT)/MAX(total_attempts,1)*100) as accuracy
                FROM users ORDER BY xp DESC LIMIT 20""")
    return jsonify([dict(r) for r in rows])

@app.route('/api/daily-bonus', methods=['POST'])
def api_daily_bonus():
    uid = session.get('uid')
    if not uid: return jsonify({'error':'请先注册'}),401
    today = date.today().isoformat()
    chal = q("SELECT * FROM daily_challenges WHERE user_id=? AND challenge_date=?",[uid,today],one=True)
    if not chal: return jsonify({'error':'没有今日挑战'}),400
    if chal['claimed']: return jsonify({'error':'已领取'}),400
    if chal['completed_count'] < chal['target_count']:
        return jsonify({'error':f'还需{chal["target_count"]-chal["completed_count"]}题'}),400
    bonus = 50
    ex("UPDATE users SET xp=xp+? WHERE id=?",[bonus,uid])
    ex("UPDATE daily_challenges SET claimed=1 WHERE id=?",[chal['id']])
    user = q("SELECT * FROM users WHERE id=?",[uid],one=True)
    lv,ln = calc_level(user['xp'])
    return jsonify({'bonus':bonus,'total_xp':user['xp'],'level':lv,'level_name':ln})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)

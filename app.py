import os, json
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models import db, User, Category, Item, Task, Comment, InventoryLog, WeeklyCount, Feedback, Idea, KakaoEvent, CostRecord, Performance, Attachment, ChecklistItem, Notification, RolePermission, Role

app = Flask(__name__)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# .env 파일에서 환경변수 로드
_env_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(_env_path):
    with open(_env_path) as _ef:
        for _line in _ef:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())
if os.environ.get('ANTHROPIC_API_KEY'):
    app.config['ANTHROPIC_API_KEY'] = os.environ['ANTHROPIC_API_KEY']

# 보안: SECRET_KEY (환경변수 우선, 없으면 랜덤 생성)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or os.urandom(32).hex()

# DB 설정: DATABASE_URL 환경변수가 있으면 PostgreSQL, 없으면 SQLite 폴백
DATABASE_URL = os.environ.get('DATABASE_URL', '')
if DATABASE_URL:
    # Heroku/Koyeb 호환: postgres:// → postgresql://
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
else:
    DB_PATH = os.path.join(BASE_DIR, 'goods_pm_new.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = '로그인이 필요합니다.'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ═══════════════════════════════════════════
# SEED DATA
# ═══════════════════════════════════════════
def seed_database():
    if User.query.first():
        return
    # 7 users
    users_data = [
        ('director', '소장', '소장', 'director@positive.co.kr'),
        ('editor', '편집장', '편집장', 'editor@positive.co.kr'),
        ('planner', '실무자', '실무자', 'planner@positive.co.kr'),
        ('designer', '디자이너', '디자이너', 'designer@positive.co.kr'),
        ('admin_mgr', '행정팀장', '행정팀장', 'admin@positive.co.kr'),
        ('sub_mgr1', '구독매니저1', '구독매니저1', 'submgr1@positive.co.kr'),
        ('sub_mgr2', '구독매니저2', '구독매니저2', 'submgr2@positive.co.kr'),
    ]
    users = {}
    for uname, name, role, email in users_data:
        u = User(username=uname, password_hash=generate_password_hash('1234'),
                 name=name, role=role, email=email)
        db.session.add(u)
        users[role] = u
    db.session.flush()

    # Categories
    cats_data = ['노트류','생활용품','지류','아트','명언집','캐릭터 굿즈','달력/일력']
    cats = {}
    for c in cats_data:
        cat = Category(name=c)
        db.session.add(cat)
        cats[c] = cat
    db.session.flush()

    # Items: (name, line, cat, cost, target_qty, stock, status, owner, target_date, smartstore, aengdu, usage)
    #   target_qty = 입고 수량 (100%), stock = 현재 잔여 수량
    #   네이밍 룰: [주체] [카테고리] [이름] [변형] [버전]
    items_data = [
        # ── 수건 (구독선물용 6색 + 판매용 3종세트) ──
        ('좋은생각 수건 연핑크', 'A', '생활용품', 3510, 500, 250, '소진중', '구독매니저1', None, None, None, '구독선물'),
        ('좋은생각 수건 민트', 'A', '생활용품', 3510, 500, 250, '소진중', '구독매니저1', None, None, None, '구독선물'),
        ('좋은생각 수건 보라', 'A', '생활용품', 3510, 500, 250, '소진중', '구독매니저1', None, None, None, '구독선물'),
        ('좋은생각 수건 핑크', 'A', '생활용품', 3510, 500, 250, '소진중', '구독매니저1', None, None, None, '구독선물'),
        ('좋은생각 수건 화이트', 'A', '생활용품', 3510, 500, 250, '소진중', '구독매니저1', None, None, None, '구독선물'),
        ('좋은생각 수건 블루', 'A', '생활용품', 3510, 500, 250, '소진중', '구독매니저1', None, None, None, '구독선물'),
        ('좋은생각 수건 3종세트', 'A', '생활용품', 3510, 200, 100, '판매중', '구독매니저1', None, None, None, '판매'),
        # ── 다이어리 ──
        ('좋은생각 다이어리 보라', 'A', '노트류', 3063, 2000, 1900, '소진중', '구독매니저1', None, 'https://smartstore.naver.com/positivethinking', 'https://aengdu.kr/products/upkfcbakb2m9', '구독선물+판매'),
        ('좋은생각 다이어리 파랑', 'A', '노트류', 3063, 2000, 1900, '소진중', '구독매니저1', None, 'https://smartstore.naver.com/positivethinking', 'https://aengdu.kr/products/upkfcbakb2m9', '구독선물+판매'),
        ('좋은생각 다이어리 초록', 'A', '노트류', 3063, 2000, 1900, '소진중', '구독매니저1', None, 'https://smartstore.naver.com/positivethinking', 'https://aengdu.kr/products/upkfcbakb2m9', '구독선물+판매'),
        # ── 명언집 ──
        ('좋은생각 명언집 긍정의한줄', 'A', '명언집', 2717, 3000, 2464, '소진중', '구독매니저1', None, 'https://smartstore.naver.com/positivethinking', 'https://aengdu.kr/products/x47zhyrnuydr', '구독선물+판매'),
        # ── 앞치마 ──
        ('좋은생각 앞치마 노랑', 'A', '생활용품', 8580, 1500, 0, '입고대기', '구독매니저1', date(2026,4,30), None, None, '구독선물'),
        # ── 심봉민 노트 ──
        ('심봉민 노트 조용히쌓인기억', 'B,C', '노트류', 1750, 500, 430, '판매중', '실무자', None, 'https://smartstore.naver.com/positivethinking', 'https://aengdu.kr/products/4hw5x4vw8frn', '판매'),
        ('심봉민 노트 뭉게뭉게피어나는밤', 'B,C', '노트류', 1750, 500, 460, '판매중', '실무자', None, 'https://smartstore.naver.com/positivethinking', 'https://aengdu.kr/products/36ddmcmrw4a5', '판매'),
        ('심봉민 노트 기억이멈춘섬', 'B,C', '노트류', 1750, 500, 480, '판매중', '실무자', None, 'https://smartstore.naver.com/positivethinking', 'https://aengdu.kr/products/dzb9dc36752u', '판매'),
        ('심봉민 노트 나를기다린다롱이', 'B,C', '노트류', 1750, 500, 490, '판매중', '실무자', None, 'https://smartstore.naver.com/positivethinking', 'https://aengdu.kr/products/k5btugqv8mzw', '판매'),
        # ── 다비드자맹 고블렛잔 ──
        ('다비드자맹 고블렛잔 OnJoue 한정판', 'B', '생활용품', 26000, 200, 165, '판매중', '실무자', None, 'https://smartstore.naver.com/positivethinking', 'https://aengdu.kr/products/ddcpvdtez4wh', '판매'),
        # ── 앨리스달튼브라운 노트 ──
        ('앨리스달튼브라운 노트 3종', 'B', '노트류', 1750, 1500, 0, '기획중', '실무자', date(2026,7,15), None, None, '판매'),
        # ── 칭찬노트 ──
        ('좋은생각 노트 칭찬노트 리뉴얼1', 'B,C', '노트류', None, None, 0, '기획중', '실무자', None, None, None, '판매'),
    ]
    items = {}
    for name, line, cat_name, cost, tgt_qty, stock, status, owner_role, tdate, smartstore, aengdu, usage in items_data:
        it = Item(name=name, line=line, category_id=cats[cat_name].id,
                  unit_cost=cost, target_qty=tgt_qty, current_stock=stock, status=status,
                  owner_id=users[owner_role].id, target_date=tdate,
                  sale_url_smartstore=smartstore, sale_url_aengdu=aengdu, usage=usage)
        db.session.add(it)
        items[name] = it
    db.session.flush()

    # Tasks for 앨리스달튼브라운 노트 (5단계)
    alice = items['앨리스달튼브라운 노트 3종']
    tasks_data = [
        ('앨리스 노트 기획', '기획', '대기', date(2026,4,1), date(2026,4,30), '실무자', '높음'),
        ('앨리스 노트 디자인', '디자인', '대기', date(2026,5,1), date(2026,5,21), '디자이너', '보통'),
        ('앨리스 노트 컨펌/견적', '컨펌/견적', '대기', date(2026,5,22), date(2026,5,28), '실무자', '보통'),
        ('앨리스 노트 제작발주', '제작', '대기', date(2026,5,29), date(2026,6,25), '실무자', '보통'),
        ('앨리스 노트 입고확인', '입고', '대기', date(2026,7,15), date(2026,7,15), '행정팀장', '보통'),
    ]
    for title, stage, status, start, due, owner_role, priority in tasks_data:
        t = Task(title=title, item_id=alice.id, stage=stage, status=status,
                 start_date=start, due_date=due, assignee_id=users[owner_role].id, priority=priority)
        db.session.add(t)

    # Some more tasks
    extra_tasks = [
        ('새 명언집 기획 착수', None, '기획', '진행중', date(2026,4,1), date(2026,4,7), '편집장', '긴급'),
        ('수건 입고 확인', items['좋은생각 수건 연핑크'].id, '입고', '대기', date(2026,4,16), date(2026,4,16), '구독매니저1', '높음'),
        ('칭찬노트 리뉴얼 기획', items['좋은생각 노트 칭찬노트 리뉴얼1'].id, '기획', '대기', date(2026,4,1), date(2026,4,15), '실무자', '높음'),
        ('좋은생각 앞치마 노랑 입고 확인', items['좋은생각 앞치마 노랑'].id, '입고', '대기', date(2026,4,30), date(2026,4,30), '구독매니저1', '보통'),
    ]
    for title, item_id, stage, status, start, due, owner_role, priority in extra_tasks:
        t = Task(title=title, item_id=item_id, stage=stage, status=status,
                 start_date=start, due_date=due, assignee_id=users[owner_role].id, priority=priority)
        db.session.add(t)

    db.session.commit()
    print("  Database seeded with initial data.")

# ═══════════════════════════════════════════
# AUTH ROUTES
# ═══════════════════════════════════════════
@app.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password_hash, request.form['password']):
            login_user(user)
            return redirect(request.args.get('next') or url_for('dashboard'))
        flash('아이디 또는 비밀번호가 올바르지 않습니다.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ═══════════════════════════════════════════
# MAIN PAGES
# ═══════════════════════════════════════════
@app.route('/')
@login_required
def dashboard():
    today = date.today()

    # ── 카드 1: 이번 달 마감 임박 ──
    month_start = date(today.year, today.month, 1)
    if today.month == 12:
        month_end = date(today.year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(today.year, today.month + 1, 1) - timedelta(days=1)
    due_this_month = Task.query.filter(
        Task.due_date >= month_start, Task.due_date <= month_end,
        Task.status != '완료'
    ).order_by(Task.due_date).all()
    due_count = len(due_this_month)
    nearest_due = due_this_month[0] if due_this_month else None
    nearest_item_name = nearest_due.item.name if nearest_due and nearest_due.item else (nearest_due.title if nearest_due else '')
    days_left = (nearest_due.due_date - today).days if nearest_due else None

    # ── 카드 2: 재고 경고 ──
    all_selling = Item.query.filter(Item.current_stock > 0, Item.status.in_(['소진중','판매중'])).all()
    stock_alerts = sum(1 for i in all_selling if i.current_stock <= (i.target_qty * 0.25 if i.target_qty else 100))
    lowest_item = None
    lowest_pct = 999
    for i in all_selling:
        if i.target_qty and i.target_qty > 0:
            pct = i.current_stock / i.target_qty * 100
            if pct < lowest_pct:
                lowest_pct = pct
                lowest_item = i

    # ── 카드 3: 파이프라인 현황 ──
    pipeline_items = Item.query.filter(Item.status.in_(['기획중','디자인중','제작중','입고대기'])).all()
    pipeline_count = len(pipeline_items)

    # ── 카드 4: 마케팅 overview ──
    selling_items = Item.query.filter(Item.status.in_(['판매중','소진중'])).all()
    selling_count = len(selling_items)
    total_stock = sum(i.current_stock or 0 for i in selling_items)
    total_target = sum(i.target_qty or 0 for i in selling_items)
    avg_remain_pct = round(total_stock / total_target * 100, 1) if total_target > 0 else 0

    # ── 카카오메이커스 역산 알림 ──
    kakao_deadline = 45  # 판매 시작 45일 전부터 알림
    kakao_alerts = []
    upcoming_kakao = KakaoEvent.query.filter(
        KakaoEvent.period_start != None,
        KakaoEvent.status.in_(['기획중', '준비완료'])
    ).all()
    for ev in upcoming_kakao:
        days_until = (ev.period_start - today).days
        if 0 < days_until <= kakao_deadline:
            kakao_alerts.append({'name': ev.name, 'start': ev.period_start, 'days': days_until})
    kakao_alerts.sort(key=lambda x: x['days'])

    # ── 나의 업무 + 재고 현황 (기존) ──
    # 소장/편집장은 전체 진행 업무 표시, 나머지는 본인 배정 업무만
    if has_perm('view_all_tasks'):
        my_tasks = Task.query.filter(Task.status!='완료').order_by(Task.due_date).limit(8).all()
    else:
        my_tasks = Task.query.filter_by(assignee_id=current_user.id).filter(Task.status!='완료').order_by(Task.due_date).limit(5).all()
    items_a = Item.query.filter(Item.line.contains('A')).all()

    return render_template('index.html', page='dashboard',
                           due_count=due_count, nearest_item_name=nearest_item_name, days_left=days_left,
                           stock_alerts=stock_alerts, lowest_item=lowest_item, lowest_pct=round(lowest_pct, 1) if lowest_item else 0,
                           pipeline_count=pipeline_count, pipeline_items=pipeline_items,
                           selling_count=selling_count, avg_remain_pct=avg_remain_pct,
                           my_tasks=my_tasks, items_a=items_a, today=today,
                           kakao_alerts=kakao_alerts)

@app.route('/tasks')
@login_required
def tasks():
    """칸반: 5단계(기획→디자인→컨펌/견적→제작→입고) 기반
    규칙: 품목별로 현재 활성 단계(진행중)와 바로 다음 대기 단계만 표시.
    아직 차례가 안 된 미래 단계 태스크는 숨김."""
    STAGES = ['기획', '디자인', '컨펌/견적', '제작', '입고']
    all_tasks = Task.query.order_by(Task.due_date).all()

    # 품목별로 현재 활성 단계 파악
    # item_id → 진행중인 가장 높은 stage index (없으면 -1)
    item_active_idx = {}  # item_id → int
    for t in all_tasks:
        if t.item_id and t.status in ('진행중', '완료') and t.stage in STAGES:
            idx = STAGES.index(t.stage)
            prev = item_active_idx.get(t.item_id, -1)
            if idx > prev:
                item_active_idx[t.item_id] = idx

    stage_tasks = {s: [] for s in STAGES}
    done_tasks = []
    for t in all_tasks:
        if t.status == '완료':
            done_tasks.append(t)
            continue
        if t.stage not in STAGES:
            continue
        # 독립 업무(item_id 없음) → 항상 표시
        if not t.item_id:
            stage_tasks[t.stage].append(t)
            continue
        # 품목 연결 업무 → 현재 활성 단계까지만 표시
        task_idx = STAGES.index(t.stage)
        active_idx = item_active_idx.get(t.item_id, -1)
        # 표시 조건: 진행중이거나, 활성 단계 이하이거나, 활성 바로 다음 대기 단계
        if t.status == '진행중':
            stage_tasks[t.stage].append(t)
        elif task_idx <= active_idx:
            # 현재 활성 이하 (이미 지난 대기 = 사실상 보여야 함)
            stage_tasks[t.stage].append(t)
        elif task_idx == active_idx + 1 and t.status == '대기':
            # 바로 다음 단계 대기 → 표시 (곧 시작할 업무)
            stage_tasks[t.stage].append(t)
        elif active_idx == -1 and task_idx == 0:
            # 아직 아무것도 시작 안 한 품목의 첫 단계
            stage_tasks[t.stage].append(t)
        # 그 외 미래 단계 대기 → 숨김

    users = User.query.order_by(User.role, User.name).all()
    return render_template('index.html', page='tasks',
                           stage_tasks=stage_tasks, done_tasks=done_tasks, STAGES=STAGES,
                           today=date.today(), users=users)

@app.route('/items')
@login_required
def items():
    line = request.args.get('line', '')
    cat = request.args.get('cat', '')
    q = request.args.get('q', '')
    query = Item.query
    if line:
        query = query.filter(Item.line.contains(line))
    if cat:
        query = query.filter(Item.category_id == int(cat))
    if q:
        query = query.filter(Item.name.contains(q))
    all_items = query.order_by(Item.created_at.desc()).all()
    categories = Category.query.order_by(Category.name).all()
    users = User.query.all()
    return render_template('index.html', page='items', items=all_items, categories=categories, users=users)

@app.route('/items/create', methods=['POST'])
@login_required
def create_item():
    name = request.form['name']
    line = request.form['line']
    category_id = request.form.get('category_id') or None
    artist = request.form.get('artist', '')
    unit_cost = int(request.form['unit_cost']) if request.form.get('unit_cost') else None
    target_qty = int(request.form['target_qty']) if request.form.get('target_qty') else None
    owner_id = int(request.form['owner_id']) if request.form.get('owner_id') else current_user.id
    target_date_str = request.form.get('target_date', '')
    target_date = date.fromisoformat(target_date_str) if target_date_str else None
    usage = request.form.get('usage', '판매')
    memo = request.form.get('memo', '')

    # 판매 URL: 사용자가 직접 입력한 값 우선, 없으면 품목명 기반 검색 URL 자동 생성
    from urllib.parse import quote
    q = quote(name)  # URL-safe 품목명

    sale_smartstore = request.form.get('sale_url_smartstore', '').strip() or None
    sale_aengdu = request.form.get('sale_url_aengdu', '').strip() or None
    sale_positive = request.form.get('sale_url_positive', '').strip() or None

    # 랜딩 페이지만 넣은 경우(경로 없음) → 검색 URL로 자동 변환
    if sale_smartstore and sale_smartstore.rstrip('/') == 'https://smartstore.naver.com/positivethinking':
        sale_smartstore = f'https://smartstore.naver.com/positivethinking/search?q={q}'
    if sale_aengdu and sale_aengdu.rstrip('/') in ('https://aengdu.kr', 'https://www.aengdu.kr'):
        sale_aengdu = f'https://aengdu.kr/?s={q}'
    if sale_positive and sale_positive.rstrip('/') in ('https://positive.co.kr', 'https://www.positive.co.kr'):
        sale_positive = f'https://positive.co.kr/?s={q}'

    # 라인에 따라 URL이 아예 비어있으면 검색 URL 자동 생성
    if line in ('A', 'B', 'B,C'):
        if not sale_smartstore:
            sale_smartstore = f'https://smartstore.naver.com/positivethinking/search?q={q}'
    if line in ('A',):
        if not sale_positive:
            sale_positive = f'https://positive.co.kr/?s={q}'
    if line in ('B', 'B,C'):
        if not sale_aengdu:
            sale_aengdu = f'https://aengdu.kr/?s={q}'

    # 기존 품목 모드: 상태와 재고를 직접 설정
    is_existing = request.form.get('is_existing') == 'on'
    if is_existing:
        item_status = request.form.get('item_status', '판매중')
        current_stock = int(request.form['current_stock']) if request.form.get('current_stock') else 0
    else:
        item_status = '기획중'
        current_stock = 0

    item = Item(name=name, line=line, category_id=category_id, artist=artist,
                unit_cost=unit_cost, target_qty=target_qty, current_stock=current_stock,
                status=item_status, owner_id=owner_id, target_date=target_date, memo=memo,
                sale_url_smartstore=sale_smartstore, sale_url_aengdu=sale_aengdu,
                sale_url_positive=sale_positive, usage=usage)
    db.session.add(item)
    db.session.flush()

    # 기존 품목이 아닐 때만 업무 자동 생성
    if not is_existing and target_date:
        auto_generate_tasks(item, owner_id)

    # 퀄리티 체크리스트 자동 생성 (카테고리 기반)
    checklist_count = _create_checklist_for_item(item)

    db.session.commit()
    if is_existing:
        flash(f'"{name}" 기존 상품이 등록되었습니다. (상태: {item_status}, 재고: {current_stock:,}개) 체크리스트 {checklist_count}건 생성!', 'success')
    else:
        msg = f'"{name}" 상품이 등록되었습니다.'
        if target_date:
            msg += f' 업무 5건 + 체크리스트 {checklist_count}건 자동 생성!'
        else:
            msg += f' 체크리스트 {checklist_count}건 자동 생성!'
        flash(msg, 'success')
    return redirect(url_for('items'))

def auto_generate_tasks(item, owner_id):
    """목표 입고일 기준 역산하여 5단계 업무 자동 생성 (기획→디자인→컨펌/견적→제작발주→입고)"""
    target = item.target_date
    designer = User.query.filter_by(role='디자이너').first()
    admin_mgr = User.query.filter_by(role='행정팀장').first()

    stock_date = target
    prod_end = target - timedelta(days=20)
    prod_start = prod_end - timedelta(days=30)
    sample_end = prod_start - timedelta(days=1)
    sample_start = sample_end - timedelta(days=6)  # 샘플 확인 7일
    design_end = sample_start - timedelta(days=1)
    design_start = design_end - timedelta(days=20)
    plan_end = design_start - timedelta(days=1)
    plan_start = plan_end - timedelta(days=29)

    stages = [
        (f'{item.name} 기획', '기획', plan_start, plan_end, owner_id, '높음'),
        (f'{item.name} 디자인', '디자인', design_start, design_end, designer.id if designer else owner_id, '보통'),
        (f'{item.name} 컨펌/견적', '컨펌/견적', sample_start, sample_end, owner_id, '보통'),
        (f'{item.name} 제작발주', '제작', prod_start, prod_end, owner_id, '보통'),
        (f'{item.name} 입고확인', '입고', stock_date, stock_date, admin_mgr.id if admin_mgr else owner_id, '보통'),
    ]
    for title, stage, start, due, assignee, priority in stages:
        t = Task(title=title, item_id=item.id, stage=stage, status='대기',
                 start_date=start, due_date=due, assignee_id=assignee, priority=priority)
        db.session.add(t)

@app.route('/items/<int:item_id>/status', methods=['POST'])
@login_required
def update_item_status(item_id):
    item = Item.query.get_or_404(item_id)
    item.status = request.form['status']
    db.session.commit()
    return jsonify({'ok': True, 'status': item.status})

@app.route('/items/<int:item_id>/edit', methods=['POST'])
@login_required
def edit_item(item_id):
    item = Item.query.get_or_404(item_id)
    item.name = request.form['name']
    item.line = request.form['line']
    item.category_id = request.form.get('category_id') or None
    item.artist = request.form.get('artist', '')
    item.unit_cost = int(request.form['unit_cost']) if request.form.get('unit_cost') else None
    item.target_qty = int(request.form['target_qty']) if request.form.get('target_qty') else None
    item.current_stock = int(request.form['current_stock']) if request.form.get('current_stock') else 0
    item.status = request.form.get('status', item.status)
    item.usage = request.form.get('usage', '판매')
    item.owner_id = int(request.form['owner_id']) if request.form.get('owner_id') else current_user.id
    target_date_str = request.form.get('target_date', '')
    item.target_date = date.fromisoformat(target_date_str) if target_date_str else None
    item.memo = request.form.get('memo', '')

    # 판매 URL
    item.sale_url_smartstore = request.form.get('sale_url_smartstore', '').strip() or None
    item.sale_url_aengdu = request.form.get('sale_url_aengdu', '').strip() or None
    item.sale_url_positive = request.form.get('sale_url_positive', '').strip() or None

    db.session.commit()
    flash(f'"{item.name}" 상품이 수정되었습니다.', 'success')
    return redirect(url_for('items'))

@app.route('/items/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_item(item_id):
    item = Item.query.get_or_404(item_id)
    name = item.name
    # 연결된 태스크도 삭제
    Task.query.filter_by(item_id=item_id).delete()
    WeeklyCount.query.filter_by(item_id=item_id).delete()
    InventoryLog.query.filter_by(item_id=item_id).delete()
    db.session.delete(item)
    db.session.commit()
    flash(f'"{name}" 상품이 삭제되었습니다.', 'success')
    return redirect(url_for('items'))

@app.route('/api/items/<int:item_id>')
@login_required
def get_item_json(item_id):
    item = Item.query.get_or_404(item_id)
    return jsonify({
        'id': item.id, 'name': item.name, 'line': item.line,
        'category_id': item.category_id, 'artist': item.artist or '',
        'unit_cost': item.unit_cost, 'target_qty': item.target_qty,
        'current_stock': item.current_stock, 'status': item.status,
        'usage': item.usage or '판매', 'owner_id': item.owner_id,
        'target_date': item.target_date.isoformat() if item.target_date else '',
        'memo': item.memo or '',
        'sale_url_smartstore': item.sale_url_smartstore or '',
        'sale_url_aengdu': item.sale_url_aengdu or '',
        'sale_url_positive': item.sale_url_positive or '',
    })

@app.route('/tasks/<int:task_id>/status', methods=['POST'])
@login_required
def update_task_status(task_id):
    STAGES = ['기획', '디자인', '컨펌/견적', '제작', '입고']
    task = Task.query.get_or_404(task_id)
    new_status = request.form['status']

    # ── 이전 단계 완료 검증: 진행중으로 바꾸려면 이전 단계가 완료여야 함 ──
    if new_status in ('진행중',) and task.item_id and task.stage in STAGES:
        stage_idx = STAGES.index(task.stage)
        if stage_idx > 0:
            prev_stage = STAGES[stage_idx - 1]
            prev_task = Task.query.filter_by(item_id=task.item_id, stage=prev_stage).first()
            if prev_task and prev_task.status != '완료':
                return jsonify({'ok': False, 'error': f'"{prev_stage}" 단계가 아직 완료되지 않았습니다. 이전 단계를 먼저 완료해 주세요.'})

    task.status = new_status
    if new_status == '완료':
        task.completed_at = datetime.utcnow()
    else:
        task.completed_at = None
    db.session.commit()
    return jsonify({'ok': True})

@app.route('/tasks/<int:task_id>/advance', methods=['POST'])
@login_required
def advance_task(task_id):
    """현재 단계를 완료하고 다음 단계를 활성화 (없으면 자동 생성)"""
    task = Task.query.get_or_404(task_id)
    STAGES = ['기획', '디자인', '컨펌/견적', '제작', '입고']

    # ── 이전 단계 완료 검증 ──
    if task.item_id and task.stage in STAGES:
        stage_idx = STAGES.index(task.stage)
        if stage_idx > 0:
            prev_stage = STAGES[stage_idx - 1]
            prev_task = Task.query.filter_by(item_id=task.item_id, stage=prev_stage).first()
            if prev_task and prev_task.status != '완료':
                return jsonify({'ok': False, 'error': f'"{prev_stage}" 단계가 아직 완료되지 않았습니다.'})
    STAGE_DEFAULTS = {
        '디자인': {'assignee_role': '디자이너', 'days': 21},
        '컨펌/견적': {'assignee_role': None, 'days': 7},
        '제작': {'assignee_role': None, 'days': 30},
        '입고': {'assignee_role': '행정팀장', 'days': 1},
    }
    current_idx = STAGES.index(task.stage) if task.stage in STAGES else -1
    task.status = '완료'
    task.completed_at = datetime.utcnow()

    # 팝업에서 선택한 담당자
    next_assignee_id = request.form.get('next_assignee_id')
    if next_assignee_id:
        next_assignee_id = int(next_assignee_id)

    assigned_user = None

    if current_idx >= 0 and current_idx < len(STAGES) - 1:
        next_stage = STAGES[current_idx + 1]
        next_task = Task.query.filter_by(item_id=task.item_id, stage=next_stage).first()

        if next_task:
            # 기존 태스크가 있으면 활성화 (완료 상태여도 재활성화)
            next_task.status = '진행중'
            next_task.completed_at = None
            if next_assignee_id:
                next_task.assignee_id = next_assignee_id
            assigned_user = User.query.get(next_task.assignee_id) if next_task.assignee_id else None
        elif task.item_id:
            # 다음 단계 태스크가 없으면 자동 생성
            defaults = STAGE_DEFAULTS.get(next_stage, {})
            assignee_id = next_assignee_id or task.assignee_id  # 팝업 선택 > 기본값
            if not next_assignee_id and defaults.get('assignee_role'):
                role_user = User.query.filter_by(role=defaults['assignee_role']).first()
                if role_user:
                    assignee_id = role_user.id
            item = Item.query.get(task.item_id)
            item_name = item.name if item else ''
            stage_label = {'디자인': '디자인', '컨펌/견적': '컨펌/견적', '제작': '제작발주', '입고': '입고확인'}
            new_task = Task(
                title=f'{item_name} {stage_label.get(next_stage, next_stage)}',
                item_id=task.item_id,
                stage=next_stage,
                status='진행중',
                assignee_id=assignee_id,
                priority='보통',
                start_date=date.today(),
                due_date=date.today() + timedelta(days=defaults.get('days', 14)),
            )
            db.session.add(new_task)
            db.session.flush()
            assigned_user = User.query.get(assignee_id) if assignee_id else None
            flash(f'"{next_stage}" 단계 업무가 자동 생성되었습니다.', 'info')

        # 담당자에게 알림 발송
        if assigned_user and assigned_user.id != current_user.id:
            item = Item.query.get(task.item_id) if task.item_id else None
            item_name = item.name if item else task.title
            noti = Notification(
                recipient_id=assigned_user.id,
                message=f'{current_user.name}님이 "{item_name}" {next_stage} 단계를 배정했습니다.',
                link=url_for('tasks'),
                noti_type='업무배정',
            )
            db.session.add(noti)

    db.session.commit()
    if not task.item_id:
        flash(f'"{task.title}" 업무가 완료되었습니다.', 'success')
    else:
        who = f' → {assigned_user.name}님 배정' if assigned_user else ''
        flash(f'"{task.stage}" 완료 → 다음 단계로 이동{who}', 'success')
    return jsonify({'ok': True})

@app.route('/tasks/<int:task_id>/revert', methods=['POST'])
@login_required
def revert_task(task_id):
    """현재 단계를 이전 단계로 되돌리기"""
    task = Task.query.get_or_404(task_id)
    STAGES = ['기획', '디자인', '컨펌/견적', '제작', '입고']
    if not task.item_id or task.stage not in STAGES:
        return jsonify({'ok': False, 'error': '이전 단계가 없습니다.'})
    current_idx = STAGES.index(task.stage)
    if current_idx == 0:
        return jsonify({'ok': False, 'error': '기획 단계에서는 더 이전으로 갈 수 없습니다.'})
    prev_stage = STAGES[current_idx - 1]
    # 현재 태스크를 대기로 되돌림
    task.status = '대기'
    task.completed_at = None
    # 이전 단계 태스크를 다시 진행중으로
    prev_task = Task.query.filter_by(item_id=task.item_id, stage=prev_stage).first()
    if prev_task:
        prev_task.status = '진행중'
        prev_task.completed_at = None
    # 현재 단계 이후의 모든 태스크도 대기로 리셋
    for future_idx in range(current_idx + 1, len(STAGES)):
        future_stage = STAGES[future_idx]
        future_task = Task.query.filter_by(item_id=task.item_id, stage=future_stage).first()
        if future_task and future_task.status != '대기':
            future_task.status = '대기'
            future_task.completed_at = None
    db.session.commit()
    flash(f'"{task.stage}" → "{prev_stage}" 단계로 되돌렸습니다.', 'info')
    return jsonify({'ok': True})

@app.route('/tasks/<int:task_id>/complete-delivery', methods=['POST'])
@login_required
def complete_delivery(task_id):
    """입고 완료 → 태스크 완료 처리 + 상품 상태 업데이트"""
    task = Task.query.get_or_404(task_id)
    if task.stage != '입고':
        return jsonify({'ok': False, 'error': '입고 태스크가 아닙니다'}), 400
    task.status = '완료'
    task.completed_at = datetime.utcnow()
    # 연결된 상품 상태를 입고완료/판매중으로 변경
    if task.item:
        task.item.status = '판매중'
    db.session.commit()
    item_name = task.item.name if task.item else task.title
    flash(f'🎉 "{item_name}" 입고 완료! 재고 수량을 확인해주세요.', 'success')
    # 재고 관리 페이지로 리다이렉트 (item_id 파라미터 포함)
    return jsonify({'ok': True, 'redirect': url_for('inventory'), 'item_name': item_name})

@app.route('/tasks/<int:task_id>/production', methods=['POST'])
@login_required
def update_production(task_id):
    """제작 태스크의 제작기간/시작일 업데이트"""
    task = Task.query.get_or_404(task_id)
    weeks = request.form.get('production_weeks')
    prod_start = request.form.get('production_start')
    if weeks:
        task.production_weeks = int(weeks)
    if prod_start:
        task.production_start = date.fromisoformat(prod_start)
    db.session.commit()
    return jsonify({'ok': True})

@app.route('/tasks/<int:task_id>/sample-approve', methods=['POST'])
@login_required
def sample_approve(task_id):
    """샘플 승인 → 컨펌/견적 태스크 완료, 제작발주 태스크 진행중으로"""
    task = Task.query.get_or_404(task_id)
    if task.stage != '컨펌/견적':
        return jsonify({'ok': False, 'error': '컨펌/견적 태스크가 아닙니다'}), 400
    task.status = '완료'
    task.completed_at = datetime.utcnow()
    # 다음 단계(제작) 활성화
    next_task = Task.query.filter_by(item_id=task.item_id, stage='제작').first()
    if next_task:
        next_task.status = '진행중'
    db.session.commit()
    flash(f'샘플 승인 완료! 제작 발주 단계로 넘어갑니다.', 'success')
    return jsonify({'ok': True})

@app.route('/tasks/<int:task_id>/sample-revise', methods=['POST'])
@login_required
def sample_revise(task_id):
    """샘플 수정요청 → 디자인 태스크로 되돌아감, 수정 횟수 증가"""
    task = Task.query.get_or_404(task_id)
    if task.stage != '컨펌/견적':
        return jsonify({'ok': False, 'error': '컨펌/견적 태스크가 아닙니다'}), 400
    task.revision_count = (task.revision_count or 0) + 1
    task.status = '대기'  # 디자인 수정 후 다시 돌아올 때까지 대기
    # 디자인 태스크를 다시 진행중으로
    design_task = Task.query.filter_by(item_id=task.item_id, stage='디자인').first()
    if design_task:
        design_task.status = '진행중'
        design_task.completed_at = None
    db.session.commit()
    flash(f'수정 요청! (#{task.revision_count}차) 디자인 단계로 되돌아갑니다.', 'warning')
    return jsonify({'ok': True, 'revision_count': task.revision_count})

@app.route('/tasks/<int:task_id>/skip-sample', methods=['POST'])
@login_required
def skip_sample(task_id):
    """컨펌/견적 건너뛰기 (재오더 등 불필요한 경우)"""
    task = Task.query.get_or_404(task_id)
    if task.stage != '컨펌/견적':
        return jsonify({'ok': False, 'error': '컨펌/견적 태스크가 아닙니다'}), 400
    task.status = '완료'
    task.completed_at = datetime.utcnow()
    task.title = task.title + ' (건너뜀)'
    next_task = Task.query.filter_by(item_id=task.item_id, stage='제작').first()
    if next_task:
        next_task.status = '진행중'
    db.session.commit()
    flash(f'컨펌/견적 건너뜀 → 제작 발주 단계로 이동합니다.', 'success')
    return jsonify({'ok': True})

@app.route('/items/<int:item_id>/reorder', methods=['POST'])
@login_required
def create_reorder(item_id):
    """재발주 태스크 자동 생성"""
    item = Item.query.get_or_404(item_id)
    # 이미 진행 중인 재발주 태스크가 있는지 확인
    existing = Task.query.filter_by(item_id=item_id).filter(
        Task.title.contains('재발주'),
        Task.status.in_(['대기', '진행중', '리뷰'])
    ).first()
    if existing:
        flash(f'이미 진행 중인 재발주 업무가 있습니다: "{existing.title}"', 'warning')
        return redirect(url_for('inventory'))

    reorder_qty = request.form.get('qty', '')
    target_date_str = request.form.get('target_date', '')
    target_date = date.fromisoformat(target_date_str) if target_date_str else date.today() + timedelta(days=60)

    task = Task(
        title=f'{item.name} 재발주' + (f' ({reorder_qty}개)' if reorder_qty else ''),
        item_id=item.id, stage='제작', status='대기',
        start_date=date.today(), due_date=target_date,
        assignee_id=item.owner_id or current_user.id,
        priority='높음'
    )
    db.session.add(task)
    db.session.commit()
    flash(f'"{item.name}" 재발주 업무가 생성되었습니다.', 'success')
    return redirect(url_for('inventory'))

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    """파일 업로드 (태스크 또는 품목에 첨부)"""
    from flask import send_from_directory
    file = request.files.get('file')
    if not file or not file.filename:
        flash('파일을 선택해주세요.', 'error')
        return redirect(request.referrer or url_for('tasks'))

    task_id = request.form.get('task_id') or None
    item_id = request.form.get('item_id') or None
    file_type = request.form.get('file_type', '기타')

    # 안전한 파일명 생성
    orig_name = file.filename
    ext = orig_name.rsplit('.', 1)[-1] if '.' in orig_name else ''
    safe_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{secure_filename(orig_name)}"
    filepath = os.path.join(UPLOAD_DIR, safe_name)
    file.save(filepath)
    file_size = os.path.getsize(filepath)

    att = Attachment(
        task_id=int(task_id) if task_id else None,
        item_id=int(item_id) if item_id else None,
        filename=safe_name, original_name=orig_name,
        file_type=file_type, file_size=file_size,
        uploaded_by=current_user.id
    )
    db.session.add(att)
    db.session.flush()  # att.id 확보

    # 소장/편집장에게 파일 첨부 알림 생성
    task_obj = Task.query.get(int(task_id)) if task_id else None
    item_obj = Item.query.get(int(item_id)) if item_id else None
    context_name = ''
    if task_obj:
        context_name = task_obj.title
    elif item_obj:
        context_name = item_obj.name
    noti_msg = f'{current_user.name}님이 "{context_name}"에 파일을 첨부했습니다: {orig_name}'
    noti_link = url_for('tasks')
    noti_roles = get_roles_with_perm('receive_notifications')
    managers = User.query.filter(User.role.in_(noti_roles)).all()
    for mgr in managers:
        if mgr.id != current_user.id:  # 본인에겐 알림 안 보냄
            noti = Notification(
                recipient_id=mgr.id,
                message=noti_msg,
                link=noti_link,
                noti_type='파일첨부',
                attachment_id=att.id,
            )
            db.session.add(noti)

    db.session.commit()
    flash(f'"{orig_name}" 업로드 완료', 'success')
    return redirect(request.referrer or url_for('tasks'))

@app.route('/uploads/<filename>')
@login_required
def download_file(filename):
    from flask import send_from_directory
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=True)

@app.route('/attachments/<int:att_id>/delete', methods=['POST'])
@login_required
def delete_attachment(att_id):
    att = Attachment.query.get_or_404(att_id)
    filepath = os.path.join(UPLOAD_DIR, att.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    db.session.delete(att)
    db.session.commit()
    flash('파일이 삭제되었습니다.', 'success')
    if request.headers.get('Content-Type') == 'application/x-www-form-urlencoded' or request.is_json:
        return jsonify({'ok': True})
    return redirect(request.referrer or url_for('tasks'))

def _build_month_data(year, month, today):
    """한 달치 캘린더 데이터(날짜 그리드, 이벤트, Gantt 바) 생성
       — 품목별 단일 색상 바 (기획 시작 ~ 입고 완료)"""
    import calendar as cal_mod
    first_weekday, days_in_month = cal_mod.monthrange(year, month)
    cal_days = [None] * first_weekday + list(range(1, days_in_month + 1))
    while len(cal_days) % 7:
        cal_days.append(None)

    month_start = date(year, month, 1)
    month_end = date(year, month, days_in_month)

    # 입고예정 이벤트만 셀에 표시
    items_in_month = Item.query.filter(
        Item.target_date >= month_start, Item.target_date <= month_end
    ).all()
    day_events = {}
    for it in items_in_month:
        d = it.target_date.day
        if d not in day_events:
            day_events[d] = []
        day_events[d].append({
            'type': 'delivery', 'label': it.name[:10],
            'stage': '입고', 'status': it.status, 'full': it.name
        })

    # ── 카카오메이커스 이벤트 (셀 이벤트 + 바) ──
    kakao_events = KakaoEvent.query.filter(
        KakaoEvent.period_start != None, KakaoEvent.period_end != None,
        KakaoEvent.period_start <= month_end, KakaoEvent.period_end >= month_start,
    ).all()
    for ke in kakao_events:
        # 시작일이 이 달에 있으면 셀 이벤트 표시
        if month_start <= ke.period_start <= month_end:
            d = ke.period_start.day
            if d not in day_events:
                day_events[d] = []
            day_events[d].append({
                'type': 'kakao', 'label': ke.name[:10],
                'stage': '카카오', 'status': ke.status, 'full': ke.name,
            })
        # 종료일이 이 달에 있으면 셀 이벤트 표시
        if month_start <= ke.period_end <= month_end and ke.period_end != ke.period_start:
            d = ke.period_end.day
            if d not in day_events:
                day_events[d] = []
            day_events[d].append({
                'type': 'kakao_end', 'label': f'{ke.name[:8]} 종료',
                'stage': '카카오', 'status': ke.status, 'full': ke.name,
            })

    # ── 품목별 단일 바 생성 (기획 시작일 ~ 입고 마감일) ──
    ITEM_PALETTE = [
        '#2E7D9B', '#7C6DAF', '#D4883A', '#2EAD6B', '#C75B7A',
        '#5B8C5A', '#E07B54', '#4A8EC2', '#9C8978', '#6B9080',
    ]
    # 품목별로 가장 빠른 start_date와 가장 늦은 due_date 구하기 (독립업무 제외)
    all_tasks = Task.query.filter(
        Task.item_id != None,
        Task.start_date != None, Task.due_date != None
    ).order_by(Task.item_id, Task.start_date).all()

    item_ranges = {}  # item_id → {start, end, name, status}
    for t in all_tasks:
        if t.item_id not in item_ranges:
            item_ranges[t.item_id] = {
                'start': t.start_date, 'end': t.due_date,
                'name': t.item.name if t.item else '?',
                'has_active': False,
            }
        r = item_ranges[t.item_id]
        if t.start_date < r['start']:
            r['start'] = t.start_date
        if t.due_date > r['end']:
            r['end'] = t.due_date
        if t.status == '진행중':
            r['has_active'] = True

    bars = []
    bar_id = 0
    for idx, (item_id, r) in enumerate(item_ranges.items()):
        # 이 달과 겹치는지 확인
        if r['start'] > month_end or r['end'] < month_start:
            continue

        vis_start = max(r['start'], month_start)
        vis_end = min(r['end'], month_end)
        start_day, end_day = vis_start.day, vis_end.day
        color = ITEM_PALETTE[idx % len(ITEM_PALETTE)]
        opacity = '1' if r['has_active'] else '.55'
        item_label = r['name'][:14]

        # 주 단위로 분할
        cur_day = start_day
        first_segment = True
        while cur_day <= end_day:
            cell_idx = first_weekday + (cur_day - 1)
            row = cell_idx // 7
            col_start = cell_idx % 7
            span = min(7 - col_start, end_day - cur_day + 1)
            is_real_start = (cur_day == start_day and r['start'] >= month_start)
            is_real_end = (cur_day + span - 1 == end_day and r['end'] <= month_end)
            bars.append({
                'id': bar_id, 'row': row, 'col': col_start, 'span': span,
                'item_id': item_id, 'color': color, 'opacity': opacity,
                'label': item_label if first_segment else '',
                'title': f'{r["name"]}  {r["start"].strftime("%m/%d")} ~ {r["end"].strftime("%m/%d")}',
                'round_left': is_real_start, 'round_right': is_real_end,
            })
            bar_id += 1
            cur_day += span
            first_segment = False

    # ── 카카오메이커스 이벤트 바 (주황 계열) ──
    KAKAO_COLOR = '#F5A623'
    for ke in kakao_events:
        vis_start = max(ke.period_start, month_start)
        vis_end = min(ke.period_end, month_end)
        start_day, end_day = vis_start.day, vis_end.day
        kakao_label = f'🟡 {ke.name[:12]}'
        kakao_item_id = f'kakao_{ke.id}'

        cur_day = start_day
        first_segment = True
        while cur_day <= end_day:
            cell_idx = first_weekday + (cur_day - 1)
            row = cell_idx // 7
            col_start = cell_idx % 7
            span = min(7 - col_start, end_day - cur_day + 1)
            is_real_start = (cur_day == start_day and ke.period_start >= month_start)
            is_real_end = (cur_day + span - 1 == end_day and ke.period_end <= month_end)
            bars.append({
                'id': bar_id, 'row': row, 'col': col_start, 'span': span,
                'item_id': kakao_item_id, 'color': KAKAO_COLOR, 'opacity': '1',
                'label': kakao_label if first_segment else '',
                'title': f'카카오메이커스: {ke.name}  {ke.period_start.strftime("%m/%d")} ~ {ke.period_end.strftime("%m/%d")}',
                'round_left': is_real_start, 'round_right': is_real_end,
            })
            bar_id += 1
            cur_day += span
            first_segment = False

    # swim-lane 배정 (같은 item_id는 같은 lane 유지)
    item_lane_map = {}  # item_id → lane index (row-independent global)
    row_lanes = {}
    # 먼저 item_id 순서대로 lane 배정
    for b in bars:
        r = b['row']
        if r not in row_lanes:
            row_lanes[r] = []
        occupied = set(range(b['col'], b['col'] + b['span']))

        # 같은 품목이 이 row에서 이미 lane을 쓰고 있으면 그 lane 재사용
        iid = b['item_id']
        if iid in item_lane_map and item_lane_map[iid][0] == r:
            lane_idx = item_lane_map[iid][1]
            if lane_idx < len(row_lanes[r]):
                row_lanes[r][lane_idx] |= occupied
            else:
                while len(row_lanes[r]) <= lane_idx:
                    row_lanes[r].append(set())
                row_lanes[r][lane_idx] |= occupied
        else:
            lane_idx = 0
            placed = False
            for li, existing_lane in enumerate(row_lanes[r]):
                if not (occupied & existing_lane):
                    lane_idx = li
                    placed = True
                    break
                lane_idx = li + 1
            if not placed:
                lane_idx = len(row_lanes[r])
            if lane_idx >= len(row_lanes[r]):
                row_lanes[r].append(occupied)
            else:
                row_lanes[r][lane_idx] |= occupied
            item_lane_map[iid] = (r, lane_idx)

        b['lane'] = lane_idx
    max_lanes = {r: len(lanes) for r, lanes in row_lanes.items()}

    return {
        'year': year, 'month': month,
        'cal_days': cal_days, 'day_events': day_events,
        'bars': bars, 'max_lanes': max_lanes,
    }

@app.route('/calendar')
@login_required
def calendar():
    today = date.today()
    year = int(request.args.get('y', today.year))
    month = int(request.args.get('m', today.month))
    # 이전/다음 2개월 단위 이동
    prev_m = month - 2 if month > 2 else month - 2 + 12
    prev_y = year if month > 2 else year - 1
    next_m = month + 2 if month <= 10 else month + 2 - 12
    next_y = year if month <= 10 else year + 1
    # 왼쪽(이번달) + 오른쪽(다음달) 데이터
    m1 = _build_month_data(year, month, today)
    m2_month = month + 1 if month < 12 else 1
    m2_year = year if month < 12 else year + 1
    m2 = _build_month_data(m2_year, m2_month, today)

    # ── 두 달 높이 통일: 행 수 맞추기 + 행별 높이 통일 ──
    m1_rows = len(m1['cal_days']) // 7
    m2_rows = len(m2['cal_days']) // 7
    max_rows = max(m1_rows, m2_rows)
    # 행 수가 적은 쪽에 빈 행 추가
    while len(m1['cal_days']) // 7 < max_rows:
        m1['cal_days'].extend([None] * 7)
    while len(m2['cal_days']) // 7 < max_rows:
        m2['cal_days'].extend([None] * 7)
    # 각 행의 lane 수를 두 달 중 큰 쪽으로 통일
    unified_lanes = {}
    for r in range(max_rows):
        l1 = m1['max_lanes'].get(r, 0)
        l2 = m2['max_lanes'].get(r, 0)
        unified = max(l1, l2, 1)  # 최소 1 lane
        unified_lanes[r] = unified
    m1['max_lanes'] = unified_lanes
    m2['max_lanes'] = unified_lanes

    # 파이프라인 & 전체 업무 리스트 (두 달 범위)
    items_with_dates = Item.query.filter(Item.target_date != None).all()
    tasks_all = Task.query.filter(Task.due_date != None).order_by(Task.start_date).all()

    # 품목별 색상 범례 (두 달에 걸쳐 표시된 품목만)
    seen_items = {}
    for b in m1['bars'] + m2['bars']:
        iid = b['item_id']
        if iid not in seen_items:
            seen_items[iid] = {'color': b['color'], 'label': b['label'] or ''}
    # label이 비어있는 경우 title에서 추출
    for b in m1['bars'] + m2['bars']:
        iid = b['item_id']
        if not seen_items[iid]['label'] and b.get('label'):
            seen_items[iid]['label'] = b['label']
    # label이 여전히 없으면 title에서
    for b in m1['bars'] + m2['bars']:
        iid = b['item_id']
        if not seen_items[iid]['label']:
            seen_items[iid]['label'] = b['title'].split('  ')[0] if b['title'] else '?'
    item_legend = list(seen_items.values())

    return render_template('index.html', page='calendar',
                           today=today,
                           prev_y=prev_y, prev_m=prev_m, next_y=next_y, next_m=next_m,
                           m1=m1, m2=m2,
                           items_with_dates=items_with_dates, tasks_all=tasks_all,
                           item_legend=item_legend)

@app.route('/inventory')
@login_required
def inventory():
    items_a = Item.query.filter(Item.line.contains('A'), Item.current_stock > 0).all()
    all_items = Item.query.order_by(Item.line, Item.name).all()
    weekly = WeeklyCount.query.order_by(WeeklyCount.counted_at.desc()).limit(20).all()

    # ── 소진 현황 (구 마케팅 부스팅) ──
    selling_items = Item.query.filter(Item.status.in_(['판매중', '소진중'])).order_by(Item.line, Item.name).all()
    items_data = []
    for it in selling_items:
        wks = WeeklyCount.query.filter_by(item_id=it.id).order_by(WeeklyCount.counted_at.desc()).limit(4).all()
        weekly_avg = 0
        if len(wks) >= 2:
            total_diff = sum(abs(w.diff) for w in wks if w.diff and w.diff < 0)
            weekly_avg = total_diff // len(wks) if total_diff else 0
        remaining_weeks = None
        if weekly_avg > 0 and it.current_stock:
            remaining_weeks = it.current_stock // weekly_avg
        recommendations = []
        pct = (it.current_stock / it.target_qty * 100) if it.target_qty and it.current_stock else 0
        if pct > 75:
            recommendations.append('📢 초기 홍보 집중 — SNS 마케팅, 스토어 배너 노출')
        elif pct > 50:
            recommendations.append('📊 중간 점검 — 판매 추이 모니터링, 리뷰 수집')
        elif pct > 25:
            recommendations.append('🔥 후반 부스팅 — 할인/번들, 재구매 유도')
        else:
            recommendations.append('⚠️ 재발주 검토 또는 마케팅 축소')
        if it.sale_url_smartstore:
            recommendations.append('🛒 스마트스토어 → 키워드 광고, 쇼핑라이브 고려')
        if it.sale_url_aengdu:
            recommendations.append('🍒 앵두 → SNS 연계, 아티스트 팬 타겟 마케팅')
        items_data.append({
            'item': it, 'weekly_avg': weekly_avg,
            'remaining_weeks': remaining_weeks,
            'pct': round(pct, 1), 'recommendations': recommendations,
        })

    return render_template('index.html', page='inventory', items_a=items_a,
                           all_items=all_items, weekly_counts=weekly,
                           items_data=items_data)

@app.route('/inventory/weekly', methods=['POST'])
@login_required
def submit_weekly_count():
    item_id = int(request.form['item_id'])
    counted_qty = int(request.form['counted_qty'])
    item = Item.query.get_or_404(item_id)
    prev = item.current_stock
    wc = WeeklyCount(item_id=item_id, counted_qty=counted_qty, counted_by=current_user.id,
                     counted_at=date.today(), prev_system_qty=prev, diff=counted_qty - prev, status='확정')
    item.current_stock = counted_qty
    db.session.add(wc)
    db.session.commit()
    flash(f'{item.name} 재고가 {counted_qty}개로 업데이트되었습니다.', 'success')
    return redirect(url_for('inventory'))

@app.route('/inventory/upload-pdf', methods=['POST'])
@login_required
def upload_inventory_pdf():
    """재고 PDF 업로드 → 표 추출 → JSON으로 미리보기 데이터 반환"""
    file = request.files.get('pdf_file')
    if not file or not file.filename:
        flash('PDF 파일을 선택해주세요.', 'error')
        return redirect(url_for('inventory'))
    if not file.filename.lower().endswith('.pdf'):
        flash('PDF 파일만 업로드 가능합니다.', 'error')
        return redirect(url_for('inventory'))

    safe_name = f"inventory_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{secure_filename(file.filename)}"
    filepath = os.path.join(UPLOAD_DIR, safe_name)
    file.save(filepath)

    # PDF에서 표 추출 (엑셀→PDF 변환 형태)
    rows = []
    try:
        import pdfplumber
        with pdfplumber.open(filepath) as pdf:
            for pg in pdf.pages:
                tables = pg.extract_tables()
                for tbl in tables:
                    for row in tbl:
                        if row:
                            rows.append([str(cell or '').strip() for cell in row])
                # 표가 없으면 텍스트에서 줄 단위 파싱
                if not tables:
                    text = pg.extract_text() or ''
                    for line in text.split('\n'):
                        parts = [p.strip() for p in line.split('\t') if p.strip()]
                        if not parts:
                            parts = [p.strip() for p in line.split('  ') if p.strip()]
                        if len(parts) >= 2:
                            rows.append(parts)
    except Exception as e:
        flash(f'PDF 파싱 오류: {str(e)}', 'error')
        return redirect(url_for('inventory'))

    if not rows:
        flash('PDF에서 데이터를 추출하지 못했습니다.', 'error')
        return redirect(url_for('inventory'))

    # 상품명↔DB 매칭 시도
    import re
    all_items = Item.query.all()
    item_map = {}  # 이름(정규화) → item
    for it in all_items:
        key = re.sub(r'\s+', '', it.name.lower())
        item_map[key] = it

    # 헤더행 감지 & 스킵
    header_keywords = ['상품', '품목', '이름', '명', '수량', '재고', 'no', '#', '번호']
    parsed = []
    for row in rows:
        # 헤더행이면 스킵
        row_text = ' '.join(row).lower()
        if any(kw in row_text for kw in header_keywords) and len(row) <= 10:
            is_header = sum(1 for kw in header_keywords if kw in row_text)
            if is_header >= 2:
                continue

        # 상품명과 수량 추출 시도
        name_cell = None
        qty_cell = None
        for cell in row:
            # 숫자(콤마 포함)를 수량으로 인식
            clean = cell.replace(',', '').replace(' ', '')
            if clean.isdigit() and qty_cell is None:
                qty_cell = int(clean)
            elif cell and not clean.isdigit() and name_cell is None:
                name_cell = cell

        if name_cell:
            # DB 상품 매칭
            norm = re.sub(r'\s+', '', name_cell.lower())
            matched_item = item_map.get(norm)
            # 부분 매칭도 시도
            if not matched_item:
                for key, it in item_map.items():
                    if norm in key or key in norm:
                        matched_item = it
                        break

            parsed.append({
                'pdf_name': name_cell,
                'item_id': matched_item.id if matched_item else None,
                'item_name': matched_item.name if matched_item else '',
                'qty': qty_cell if qty_cell is not None else 0,
                'prev_qty': matched_item.current_stock if matched_item else 0,
            })

    if not parsed:
        flash('PDF에서 재고 데이터를 인식하지 못했습니다.', 'error')
        return redirect(url_for('inventory'))

    # 미리보기 페이지로 전달
    return render_template('index.html', page='inventory_preview',
                           parsed_data=parsed,
                           all_items=Item.query.order_by(Item.name).all(),
                           pdf_filename=file.filename)

@app.route('/inventory/confirm-pdf', methods=['POST'])
@login_required
def confirm_inventory_pdf():
    """미리보기에서 수정한 재고 데이터를 확정 저장"""
    item_ids = request.form.getlist('item_id')
    qtys = request.form.getlist('qty')
    count = 0
    for i, item_id_str in enumerate(item_ids):
        if not item_id_str or item_id_str == '0':
            continue
        try:
            item_id = int(item_id_str)
            qty = int(qtys[i]) if i < len(qtys) else 0
        except (ValueError, IndexError):
            continue

        item = Item.query.get(item_id)
        if not item:
            continue

        prev = item.current_stock or 0
        wc = WeeklyCount(
            item_id=item_id,
            counted_qty=qty,
            counted_by=current_user.id,
            counted_at=date.today(),
            prev_system_qty=prev,
            diff=qty - prev,
            status='확정'
        )
        item.current_stock = qty
        db.session.add(wc)
        count += 1

    db.session.commit()
    flash(f'PDF 재고 데이터 {count}건이 확정 저장되었습니다.', 'success')
    return redirect(url_for('inventory'))

@app.route('/categories')
@login_required
def categories():
    cats = Category.query.all()
    return render_template('index.html', page='categories', categories=cats)

@app.route('/categories/create', methods=['POST'])
@login_required
def create_category():
    name = request.form['name'].strip()
    if name and not Category.query.filter_by(name=name).first():
        db.session.add(Category(name=name))
        db.session.commit()
        flash(f'카테고리 "{name}" 추가 완료', 'success')
    return redirect(url_for('categories'))

@app.route('/categories/<int:cat_id>/rename', methods=['POST'])
@login_required
def rename_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    new_name = request.form['name'].strip()
    if new_name and new_name != cat.name:
        if Category.query.filter_by(name=new_name).first():
            flash(f'"{new_name}" 카테고리가 이미 존재합니다.', 'error')
        else:
            old = cat.name
            cat.name = new_name
            db.session.commit()
            flash(f'"{old}" → "{new_name}" 수정 완료', 'success')
    return redirect(url_for('categories'))

@app.route('/categories/<int:cat_id>/delete', methods=['POST'])
@login_required
def delete_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    if len(cat.items) > 0:
        flash('상품이 연결된 카테고리는 삭제할 수 없습니다.', 'error')
    else:
        db.session.delete(cat)
        db.session.commit()
        flash(f'카테고리 "{cat.name}" 삭제 완료', 'success')
    return redirect(url_for('categories'))

@app.route('/books')
@login_required
def books():
    items_b = Item.query.filter(Item.line.contains('B')).all()
    return render_template('index.html', page='books', items_b=items_b)

@app.route('/kakao')
@login_required
def kakao():
    events = KakaoEvent.query.order_by(KakaoEvent.period_start.desc()).all()
    items_all = Item.query.order_by(Item.name).all()
    return render_template('index.html', page='kakao', events=events, items_all=items_all)

@app.route('/kakao/create', methods=['POST'])
@login_required
def create_kakao_event():
    bundles_raw = request.form.getlist('bundle_items')  # item_id 목록
    bundles_json = json.dumps(bundles_raw) if bundles_raw else '[]'
    ev = KakaoEvent(
        name=request.form['name'],
        period_start=date.fromisoformat(request.form['period_start']) if request.form.get('period_start') else None,
        period_end=date.fromisoformat(request.form['period_end']) if request.form.get('period_end') else None,
        status=request.form.get('status', '기획중'),
        bundles=bundles_json,
        memo=request.form.get('memo', ''),
    )
    db.session.add(ev)
    db.session.flush()  # get ev.id

    # ── 자동 업무 생성: 번들 상품별 준비 Task ──
    from datetime import timedelta
    bundle_ids = json.loads(bundles_json) if bundles_json else []
    prep_due = ev.period_start - timedelta(days=7) if ev.period_start else None
    for bid in bundle_ids:
        item = Item.query.get(int(bid))
        if not item:
            continue
        task = Task(
            title=f'[카카오] {ev.name} — {item.name} 준비',
            description=f'카카오메이커스 이벤트 "{ev.name}" 번들 상품 준비\n기간: {ev.period_start} ~ {ev.period_end}',
            item_id=item.id,
            assignee_id=item.owner_id or current_user.id,
            status='대기',
            priority='높음',
            stage='기획',
            start_date=date.today(),
            due_date=prep_due,
        )
        db.session.add(task)
    # 번들이 없어도 이벤트 전체 준비 Task 1개 생성
    if not bundle_ids:
        task = Task(
            title=f'[카카오] {ev.name} 준비',
            description=f'카카오메이커스 이벤트 "{ev.name}" 준비\n기간: {ev.period_start} ~ {ev.period_end}',
            assignee_id=current_user.id,
            status='대기',
            priority='높음',
            stage='기획',
            start_date=date.today(),
            due_date=prep_due,
        )
        db.session.add(task)

    db.session.commit()
    flash(f'카카오메이커스 이벤트 "{ev.name}" 등록! 업무 {max(len(bundle_ids),1)}건 자동 생성', 'success')
    return redirect(url_for('kakao'))

@app.route('/kakao/<int:event_id>/update', methods=['POST'])
@login_required
def update_kakao_event(event_id):
    ev = KakaoEvent.query.get_or_404(event_id)
    ev.name = request.form.get('name', ev.name)
    ev.status = request.form.get('status', ev.status)
    ev.total_sold = int(request.form['total_sold']) if request.form.get('total_sold') else ev.total_sold
    ev.memo = request.form.get('memo', ev.memo)
    if request.form.get('period_start'):
        ev.period_start = date.fromisoformat(request.form['period_start'])
    if request.form.get('period_end'):
        ev.period_end = date.fromisoformat(request.form['period_end'])
    bundles_raw = request.form.getlist('bundle_items')
    if bundles_raw:
        ev.bundles = json.dumps(bundles_raw)
    db.session.commit()
    flash(f'이벤트 "{ev.name}" 수정 완료', 'success')
    return redirect(url_for('kakao'))

@app.route('/kakao/<int:event_id>/delete', methods=['POST'])
@login_required
def delete_kakao_event(event_id):
    ev = KakaoEvent.query.get_or_404(event_id)
    name = ev.name
    db.session.delete(ev)
    db.session.commit()
    flash(f'이벤트 "{name}" 삭제', 'info')
    return redirect(url_for('kakao'))

@app.route('/ideas')
@login_required
def ideas():
    all_ideas = Idea.query.order_by(Idea.created_at.desc()).all()
    users = User.query.all()
    categories = Category.query.order_by(Category.name).all()
    return render_template('index.html', page='ideas', ideas=all_ideas, users=users, categories=categories)

@app.route('/ideas/create', methods=['POST'])
@login_required
def create_idea():
    idea = Idea(
        title=request.form['title'],
        description=request.form.get('description', ''),
        proposer_id=current_user.id,
        line=request.form.get('line', ''),
        category=request.form.get('category', ''),
        artist=request.form.get('artist', ''),
    )
    db.session.add(idea)
    db.session.flush()

    # 편집장/행정팀장/소장에게 새 아이디어 알림
    noti_msg = f'{current_user.name}님이 새 아이디어를 제안했습니다: "{idea.title}"'
    noti_link = url_for('ideas')
    noti_roles = get_roles_with_perm('receive_notifications')
    reviewers = User.query.filter(User.role.in_(noti_roles)).all()
    for rev in reviewers:
        if rev.id != current_user.id:
            noti = Notification(
                recipient_id=rev.id,
                message=noti_msg,
                link=noti_link,
                noti_type='아이디어',
            )
            db.session.add(noti)

    db.session.commit()
    flash(f'아이디어 "{idea.title}" 제안 완료!', 'success')
    return redirect(url_for('ideas'))

@app.route('/ideas/<int:idea_id>/review', methods=['POST'])
@login_required
def review_idea(idea_id):
    idea = Idea.query.get_or_404(idea_id)
    action = request.form['action']  # 승인/보류/반려
    if action == '승인':
        idea.status = '승인'
        idea.approved_by = current_user.id
        flash(f'"{idea.title}" 아이디어 승인! 상품 등록 페이지에서 신규 상품을 등록하세요.', 'success')
    elif action == '보류':
        idea.status = '보류'
        flash(f'"{idea.title}" 아이디어 보류', 'info')
    elif action == '반려':
        idea.status = '반려'
        idea.reject_reason = request.form.get('reason', '')
        flash(f'"{idea.title}" 아이디어 반려', 'warning')
    elif action == '검토중':
        idea.status = '검토중'
        flash(f'"{idea.title}" 검토 시작', 'info')
    db.session.commit()
    return redirect(url_for('ideas'))

@app.route('/checklist')
@login_required
def checklist():
    items_active = Item.query.filter(Item.status.in_(['기획중','디자인중','제작중','입고대기'])).all()
    # 각 품목별 체크리스트 항목 + 진행률
    items_checklists = []
    for it in items_active:
        checks = ChecklistItem.query.filter_by(item_id=it.id).order_by(ChecklistItem.sort_order, ChecklistItem.id).all()
        total = len(checks)
        done = sum(1 for c in checks if c.checked)
        pct = round(done / total * 100) if total else 0
        cat_name = it.category_ref.name if it.category_ref else ''
        items_checklists.append({'item': it, 'checks': checks, 'total': total, 'done': done, 'pct': pct, 'cat_name': cat_name})
    return render_template('index.html', page='checklist', items_checklists=items_checklists)

# ─── 체크리스트 자동 생성 ───
CATEGORY_CHECKLISTS = {
    '노트류': [
        ('용지 종류 및 평량 결정 (80g/100g/120g)', '노트류'),
        ('제본 방식 (무선/스프링/실제본/양장)', '노트류'),
        ('내지 디자인 시안 확정', '노트류'),
        ('커버 코팅 처리 (무광/유광/소프트터치)', '노트류'),
        ('페이지 수 결정', '노트류'),
        ('인쇄 색도 확인 (4도/2도/별색)', '노트류'),
        ('바코드/ISBN 삽입 여부', '노트류'),
        ('포장 방식 (OPP/박스/밴드)', '노트류'),
    ],
    '생활용품': [
        ('소재 및 원단 결정', '생활용품'),
        ('안전인증 필요 여부 (KC인증 등)', '생활용품'),
        ('사이즈 규격 확정', '생활용품'),
        ('색상/패턴 시안 확정', '생활용품'),
        ('포장 방식 결정', '생활용품'),
        ('내구성 테스트', '생활용품'),
        ('세탁/사용 안내문 삽입', '생활용품'),
    ],
    '지류': [
        ('용지 종류 및 평량', '지류'),
        ('인쇄 색도 (4도/별색)', '지류'),
        ('후가공 (형압/박/코팅/도무송)', '지류'),
        ('사이즈 규격', '지류'),
        ('세트 구성 및 봉투 여부', '지류'),
        ('포장 방식', '지류'),
    ],
    '아트': [
        ('원본 작품 해상도 확인 (300dpi 이상)', '아트'),
        ('아티스트 저작권/라이선스 확인', '아트'),
        ('액자/마운팅 방식', '아트'),
        ('에디션 넘버링 여부', '아트'),
        ('인증서 동봉 여부', '아트'),
        ('포장 및 운송 보호', '아트'),
    ],
}
DEFAULT_CHECKLIST = [
    ('디자인 시안 확정', '공통'),
    ('견적 비교 (최소 2곳)', '공통'),
    ('샘플 제작 및 검수', '공통'),
    ('포장 방식 결정', '공통'),
    ('단가 한도 확인', '공통'),
    ('납기일 확인', '공통'),
]
COMMON_CHECKS = [
    ('브랜드 가이드라인 준수', '공통'),
    ('단가 한도 준수 (A라인 4,000원 이하)', '공통'),
    ('목표 수량 및 MOQ 확인', '공통'),
]

def _create_checklist_for_item(item):
    """품목의 카테고리에 맞는 체크리스트 항목 생성 (내부 헬퍼, commit 하지 않음)"""
    existing = ChecklistItem.query.filter_by(item_id=item.id).count()
    if existing > 0:
        return 0  # 이미 있으면 스킵

    cat_name = item.category_ref.name if item.category_ref else ''
    cat_checks = CATEGORY_CHECKLISTS.get(cat_name, DEFAULT_CHECKLIST)

    order = 0
    for label, cat in COMMON_CHECKS:
        ci = ChecklistItem(item_id=item.id, label=label, category=cat, sort_order=order)
        db.session.add(ci)
        order += 1
    for label, cat in cat_checks:
        ci = ChecklistItem(item_id=item.id, label=label, category=cat, sort_order=order)
        db.session.add(ci)
        order += 1
    return order

@app.route('/checklist/generate/<int:item_id>', methods=['POST'])
@login_required
def generate_checklist(item_id):
    """품목의 카테고리에 맞는 체크리스트 자동 생성 (수동 버튼용)"""
    item = Item.query.get_or_404(item_id)
    existing = ChecklistItem.query.filter_by(item_id=item_id).count()
    if existing > 0:
        return jsonify({'ok': False, 'error': '이미 체크리스트가 있습니다. 초기화하려면 먼저 삭제하세요.'})

    total = _create_checklist_for_item(item)
    db.session.commit()
    return jsonify({'ok': True, 'count': total})

@app.route('/checklist/toggle/<int:check_id>', methods=['POST'])
@login_required
def toggle_check(check_id):
    """체크리스트 항목 체크/해제 토글"""
    ci = ChecklistItem.query.get_or_404(check_id)
    ci.checked = not ci.checked
    if ci.checked:
        ci.checked_by = current_user.id
        ci.checked_at = datetime.utcnow()
    else:
        ci.checked_by = None
        ci.checked_at = None
    db.session.commit()
    # 해당 품목의 진행률 반환
    total = ChecklistItem.query.filter_by(item_id=ci.item_id).count()
    done = ChecklistItem.query.filter_by(item_id=ci.item_id, checked=True).count()
    pct = round(done / total * 100) if total else 0
    return jsonify({'ok': True, 'checked': ci.checked, 'pct': pct, 'done': done, 'total': total})

@app.route('/checklist/add/<int:item_id>', methods=['POST'])
@login_required
def add_check_item(item_id):
    """수동으로 체크리스트 항목 추가"""
    item = Item.query.get_or_404(item_id)
    label = request.form.get('label', '').strip()
    if not label:
        return jsonify({'ok': False, 'error': '항목명을 입력하세요'})
    max_order = db.session.query(db.func.max(ChecklistItem.sort_order)).filter_by(item_id=item_id).scalar() or 0
    ci = ChecklistItem(item_id=item_id, label=label, category='수동추가', sort_order=max_order + 1)
    db.session.add(ci)
    db.session.commit()
    return jsonify({'ok': True, 'id': ci.id, 'label': ci.label})

@app.route('/checklist/delete/<int:check_id>', methods=['POST'])
@login_required
def delete_check_item(check_id):
    """체크리스트 항목 삭제"""
    ci = ChecklistItem.query.get_or_404(check_id)
    item_id = ci.item_id
    db.session.delete(ci)
    db.session.commit()
    total = ChecklistItem.query.filter_by(item_id=item_id).count()
    done = ChecklistItem.query.filter_by(item_id=item_id, checked=True).count()
    pct = round(done / total * 100) if total else 0
    return jsonify({'ok': True, 'pct': pct, 'done': done, 'total': total})

@app.route('/checklist/ai-suggest/<int:item_id>', methods=['POST'])
@login_required
def ai_suggest_checks(item_id):
    """AI 기반 추가 체크 항목 제안 — 품목 특성에 맞춘 맞춤 가이드"""
    item = Item.query.get_or_404(item_id)
    cat_name = item.category_ref.name if item.category_ref else ''
    line = item.line or ''

    suggestions = []

    # 라인별 추가 제안
    if 'A' in line:
        suggestions.extend([
            '구독자 선호도 조사 (최근 설문 반영)',
            '구독 발송 시 동봉 가능 사이즈/무게 확인',
            '포장 후 우편요금 추가비용 검토',
            '구독갱신 시즌 (1월/7월) 타이밍 맞춤 확인',
        ])
    if 'B' in line:
        suggestions.extend([
            '아티스트 콜라보 계약서 확인',
            '스마트스토어 상세페이지 촬영 일정',
            '앵두 사이트 등록 준비 (상품설명/이미지)',
        ])
    if 'C' in line:
        suggestions.extend([
            '카카오메이커스 입점 조건 확인',
            '카카오 전용 패키지/라벨 필요 여부',
            '카카오 판매 수수료 반영한 단가 재검토',
        ])

    # 카테고리별 심화 제안
    cat_suggestions = {
        '노트류': [
            '경쟁 제품 벤치마킹 (디자인/단가)',
            '내지 여백 비율 테스트 (사용성)',
            '커버 타이틀 명언/문구 최종 선정',
            '시제품 실사용 테스트 (직원 3인 이상)',
        ],
        '생활용품': [
            '유사 제품 소비자 리뷰 분석',
            '색상 시뮬레이션 (모니터 vs 실물 차이)',
            '포장재 친환경 옵션 검토',
            '사용 설명서 다국어 필요 여부',
        ],
        '지류': [
            '봉투/케이스 사이즈 호환성',
            '후가공 비용 대비 효과 검토',
            '특수 인쇄 (별색/형광) 필요시 테스트 인쇄',
        ],
        '아트': [
            '에디션 수량 대비 가격 전략',
            '아티스트 SNS 홍보 협의',
            '전시 연계 판매 가능성 검토',
            '보관/운송 시 손상 방지 방안',
        ],
        '명언집': [
            '명언 저작권/출처 확인',
            '폰트 라이선스 확인',
            '기존 명언집과 중복 내용 체크',
        ],
    }
    suggestions.extend(cat_suggestions.get(cat_name, [
        '타겟 고객층 명확히 정의',
        '유사 제품 시장 조사',
        '판매 채널별 마진율 계산',
    ]))

    # 수량별 제안
    if item.target_qty:
        if item.target_qty >= 3000:
            suggestions.append('대량 생산 — 2차 발주 가능성 및 보관 장소 확보')
        elif item.target_qty < 500:
            suggestions.append('소량 생산 — MOQ 미달 시 단가 상승 대비')

    # 기존 체크리스트에 없는 것만 필터
    existing_labels = set(c.label for c in ChecklistItem.query.filter_by(item_id=item_id).all())
    suggestions = [s for s in suggestions if s not in existing_labels]

    return jsonify({'ok': True, 'suggestions': suggestions})

@app.route('/ai-check')
@login_required
def ai_check():
    categories = Category.query.order_by(Category.name).all()
    environ_claude = bool(os.environ.get('ANTHROPIC_API_KEY') or app.config.get('ANTHROPIC_API_KEY'))
    return render_template('index.html', page='ai_check', categories=categories, environ_claude=environ_claude)

@app.route('/ai-check/set-key', methods=['POST'])
@login_required
def set_claude_key():
    key = request.form.get('api_key', '').strip()
    if key:
        app.config['ANTHROPIC_API_KEY'] = key
        # .env 파일에도 저장 (재시작 시 유지)
        env_path = os.path.join(BASE_DIR, '.env')
        lines = []
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                lines = [l for l in f.readlines() if not l.startswith('ANTHROPIC_API_KEY=')]
        lines.append(f'ANTHROPIC_API_KEY={key}\n')
        with open(env_path, 'w') as f:
            f.writelines(lines)
        flash('분석 엔진 키가 저장되었습니다!', 'success')
    return redirect(url_for('ai_check'))

@app.route('/ai-check/analyze', methods=['POST'])
@login_required
def ai_analyze():
    """제작 타당성 분석 + 체크리스트 자동 생성"""
    import urllib.request, urllib.error

    item_name = request.form.get('item_name', '')
    item_line = request.form.get('line', '')
    item_category = request.form.get('category', '')
    target_qty = request.form.get('target_qty', '')
    budget = request.form.get('budget', '')
    selling_price = request.form.get('selling_price', '')
    description = request.form.get('description', '')

    line_desc = {'A': '정기구독 사은품', 'B': '앵두/단행본 굿즈', 'C': '카카오메이커스', 'A,B': '정기구독+앵두/단행본', 'B,C': '앵두+카카오메이커스'}
    line_label = line_desc.get(item_line, item_line or '미정')

    # 유사 품목 검색 (DB)
    similar = []
    if item_category:
        similar_items = Item.query.join(Category).filter(Category.name == item_category).all()
        for si in similar_items[:5]:
            similar.append({
                'name': si.name, 'line': si.line, 'cost': si.unit_cost,
                'status': si.status, 'stock': si.current_stock
            })

    # ── Claude API 호출 ──
    claude_key = app.config.get('ANTHROPIC_API_KEY') or os.environ.get('ANTHROPIC_API_KEY', '')
    ai_analysis = ''
    ai_checklist = []

    if claude_key:
        # 기존 유사상품 정보 컨텍스트
        similar_ctx = ''
        if similar:
            similar_ctx = '\n기존 유사 상품:\n' + '\n'.join(
                f"- {s['name']} ({s['line']}): 단가 {s['cost']:,}원, 상태 {s['status']}, 재고 {s['stock'] or 0}개"
                for s in similar if s['cost']
            )

        prompt = f"""당신은 출판사 굿즈(사은품/상품) 제작 전문 컨설턴트입니다.
다음 굿즈 기획에 대해 분석해주세요.

[기획 정보]
- 상품명: {item_name}
- 사업 라인: {line_label}
- 카테고리: {item_category or '미정'}
- 예상 단가: {budget + '원' if budget else '미정'}
- 희망 판매가: {selling_price + '원' if selling_price else '미정'}
- 목표 수량: {target_qty + '개' if target_qty else '미정'}
- 기획 설명: {description or '없음'}
{similar_ctx}

[주의사항]
- 정기구독 사은품(A라인)은 단가 4,000원 이하가 원칙입니다
- 출판사 '좋은생각'의 브랜드 — 명언, 글, 사진 위주의 따뜻한 감성
- 앵두/단행본 라인은 아티스트 콜라보, 좀 더 젊고 세련된 스타일

다음 형식으로 답해주세요 (JSON):
{{
  "feasibility": "타당성 평가 (2~3문장, 장점/주의사항 포함)",
  "cost_analysis": "단가 적정성 분석 (1~2문장)",
  "margin": "마진 분석 — 단가와 희망 판매가 기반 마진율과 수익성 평가 (1~2문장, 판매가 미입력 시 '판매가 미입력'으로 표시)",
  "lead_time": "예상 제작 기간과 일정 조언 (1~2문장)",
  "risk": "주요 리스크 1~2가지",
  "tip": "성공을 위한 실무 팁 1~2가지"
}}

반드시 유효한 JSON만 출력하세요. 다른 텍스트 없이 JSON만."""

        try:
            api_url = "https://api.anthropic.com/v1/messages"
            payload = json.dumps({
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1500,
                "messages": [{"role": "user", "content": prompt}]
            }).encode('utf-8')

            req = urllib.request.Request(api_url, data=payload, headers={
                'Content-Type': 'application/json',
                'x-api-key': claude_key,
                'anthropic-version': '2023-06-01'
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode('utf-8'))

            # Claude 응답 파싱
            raw_text = ''
            for block in body.get('content', []):
                if block.get('type') == 'text':
                    raw_text += block.get('text', '')
            # JSON 블록 추출 (```json ... ``` 또는 순수 JSON)
            import re
            json_match = re.search(r'\{[\s\S]*\}', raw_text)
            if json_match:
                ai_data = json.loads(json_match.group())
                ai_analysis = ai_data
            else:
                ai_analysis = {'feasibility': raw_text, 'cost_analysis': '', 'lead_time': '', 'risk': '', 'tip': ''}

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ''
            ai_analysis = {'error': f'분석 엔진 오류 ({e.code}): {error_body[:200]}'}
        except Exception as e:
            ai_analysis = {'error': f'분석 중 오류: {str(e)}'}

    # 체크리스트는 항상 룰 기반 (카테고리별 내장 데이터)
    checklists = {
        '노트류': ['용지 종류 및 평량 결정 (80g/100g/120g)', '제본 방식 (무선/스프링/실제본/양장)', '내지 디자인 시안 확정', '커버 코팅 처리 (무광/유광/소프트터치)', '페이지 수 결정', '인쇄 색도 확인 (4도/2도/별색)', '바코드/ISBN 삽입 여부', '포장 방식 (OPP/박스/밴드)'],
        '생활용품': ['소재 및 원단 결정', '안전인증 필요 여부 (KC인증 등)', '사이즈 규격 확정', '색상/패턴 시안 확정', '포장 방식 결정', '내구성 테스트', '세탁/사용 안내문 삽입'],
        '지류': ['용지 종류 및 평량', '인쇄 색도 (4도/별색)', '후가공 (형압/박/코팅/도무송)', '사이즈 규격', '세트 구성 및 봉투 여부', '포장 방식'],
        '아트': ['원본 작품 해상도 확인 (300dpi 이상)', '아티스트 저작권/라이선스 확인', '액자/마운팅 방식', '에디션 넘버링 여부', '인증서 동봉 여부', '포장 및 운송 보호'],
        '캐릭터 굿즈': ['캐릭터 저작권/라이선스 확인', '디자인 시안 확정', '소재 결정', '사이즈 규격 확정', '안전인증 (KC인증)', '포장 방식 결정', '태그/라벨 디자인'],
        '달력/일력': ['용지 종류 및 평량', '제본/걸이 방식', '달력 구조 (탁상/벽걸이/일력)', '사진/이미지 해상도 확인', '인쇄 색도', '포장 방식'],
        '명언집': ['수록 명언 선별 및 저작권 확인', '용지 종류 및 평량', '제본 방식', '커버 디자인 확정', '인쇄 색도', '사이즈 규격', 'ISBN 발급 여부'],
    }
    default_checklist = ['디자인 시안 확정', '견적 비교 (최소 2곳)', '샘플 제작 및 검수', '포장 방식 결정', '단가 한도 확인', '납기일 확인']
    ai_checklist = checklists.get(item_category, default_checklist)

    if not claude_key:
        # API 키 없으면 타당성도 룰 기반 폴백
        lead_times = {'노트류': '약 4~6주', '생활용품': '약 6~10주', '지류': '약 2~4주', '아트': '약 4~8주'}
        cost_note = ''
        if item_line == 'A' and budget:
            cost_note = '❌ 단가 한도 초과' if int(budget) >= 4000 else f'✅ 단가 {int(budget):,}원 적합'
        margin_note = '판매가 미입력'
        if budget and selling_price:
            try:
                b, sp = int(budget), int(selling_price)
                if sp > 0:
                    margin_pct = round((sp - b) / sp * 100, 1)
                    margin_note = f'마진율 약 {margin_pct}% (단가 {b:,}원 → 판매가 {sp:,}원)'
            except ValueError:
                pass
        ai_analysis = {
            'feasibility': f'{item_name} — 기본 분석입니다. 고급 분석을 사용하려면 분석 엔진 키를 설정해주세요.',
            'cost_analysis': cost_note or '단가 정보 미입력',
            'margin': margin_note,
            'lead_time': lead_times.get(item_category, '약 4~8주'),
            'risk': '',
            'tip': '',
            'no_api_key': True,
        }

    result = {
        'item_name': item_name,
        'line_desc': line_label,
        'ai': ai_analysis,
        'checklist': ai_checklist,
        'similar': similar,
    }
    return jsonify(result)

@app.route('/cost')
@login_required
def cost():
    items_all = Item.query.order_by(Item.name).all()
    # 상품별 비용 합산 + 예상단가 비교
    item_costs = []
    for it in items_all:
        records = CostRecord.query.filter_by(item_id=it.id).order_by(CostRecord.cost_date.desc(), CostRecord.id.desc()).all()
        total = sum(r.amount for r in records)
        est_total = (it.unit_cost or 0) * (it.target_qty or 0)
        item_costs.append({
            'item': it, 'records': records, 'total': total,
            'est_total': est_total,
            'diff': total - est_total if est_total else None,
        })
    return render_template('index.html', page='cost', item_costs=item_costs, items_all=items_all, today=date.today())

@app.route('/cost/add', methods=['POST'])
@login_required
def add_cost():
    item_id = int(request.form['item_id'])
    label = request.form['label'].strip()
    amount = int(request.form['amount'])
    cost_date_str = request.form.get('cost_date', '')
    cost_date = date.fromisoformat(cost_date_str) if cost_date_str else date.today()
    note = request.form.get('note', '').strip()
    cr = CostRecord(item_id=item_id, label=label, amount=amount,
                    cost_date=cost_date, added_by=current_user.id, note=note)
    db.session.add(cr)
    db.session.commit()
    return jsonify({'ok': True, 'id': cr.id})

@app.route('/cost/delete/<int:cost_id>', methods=['POST'])
@login_required
def delete_cost(cost_id):
    cr = CostRecord.query.get_or_404(cost_id)
    db.session.delete(cr)
    db.session.commit()
    return jsonify({'ok': True})

@app.route('/profile', methods=['GET','POST'])
@login_required
def profile():
    if request.method == 'POST':
        new_name = request.form.get('name', '').strip()
        new_email = request.form.get('email', '').strip()
        new_pw = request.form.get('new_password', '').strip()
        confirm_pw = request.form.get('confirm_password', '').strip()

        if new_name and new_name != current_user.name:
            old_name = current_user.name
            current_user.name = new_name
            flash(f'이름이 "{old_name}" → "{new_name}"으로 변경되었습니다.', 'success')
        if new_email:
            current_user.email = new_email
        if new_pw:
            if new_pw != confirm_pw:
                flash('새 비밀번호가 일치하지 않습니다.', 'error')
                return redirect(url_for('profile'))
            current_user.password_hash = generate_password_hash(new_pw)
            flash('비밀번호가 변경되었습니다.', 'success')

        db.session.commit()
        return redirect(url_for('profile'))

    return render_template('index.html', page='profile')

# ═══ 권한 시스템 ═══
PERMISSION_DEFS = {
    'view_all_tasks': '전체 업무 열람',
    'manage_users': '사용자 관리',
    'review_ideas': '아이디어 승인/반려',
    'receive_notifications': '알림 수신 (파일첨부, 아이디어 등)',
    'manage_items': '상품 등록/수정',
    'manage_inventory': '재고 관리',
    'manage_costs': '비용 관리',
    'manage_checklist': '퀄리티 체크리스트',
    'use_ai_check': '제작 가이드 사용',
    'manage_kakao': '카카오메이커스 관리',
}

DEFAULT_ROLES = [
    {'name': '소장', 'description': '총괄 디렉터', 'is_admin': True, 'sort_order': 1},
    {'name': '편집장', 'description': '편집 총괄', 'is_admin': True, 'sort_order': 2},
    {'name': '행정팀장', 'description': '행정/스케줄 관리', 'is_admin': True, 'sort_order': 3},
    {'name': '실무자', 'description': '굿즈 기획/제작 실무', 'is_admin': False, 'sort_order': 10},
    {'name': '디자이너', 'description': '디자인 담당', 'is_admin': False, 'sort_order': 11},
    {'name': '구독매니저1', 'description': '구독 관리 (정황규)', 'is_admin': False, 'sort_order': 20},
    {'name': '구독매니저2', 'description': '구독 관리', 'is_admin': False, 'sort_order': 21},
]

DEFAULT_PERMISSIONS = {
    '소장':       ['view_all_tasks', 'manage_users', 'review_ideas', 'receive_notifications', 'manage_items', 'manage_inventory', 'manage_costs', 'manage_checklist', 'use_ai_check', 'manage_kakao'],
    '편집장':     ['view_all_tasks', 'manage_users', 'review_ideas', 'receive_notifications', 'manage_items', 'manage_inventory', 'manage_costs', 'manage_checklist', 'use_ai_check', 'manage_kakao'],
    '행정팀장':   ['view_all_tasks', 'manage_users', 'review_ideas', 'receive_notifications', 'manage_items', 'manage_inventory', 'manage_costs', 'manage_checklist', 'use_ai_check', 'manage_kakao'],
    '실무자':     ['manage_items', 'manage_inventory', 'manage_costs', 'manage_checklist', 'use_ai_check', 'manage_kakao'],
    '디자이너':   ['manage_items', 'manage_checklist', 'use_ai_check'],
    '구독매니저1': ['manage_inventory', 'manage_costs', 'manage_checklist'],
    '구독매니저2': ['manage_inventory', 'manage_costs', 'manage_checklist'],
}

def get_all_roles():
    """DB에서 역할 목록을 정렬하여 반환 (이름 리스트)"""
    roles = Role.query.order_by(Role.sort_order, Role.name).all()
    if roles:
        return [r.name for r in roles]
    return [r['name'] for r in DEFAULT_ROLES]

def get_all_role_objects():
    """DB에서 역할 객체 목록 반환"""
    return Role.query.order_by(Role.sort_order, Role.name).all()

def seed_roles():
    """기본 역할이 없으면 초기화"""
    if Role.query.first():
        return
    for rd in DEFAULT_ROLES:
        r = Role(name=rd['name'], description=rd['description'],
                 is_admin=rd['is_admin'], sort_order=rd['sort_order'])
        db.session.add(r)
    db.session.commit()

def seed_permissions():
    """기본 권한이 없으면 초기화"""
    existing = RolePermission.query.first()
    if existing:
        return
    for role, perms in DEFAULT_PERMISSIONS.items():
        for perm_key in PERMISSION_DEFS:
            rp = RolePermission(role=role, permission=perm_key, enabled=(perm_key in perms))
            db.session.add(rp)
    db.session.commit()

def has_perm(permission, role=None):
    """현재 사용자(또는 지정 역할)가 특정 권한을 가지고 있는지 확인"""
    r = role or current_user.role
    rp = RolePermission.query.filter_by(role=r, permission=permission).first()
    if rp:
        return rp.enabled
    # DB에 없으면 기본값 참조
    return permission in DEFAULT_PERMISSIONS.get(r, [])

def is_admin():
    return has_perm('manage_users')

def get_roles_with_perm(permission):
    """특정 권한을 가진 역할 목록 반환"""
    perms = RolePermission.query.filter_by(permission=permission, enabled=True).all()
    return [p.role for p in perms]

@app.route('/admin/users')
@login_required
def admin_users():
    if not is_admin():
        flash('관리자만 접근할 수 있습니다.', 'error')
        return redirect(url_for('dashboard'))
    users = User.query.order_by(User.role, User.name).all()
    all_roles = get_all_roles()
    return render_template('index.html', page='admin_users', all_users=users, all_roles=all_roles)

@app.route('/admin/users/create', methods=['POST'])
@login_required
def admin_create_user():
    if not is_admin():
        flash('관리자만 사용자를 추가할 수 있습니다.', 'error')
        return redirect(url_for('dashboard'))
    username = request.form['username'].strip()
    name = request.form['name'].strip()
    role = request.form['role']
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '1234').strip() or '1234'

    if User.query.filter_by(username=username).first():
        flash(f'아이디 "{username}"이 이미 존재합니다.', 'error')
        return redirect(url_for('admin_users'))

    u = User(username=username, password_hash=generate_password_hash(password),
             name=name, role=role, email=email)
    db.session.add(u)
    db.session.commit()
    flash(f'사용자 "{name}" ({role}) 추가 완료. 초기 비밀번호: {password}', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/edit', methods=['POST'])
@login_required
def admin_edit_user(user_id):
    if not is_admin():
        flash('관리자만 사용자 정보를 변경할 수 있습니다.', 'error')
        return redirect(url_for('dashboard'))
    user = User.query.get_or_404(user_id)
    new_name = request.form.get('name', '').strip()
    new_role = request.form.get('role', '')
    new_email = request.form.get('email', '').strip()
    new_username = request.form.get('username', '').strip()
    reset_pw = request.form.get('reset_password', '')

    if new_name:
        user.name = new_name
    if new_role:
        user.role = new_role
    if new_email:
        user.email = new_email
    if new_username and new_username != user.username:
        if User.query.filter_by(username=new_username).first():
            flash(f'아이디 "{new_username}"이 이미 존재합니다.', 'error')
            return redirect(url_for('admin_users'))
        user.username = new_username
    if reset_pw:
        user.password_hash = generate_password_hash(reset_pw)
        flash(f'"{user.name}" 비밀번호가 재설정되었습니다.', 'info')

    db.session.commit()
    flash(f'"{user.name}" 정보가 수정되었습니다.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if not is_admin():
        flash('관리자만 사용자를 삭제할 수 있습니다.', 'error')
        return redirect(url_for('dashboard'))
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('자기 자신은 삭제할 수 없습니다.', 'error')
        return redirect(url_for('admin_users'))
    # 연결된 품목/태스크의 담당자를 null로
    Item.query.filter_by(owner_id=user_id).update({'owner_id': None})
    Task.query.filter_by(assignee_id=user_id).update({'assignee_id': None})
    name = user.name
    db.session.delete(user)
    db.session.commit()
    flash(f'사용자 "{name}"이 삭제되었습니다.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/permissions')
@login_required
def admin_permissions():
    if not is_admin():
        flash('관리자만 접근할 수 있습니다.', 'error')
        return redirect(url_for('dashboard'))
    # 역할별 권한 매트릭스 구성
    all_roles = get_all_roles()
    role_objects = get_all_role_objects()
    perm_matrix = {}
    for role in all_roles:
        perm_matrix[role] = {}
        for perm_key in PERMISSION_DEFS:
            rp = RolePermission.query.filter_by(role=role, permission=perm_key).first()
            perm_matrix[role][perm_key] = rp.enabled if rp else (perm_key in DEFAULT_PERMISSIONS.get(role, []))
    all_users = User.query.all()
    return render_template('index.html', page='admin_permissions',
                           perm_matrix=perm_matrix, perm_defs=PERMISSION_DEFS,
                           all_roles=all_roles, role_objects=role_objects,
                           all_users=all_users)

@app.route('/admin/permissions/update', methods=['POST'])
@login_required
def admin_update_permissions():
    if not is_admin():
        flash('관리자만 권한을 변경할 수 있습니다.', 'error')
        return redirect(url_for('dashboard'))
    for role in get_all_roles():
        for perm_key in PERMISSION_DEFS:
            field_name = f'perm_{role}_{perm_key}'
            enabled = field_name in request.form
            rp = RolePermission.query.filter_by(role=role, permission=perm_key).first()
            if rp:
                rp.enabled = enabled
            else:
                rp = RolePermission(role=role, permission=perm_key, enabled=enabled)
                db.session.add(rp)
    db.session.commit()
    flash('권한 설정이 저장되었습니다.', 'success')
    return redirect(url_for('admin_permissions'))

# ── 역할 관리 ──
@app.route('/admin/roles/create', methods=['POST'])
@login_required
def admin_create_role():
    if not is_admin():
        flash('관리자만 역할을 추가할 수 있습니다.', 'error')
        return redirect(url_for('dashboard'))
    name = request.form.get('role_name', '').strip()
    desc = request.form.get('role_desc', '').strip()
    is_adm = 'role_is_admin' in request.form
    if not name:
        flash('역할 이름을 입력해주세요.', 'error')
        return redirect(url_for('admin_permissions'))
    if Role.query.filter_by(name=name).first():
        flash(f'역할 "{name}"이(가) 이미 존재합니다.', 'error')
        return redirect(url_for('admin_permissions'))
    max_order = db.session.query(db.func.max(Role.sort_order)).scalar() or 0
    role = Role(name=name, description=desc, is_admin=is_adm, sort_order=max_order + 10)
    db.session.add(role)
    # 새 역할에 대한 기본 권한 생성 (모두 off)
    for perm_key in PERMISSION_DEFS:
        rp = RolePermission(role=name, permission=perm_key, enabled=False)
        db.session.add(rp)
    db.session.commit()
    flash(f'역할 "{name}"이(가) 추가되었습니다. 권한을 설정해주세요.', 'success')
    return redirect(url_for('admin_permissions'))

@app.route('/admin/roles/<int:role_id>/edit', methods=['POST'])
@login_required
def admin_edit_role(role_id):
    if not is_admin():
        flash('관리자만 역할을 수정할 수 있습니다.', 'error')
        return redirect(url_for('dashboard'))
    role = Role.query.get_or_404(role_id)
    old_name = role.name
    new_name = request.form.get('role_name', '').strip()
    new_desc = request.form.get('role_desc', '').strip()
    new_is_admin = 'role_is_admin' in request.form
    if new_name and new_name != old_name:
        if Role.query.filter_by(name=new_name).first():
            flash(f'역할 "{new_name}"이(가) 이미 존재합니다.', 'error')
            return redirect(url_for('admin_permissions'))
        # 연결된 사용자, 권한 레코드도 업데이트
        User.query.filter_by(role=old_name).update({'role': new_name})
        RolePermission.query.filter_by(role=old_name).update({'role': new_name})
        role.name = new_name
    if new_desc is not None:
        role.description = new_desc
    role.is_admin = new_is_admin
    db.session.commit()
    flash(f'역할이 수정되었습니다.', 'success')
    return redirect(url_for('admin_permissions'))

@app.route('/admin/roles/<int:role_id>/delete', methods=['POST'])
@login_required
def admin_delete_role(role_id):
    if not is_admin():
        flash('관리자만 역할을 삭제할 수 있습니다.', 'error')
        return redirect(url_for('dashboard'))
    role = Role.query.get_or_404(role_id)
    # 해당 역할을 사용하는 사용자가 있으면 삭제 불가
    users_with_role = User.query.filter_by(role=role.name).count()
    if users_with_role > 0:
        flash(f'역할 "{role.name}"을(를) 사용하는 사용자가 {users_with_role}명 있어 삭제할 수 없습니다. 먼저 사용자의 역할을 변경해주세요.', 'error')
        return redirect(url_for('admin_permissions'))
    # 권한 레코드 삭제
    RolePermission.query.filter_by(role=role.name).delete()
    db.session.delete(role)
    db.session.commit()
    flash(f'역할 "{role.name}"이(가) 삭제되었습니다.', 'success')
    return redirect(url_for('admin_permissions'))

@app.route('/feedback')
@login_required
def feedback():
    fbs = Feedback.query.order_by(Feedback.created_at.desc()).all()
    items_all = Item.query.order_by(Item.name).all()
    return render_template('index.html', page='feedback', feedbacks=fbs, items_all=items_all, today=date.today().isoformat())

@app.route('/feedback/create', methods=['POST'])
@login_required
def create_feedback():
    fb = Feedback(
        item_id=int(request.form['item_id']) if request.form.get('item_id') else None,
        category_type=request.form.get('category_type', '기타'),
        content=request.form['content'],
        channel=request.form.get('channel', ''),
        feedback_date=date.fromisoformat(request.form['feedback_date']) if request.form.get('feedback_date') else date.today(),
        customer_ref=request.form.get('customer_ref', ''),
        book_type=request.form.get('book_type', ''),
    )
    db.session.add(fb)
    db.session.commit()
    flash('피드백 등록 완료', 'success')
    return redirect(url_for('feedback'))

@app.route('/feedback/upload-pdf', methods=['POST'])
@login_required
def upload_feedback_pdf():
    """PDF 업로드 → 텍스트 추출 → 피드백 레코드 자동 생성"""
    file = request.files.get('pdf_file')
    if not file or not file.filename:
        flash('PDF 파일을 선택해주세요.', 'error')
        return redirect(url_for('feedback'))
    if not file.filename.lower().endswith('.pdf'):
        flash('PDF 파일만 업로드 가능합니다.', 'error')
        return redirect(url_for('feedback'))

    # PDF 저장
    safe_name = f"feedback_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{secure_filename(file.filename)}"
    filepath = os.path.join(UPLOAD_DIR, safe_name)
    file.save(filepath)

    # PDF 텍스트 추출
    extracted_text = ''
    try:
        import pdfplumber
        with pdfplumber.open(filepath) as pdf:
            for pg in pdf.pages:
                extracted_text += (pg.extract_text() or '') + '\n'
    except ImportError:
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(filepath)
            for pg in reader.pages:
                extracted_text += (pg.extract_text() or '') + '\n'
        except ImportError:
            # 라이브러리 없으면 raw 텍스트로 저장
            extracted_text = '[PDF 파싱 라이브러리 없음 — 수동 확인 필요]'

    if not extracted_text.strip() or extracted_text.startswith('[PDF'):
        # 파싱 실패 시 전체를 하나의 피드백으로 등록
        fb = Feedback(
            category_type='기타',
            content=extracted_text.strip() or f'[PDF 업로드: {file.filename}]',
            channel='PDF업로드',
            feedback_date=date.today(),
        )
        db.session.add(fb)
        db.session.commit()
        flash(f'PDF 업로드 완료 (텍스트 추출 제한 — 1건 등록)', 'info')
        return redirect(url_for('feedback'))

    # 텍스트를 피드백 항목으로 파싱
    # 더아이앤오 PDF 패턴: 보통 줄 단위 피드백, 구분자 기반 파싱 시도
    lines = [l.strip() for l in extracted_text.split('\n') if l.strip()]
    count = 0

    # 패턴1: "날짜 | 분류 | 내용 | 채널" 탭/파이프 구분
    import re
    date_pattern = re.compile(r'(\d{4}[./-]\d{1,2}[./-]\d{1,2})')

    # 헤더행 스킵 패턴
    header_keywords = ['날짜', '분류', '내용', '채널', '고객', '번호', 'No', '#']

    parsed_rows = []
    for line in lines:
        # 헤더행이면 스킵
        if any(kw in line for kw in header_keywords) and len(line) < 80:
            continue
        # 구분자로 분리 시도 (탭, 파이프, 쉼표)
        parts = None
        for sep in ['\t', '|', ',']:
            trial = [p.strip() for p in line.split(sep) if p.strip()]
            if len(trial) >= 2:
                parts = trial
                break
        if parts and len(parts) >= 2:
            parsed_rows.append(parts)
        elif len(line) > 10:
            # 구분자 없는 긴 텍스트 → 내용으로만 등록
            parsed_rows.append([line])

    for parts in parsed_rows:
        fb_date = date.today()
        fb_category = '기타'
        fb_content = ''
        fb_channel = 'PDF업로드'
        fb_customer = ''

        if len(parts) >= 4:
            # 날짜 | 분류 | 내용 | 채널
            dm = date_pattern.search(parts[0])
            if dm:
                try:
                    fb_date = date.fromisoformat(dm.group(1).replace('.', '-').replace('/', '-'))
                except ValueError:
                    pass
            fb_category = parts[1] if parts[1] in ['컨텐츠이슈', '감사', '불만', '기타'] else '기타'
            fb_content = parts[2]
            fb_channel = parts[3] if len(parts) > 3 else 'PDF업로드'
            fb_customer = parts[4] if len(parts) > 4 else ''
        elif len(parts) >= 2:
            dm = date_pattern.search(parts[0])
            if dm:
                try:
                    fb_date = date.fromisoformat(dm.group(1).replace('.', '-').replace('/', '-'))
                except ValueError:
                    pass
                fb_content = ' '.join(parts[1:])
            else:
                fb_content = ' '.join(parts)
        else:
            fb_content = parts[0]

        if fb_content:
            fb = Feedback(
                category_type=fb_category,
                content=fb_content[:1000],
                channel=fb_channel,
                feedback_date=fb_date,
                customer_ref=fb_customer,
            )
            db.session.add(fb)
            count += 1

    db.session.commit()
    flash(f'PDF에서 {count}건의 피드백을 추출하여 등록했습니다.', 'success')
    return redirect(url_for('feedback'))

@app.route('/feedback/<int:fb_id>/delete', methods=['POST'])
@login_required
def delete_feedback(fb_id):
    fb = Feedback.query.get_or_404(fb_id)
    db.session.delete(fb)
    db.session.commit()
    flash('피드백 삭제 완료', 'info')
    return redirect(url_for('feedback'))

# ═══════════════════════════════════════════
# API endpoints for AJAX
# ═══════════════════════════════════════════
@app.route('/api/dashboard-stats')
@login_required
def dashboard_stats():
    today = date.today()
    month_end = date(today.year, today.month + 1, 1) - timedelta(days=1) if today.month < 12 else date(today.year, 12, 31)
    return jsonify({
        'due_this_month': Task.query.filter(Task.due_date >= today, Task.due_date <= month_end, Task.status != '완료').count(),
        'stock_alerts': sum(1 for i in Item.query.filter(Item.current_stock > 0, Item.status.in_(['소진중','판매중'])).all() if i.current_stock <= (i.target_qty * 0.25 if i.target_qty else 100)),
        'pipeline': Item.query.filter(Item.status.in_(['기획중','디자인중','제작중','입고대기'])).count(),
        'selling': Item.query.filter(Item.status.in_(['판매중','소진중'])).count(),
    })

# ═══════════════════════════════════════════
# NOTIFICATIONS
# ═══════════════════════════════════════════
@app.route('/api/notifications')
@login_required
def get_notifications():
    notis = Notification.query.filter_by(recipient_id=current_user.id, is_read=False)\
        .order_by(Notification.created_at.desc()).limit(20).all()
    return jsonify({'notifications': [{
        'id': n.id,
        'message': n.message,
        'link': n.link,
        'type': n.noti_type,
        'confirmed': n.confirmed,
        'created_at': n.created_at.strftime('%m/%d %H:%M'),
    } for n in notis], 'unread_count': len(notis)})

@app.route('/api/notifications/<int:noti_id>/read', methods=['POST'])
@login_required
def mark_notification_read(noti_id):
    noti = Notification.query.get_or_404(noti_id)
    if noti.recipient_id != current_user.id:
        return jsonify({'ok': False}), 403
    noti.is_read = True
    db.session.commit()
    return jsonify({'ok': True})

@app.route('/api/notifications/<int:noti_id>/confirm', methods=['POST'])
@login_required
def confirm_notification(noti_id):
    """소장/편집장이 파일 첨부를 확인함"""
    noti = Notification.query.get_or_404(noti_id)
    if noti.recipient_id != current_user.id:
        return jsonify({'ok': False}), 403
    noti.confirmed = True
    noti.confirmed_at = datetime.utcnow()
    noti.is_read = True
    db.session.commit()
    return jsonify({'ok': True, 'confirmed_at': noti.confirmed_at.strftime('%m/%d %H:%M')})

@app.route('/api/notifications/read-all', methods=['POST'])
@login_required
def read_all_notifications():
    Notification.query.filter_by(recipient_id=current_user.id, is_read=False)\
        .update({'is_read': True})
    db.session.commit()
    return jsonify({'ok': True})

@app.context_processor
def inject_notification_count():
    """모든 페이지에서 알림 개수를 사용할 수 있도록"""
    if hasattr(current_user, 'id') and current_user.is_authenticated:
        unread = Notification.query.filter_by(recipient_id=current_user.id, is_read=False).count()
        return {'noti_count': unread, 'user_is_admin': is_admin()}
    return {'noti_count': 0, 'user_is_admin': False}

# ═══════════════════════════════════════════
# INIT — 스키마 자동 검증 & 재생성
# ═══════════════════════════════════════════
with app.app_context():
    db.create_all()
    seed_database()
    seed_roles()
    seed_permissions()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

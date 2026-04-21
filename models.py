from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, date

db = SQLAlchemy()

# ─── Users ───
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # 소장/편집장/실무자/디자이너/행정팀장/구독매니저1/구독매니저2
    email = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ─── Categories ───
class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('Item', backref='category_ref', lazy=True)

# ─── Items ───
class Item(db.Model):
    __tablename__ = 'items'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    sku_code = db.Column(db.String(200))  # 위하고 품목코드 (쉼표 구분 다중 가능, 예: GG220801,GG220802)
    line = db.Column(db.String(10), nullable=False)  # A, B, C, B,C
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    artist = db.Column(db.String(100))
    unit_cost = db.Column(db.Integer)  # 원
    target_qty = db.Column(db.Integer)
    current_stock = db.Column(db.Integer, default=0)
    status = db.Column(db.String(30), default='기획중')
    # 기획중/디자인중/제작중/입고대기/입고완료/소진중/판매중/소진완료/단종
    usage = db.Column(db.String(30), default='판매')
    # 구독선물 / 판매 / 구독선물+판매 / 프로모션
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    target_date = db.Column(db.Date)  # 목표 입고일
    memo = db.Column(db.Text)
    sale_url_smartstore = db.Column(db.String(500))  # 스마트스토어 링크
    sale_url_aengdu = db.Column(db.String(500))      # aengdu.kr 링크
    sale_url_positive = db.Column(db.String(500))     # positive.co.kr 링크
    sale_url_other = db.Column(db.String(500))        # 기타 판매 링크
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = db.relationship('User', backref='items')
    tasks = db.relationship('Task', backref='item', lazy=True)
    inventory_logs = db.relationship('InventoryLog', backref='item', lazy=True)
    weekly_counts = db.relationship('WeeklyCount', backref='item', lazy=True)

# ─── Tasks ───
class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    assignee_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    status = db.Column(db.String(20), default='대기')  # 대기/진행중/완료
    priority = db.Column(db.String(10), default='보통')  # 긴급/높음/보통/낮음
    stage = db.Column(db.String(20))  # 기획/디자인/컨펌·견적/제작/입고
    revision_count = db.Column(db.Integer, default=0)  # 샘플 수정 횟수
    production_weeks = db.Column(db.Integer)  # 제작 기간 (1~8주)
    production_start = db.Column(db.Date)    # 제작 시작일
    due_date = db.Column(db.Date)
    start_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    assignee = db.relationship('User', backref='tasks')
    comments = db.relationship('Comment', backref='task', lazy=True, cascade='all,delete-orphan')

# ─── Comments ───
class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author = db.relationship('User')

# ─── Inventory Logs ───
class InventoryLog(db.Model):
    __tablename__ = 'inventory_logs'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    log_type = db.Column(db.String(20), nullable=False)  # 입고/출고/실사
    qty = db.Column(db.Integer, nullable=False)
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ─── Weekly Counts (매주 금요일 재고 실사) ───
class WeeklyCount(db.Model):
    __tablename__ = 'weekly_counts'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    counted_qty = db.Column(db.Integer, nullable=False)
    counted_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    counted_at = db.Column(db.Date, nullable=False)
    prev_system_qty = db.Column(db.Integer)
    diff = db.Column(db.Integer)  # counted - prev_system
    status = db.Column(db.String(20), default='확정')  # 확인대기/확정
    counter = db.relationship('User')

# ─── Attachments ───
class Attachment(db.Model):
    __tablename__ = 'attachments'
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'))
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    filename = db.Column(db.String(300), nullable=False)
    original_name = db.Column(db.String(300), nullable=False)
    file_type = db.Column(db.String(50))  # 디자인시안/견적서/감리보고서/샘플사진/기타
    file_size = db.Column(db.Integer)  # bytes
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploader = db.relationship('User')
    task = db.relationship('Task', backref='attachments')
    item_ref = db.relationship('Item', backref='attachments')

# ─── Checklist Items (퀄리티 체크) ───
class ChecklistItem(db.Model):
    __tablename__ = 'checklist_items'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    label = db.Column(db.String(300), nullable=False)
    category = db.Column(db.String(50))  # 공통/노트류/생활용품/지류/아트/AI추천
    checked = db.Column(db.Boolean, default=False)
    checked_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    checked_at = db.Column(db.DateTime)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    item = db.relationship('Item', backref='checklist_items')
    checker = db.relationship('User')

# ─── Feedbacks ───
class Feedback(db.Model):
    __tablename__ = 'feedbacks'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    category_type = db.Column(db.String(50))  # 컨텐츠이슈/감사/불만/기타
    content = db.Column(db.Text, nullable=False)
    channel = db.Column(db.String(50))  # 전화/메일/SNS/고객의소리
    feedback_date = db.Column(db.Date)
    customer_ref = db.Column(db.String(100))
    book_type = db.Column(db.String(100))
    status = db.Column(db.String(20), default='등록완료')  # 확인대기/등록완료
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    item = db.relationship('Item', backref='feedbacks')

# ─── Ideas ───
class Idea(db.Model):
    __tablename__ = 'ideas'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    proposer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    line = db.Column(db.String(10))
    category = db.Column(db.String(50))
    artist = db.Column(db.String(100))
    status = db.Column(db.String(20), default='제안됨')  # 제안됨/검토중/승인/보류/반려
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    reject_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    proposer = db.relationship('User', foreign_keys=[proposer_id], backref='ideas')
    approver = db.relationship('User', foreign_keys=[approved_by])

# ─── Notifications ───
class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    link = db.Column(db.String(300))  # 알림 클릭 시 이동할 URL
    noti_type = db.Column(db.String(30), default='파일첨부')  # 파일첨부/업무변경/기타
    is_read = db.Column(db.Boolean, default=False)
    confirmed = db.Column(db.Boolean, default=False)  # 소장/편집장 확인 여부
    confirmed_at = db.Column(db.DateTime)
    attachment_id = db.Column(db.Integer, db.ForeignKey('attachments.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    recipient = db.relationship('User', backref='notifications')
    attachment = db.relationship('Attachment', backref='notifications')

# ─── Kakao Events ───
class KakaoEvent(db.Model):
    __tablename__ = 'kakao_events'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    period_start = db.Column(db.Date)
    period_end = db.Column(db.Date)
    status = db.Column(db.String(20), default='기획중')  # 기획중/준비완료/진행중/종료
    bundles = db.Column(db.Text)  # JSON — 번들 상품 ID 목록
    existing_stock_items = db.Column(db.Text)  # JSON — 기존 재고 사용 상품 ID 목록
    total_sold = db.Column(db.Integer)
    memo = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ─── Cost Records (상품별 비용 기록) ───
class CostRecord(db.Model):
    __tablename__ = 'cost_records'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    label = db.Column(db.String(200), nullable=False)  # 비용 항목명 (디자인 외주비, 샘플 제작비, 포장재 등)
    amount = db.Column(db.Integer, nullable=False)      # 금액 (원)
    cost_date = db.Column(db.Date)                       # 발생일
    added_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    note = db.Column(db.Text)                            # 메모 (업체명, 비고 등)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    item = db.relationship('Item', backref='cost_records')
    adder = db.relationship('User')

# ─── Performance ───
# ─── Roles (역할 관리) ───
class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))
    is_admin = db.Column(db.Boolean, default=False)  # 관리자 권한 여부
    sort_order = db.Column(db.Integer, default=100)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ─── Role Permissions (역할별 권한) ───
class RolePermission(db.Model):
    __tablename__ = 'role_permissions'
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(50), nullable=False)
    permission = db.Column(db.String(50), nullable=False)  # permission key
    enabled = db.Column(db.Boolean, default=False)
    __table_args__ = (db.UniqueConstraint('role', 'permission', name='uq_role_perm'),)

# ─── Audit Log (변경 이력) ───
class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(50), nullable=False)  # 생성/수정/삭제/상태변경/승인/되돌리기 등
    target_type = db.Column(db.String(30))  # item/task/checklist/kakao 등
    target_id = db.Column(db.Integer)
    target_name = db.Column(db.String(200))  # 표시용 이름
    detail = db.Column(db.Text)  # 변경 세부 (예: "상태: 기획중 → 판매중")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='audit_logs')

class Performance(db.Model):
    __tablename__ = 'performance'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    total_sold = db.Column(db.Integer)
    revenue = db.Column(db.Integer)
    cost_total = db.Column(db.Integer)
    margin_rate = db.Column(db.Float)
    avg_monthly_sales = db.Column(db.Integer)
    internal_rating = db.Column(db.Integer)  # 1~5
    review_comment = db.Column(db.Text)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
    item = db.relationship('Item', backref='performances')

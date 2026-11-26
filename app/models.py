from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db

def utcnow(): return datetime.now(timezone.utc)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    college = db.Column(db.String(160), nullable=False)
    department = db.Column(db.String(120), nullable=False)
    academic_year = db.Column(db.String(30), nullable=False)
    bio = db.Column(db.String(500), default='')
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    is_active_account = db.Column(db.Boolean, nullable=False, default=True)
    login_count = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    skills = db.relationship('UserSkill', back_populates='user', cascade='all, delete-orphan')
    availability = db.relationship('Availability', back_populates='user', cascade='all, delete-orphan')
    sent_requests = db.relationship('ExchangeRequest', foreign_keys='ExchangeRequest.sender_id', back_populates='sender')
    received_requests = db.relationship('ExchangeRequest', foreign_keys='ExchangeRequest.receiver_id', back_populates='receiver')
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class SkillCategory(db.Model):
    __tablename__ = 'skill_categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    skills = db.relationship('Skill', back_populates='category')

class Skill(db.Model):
    __tablename__ = 'skills'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('skill_categories.id', ondelete='SET NULL'))
    category = db.relationship('SkillCategory', back_populates='skills')

class UserSkill(db.Model):
    __tablename__ = 'user_skills'
    __table_args__ = (db.UniqueConstraint('user_id', 'skill_id', 'direction', name='uq_user_skill_direction'), db.CheckConstraint('proficiency >= 1 AND proficiency <= 5'), db.CheckConstraint("direction IN ('teach','learn')"))
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    skill_id = db.Column(db.Integer, db.ForeignKey('skills.id', ondelete='CASCADE'), nullable=False, index=True)
    direction = db.Column(db.String(10), nullable=False) # teach / learn
    proficiency = db.Column(db.Integer, nullable=False, default=3)
    user = db.relationship('User', back_populates='skills')
    skill = db.relationship('Skill')

class Availability(db.Model):
    __tablename__ = 'availability'
    __table_args__ = (db.UniqueConstraint('user_id', 'weekday', 'start_hour', name='uq_availability_slot'), db.CheckConstraint('weekday >= 0 AND weekday <= 6'), db.CheckConstraint('start_hour >= 0 AND start_hour <= 23'))
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    weekday = db.Column(db.Integer, nullable=False)
    start_hour = db.Column(db.Integer, nullable=False)
    user = db.relationship('User', back_populates='availability')

class ExchangeRequest(db.Model):
    __tablename__ = 'exchange_requests'
    __table_args__ = (db.CheckConstraint('sender_id != receiver_id'),)
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    teach_skill_id = db.Column(db.Integer, db.ForeignKey('skills.id'), nullable=False)
    learn_skill_id = db.Column(db.Integer, db.ForeignKey('skills.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    sender = db.relationship('User', foreign_keys=[sender_id], back_populates='sent_requests')
    receiver = db.relationship('User', foreign_keys=[receiver_id], back_populates='received_requests')
    teach_skill = db.relationship('Skill', foreign_keys=[teach_skill_id])
    learn_skill = db.relationship('Skill', foreign_keys=[learn_skill_id])

class Exchange(db.Model):
    __tablename__ = 'exchanges'
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('exchange_requests.id', ondelete='CASCADE'), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='active')
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    request = db.relationship('ExchangeRequest')
    conversation = db.relationship('Conversation', back_populates='exchange', uselist=False, cascade='all, delete-orphan')

class Conversation(db.Model):
    __tablename__ = 'conversations'
    __table_args__ = (db.UniqueConstraint('exchange_id', name='uq_conversation_exchange'),)
    id = db.Column(db.Integer, primary_key=True)
    exchange_id = db.Column(db.Integer, db.ForeignKey('exchanges.id', ondelete='CASCADE'), nullable=False)
    exchange = db.relationship('Exchange', back_populates='conversation')

class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    body = db.Column(db.String(2000), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    sender = db.relationship('User')

class LearningSession(db.Model):
    __tablename__ = 'learning_sessions'
    id = db.Column(db.Integer, primary_key=True)
    exchange_id = db.Column(db.Integer, db.ForeignKey('exchanges.id', ondelete='CASCADE'), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    starts_at = db.Column(db.DateTime(timezone=True), nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False, default=60)
    status = db.Column(db.String(20), nullable=False, default='scheduled')
    exchange = db.relationship('Exchange')

class LearningGoal(db.Model):
    __tablename__ = 'learning_goals'
    id = db.Column(db.Integer, primary_key=True)
    exchange_id = db.Column(db.Integer, db.ForeignKey('exchanges.id', ondelete='CASCADE'), nullable=False, index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(180), nullable=False)
    completed = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

class Review(db.Model):
    __tablename__ = 'reviews'
    __table_args__ = (db.UniqueConstraint('exchange_id', 'reviewer_id', name='uq_review_exchange_reviewer'), db.CheckConstraint('rating >= 1 AND rating <= 5'))
    id = db.Column(db.Integer, primary_key=True)
    exchange_id = db.Column(db.Integer, db.ForeignKey('exchanges.id', ondelete='CASCADE'), nullable=False, index=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    reviewee_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    body = db.Column(db.String(800), default='')
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    reviewer = db.relationship('User', foreign_keys=[reviewer_id])
    reviewee = db.relationship('User', foreign_keys=[reviewee_id])

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    message = db.Column(db.String(300), nullable=False)
    link = db.Column(db.String(250), default='/dashboard')
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    user = db.relationship('User')

class Report(db.Model):
    __tablename__ = 'reports'
    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    reported_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    reason = db.Column(db.String(800), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='open', index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    reporter = db.relationship('User', foreign_keys=[reporter_id])
    reported_user = db.relationship('User', foreign_keys=[reported_user_id])


class LoginEvent(db.Model):
    __tablename__ = 'login_events'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    logged_in_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    user = db.relationship('User')

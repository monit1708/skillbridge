from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import func
from email_validator import validate_email, EmailNotValidError
from .extensions import db
from .models import (
    User, Skill, SkillCategory, UserSkill, Availability,
    ExchangeRequest, Exchange, Conversation, LearningSession,
    LearningGoal, Review, Notification, Message, Report, LoginEvent, utcnow,
)
from .matching import recommendations, relevant_matches, skill_relevance

main = Blueprint('main', __name__)
auth = Blueprint('auth', __name__)
api = Blueprint('api', __name__)


def _record_login(user):
    user.login_count = (user.login_count or 0) + 1
    user.last_login_at = utcnow()
    db.session.add(LoginEvent(user_id=user.id))


@main.route('/')
def index():
    try:
        featured = Skill.query.order_by(Skill.name).limit(6).all()
    except Exception:
        featured = []
    return render_template('index.html', featured=featured)


@main.route('/dashboard')
@login_required
def dashboard():
    recs = recommendations(current_user, 6)
    related_recs = relevant_matches(current_user, 6)
    requests = ExchangeRequest.query.filter_by(receiver_id=current_user.id, status='pending').all()
    exchanges = (
        Exchange.query.join(ExchangeRequest).filter(ExchangeRequest.sender_id == current_user.id).all()
        + Exchange.query.join(ExchangeRequest).filter(ExchangeRequest.receiver_id == current_user.id).all()
    )
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(8).all()
    return render_template(
        'dashboard.html',
        recs=recs,
        related_recs=related_recs,
        requests=requests,
        exchanges=exchanges,
        sessions_by_exchange={e.id: LearningSession.query.filter_by(exchange_id=e.id).order_by(LearningSession.starts_at).all() for e in exchanges},
        goals_by_exchange={e.id: LearningGoal.query.filter_by(exchange_id=e.id).all() for e in exchanges},
        notifications=notifications,
        unread=Notification.query.filter_by(user_id=current_user.id, is_read=False).count(),
    )


@main.route('/discover')
@login_required
def discover():
    recs = recommendations(current_user, 100)
    related_recs = relevant_matches(current_user, 100)
    q = request.args.get('q', '').strip().lower()
    college = request.args.get('college', '').strip().lower()
    if q:
        recs = [(u, s, m, t) for u, s, m, t in recs if q in u.name.lower() or any(q in x.skill.name.lower() for x in u.skills)]
        related_recs = [(u, s, k, src, dst) for u, s, k, src, dst in related_recs if q in u.name.lower() or any(q in x.skill.name.lower() for x in u.skills)]
    if college:
        recs = [(u, s, m, t) for u, s, m, t in recs if college in u.college.lower()]
        related_recs = [(u, s, k, src, dst) for u, s, k, src, dst in related_recs if college in u.college.lower()]
    return render_template('discover.html', recs=recs, related_recs=related_recs, q=q, college=college)


@main.route('/profile')
@login_required
def profile():
    return render_template('profile.html', categories=SkillCategory.query.order_by(SkillCategory.name).all(), skills=Skill.query.order_by(Skill.name).all())


@main.route('/chat/<int:conversation_id>')
@login_required
def chat_page(conversation_id):
    conv = Conversation.query.get_or_404(conversation_id)
    if not can_access_conversation(conv, current_user.id):
        abort(403)
    messages = Message.query.filter_by(conversation_id=conv.id).order_by(Message.id).limit(100).all()
    return render_template('chat.html', conversation=conv, messages=messages)


def can_access_conversation(conv, uid):
    req = conv.exchange.request
    return uid in (req.sender_id, req.receiver_id)


@api.get('/conversations/<int:conversation_id>/messages')
@login_required
def get_conversation_messages(conversation_id):
    conv = Conversation.query.get_or_404(conversation_id)
    if not can_access_conversation(conv, current_user.id):
        abort(403)
    query = Message.query.filter_by(conversation_id=conv.id)
    after = request.args.get('after', type=int)
    if after:
        query = query.filter(Message.id > after)
    messages = query.order_by(Message.id).limit(100).all()
    return jsonify(
        messages=[
            {
                'id': m.id,
                'sender': m.sender.name,
                'sender_id': m.sender_id,
                'body': m.body,
                'created_at': m.created_at.isoformat(),
            }
            for m in messages
        ]
    )


@api.post('/conversations/<int:conversation_id>/messages')
@login_required
def post_conversation_message(conversation_id):
    conv = Conversation.query.get_or_404(conversation_id)
    if not can_access_conversation(conv, current_user.id):
        abort(403)
    data = request.get_json(silent=True) or {}
    body = str(data.get('body', '')).strip()
    if not body or len(body) > 2000:
        return jsonify(error='Message must be 1–2000 characters.'), 400
    message = Message(conversation_id=conv.id, sender_id=current_user.id, body=body)
    db.session.add(message)
    db.session.commit()
    return jsonify(
        id=message.id,
        sender=current_user.name,
        sender_id=current_user.id,
        body=message.body,
        created_at=message.created_at.isoformat(),
    ), 201


@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        college = request.form.get('college', '').strip()
        department = request.form.get('department', '').strip()
        year = request.form.get('academic_year', '').strip()
        try:
            email = validate_email(email, check_deliverability=False).normalized
        except EmailNotValidError:
            flash('Enter a valid email address.', 'danger')
        else:
            if not all([name, email, password, college, department, year]):
                flash('Please complete every field.', 'danger')
            elif len(name) > 100 or len(email) > 255 or len(college) > 160 or len(department) > 120 or len(password) < 10 or len(password) > 128:
                flash('Check the field lengths. Passwords must be 10–128 characters.', 'danger')
            elif User.query.filter_by(email=email).first():
                flash('That email is already registered.', 'danger')
            else:
                u = User(name=name, email=email, college=college, department=department, academic_year=year)
                u.set_password(password)
                db.session.add(u)
                db.session.flush()
                _record_login(u)
                db.session.commit()
                login_user(u)
                return redirect(url_for('main.profile'))
    return render_template('auth.html', mode='register')


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.admin_page' if current_user.is_admin else 'main.dashboard'))
    if request.method == 'POST':
        u = User.query.filter(func.lower(User.email) == request.form.get('email', '').strip().lower()).first()
        if u and u.is_active_account and u.check_password(request.form.get('password', '')):
            _record_login(u)
            db.session.commit()
            login_user(u, remember=True)
            next_url = request.args.get('next')
            if next_url:
                return redirect(next_url)
            return redirect(url_for('main.admin_page' if u.is_admin else 'main.dashboard'))
        flash('Email or password is incorrect.', 'danger')
    return render_template('auth.html', mode='login')


@auth.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('main.admin_page'))
        flash('You are signed in as a student without admin access.', 'warning')
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        u = User.query.filter(func.lower(User.email) == request.form.get('email', '').strip().lower()).first()
        if u and u.is_active_account and u.check_password(request.form.get('password', '')):
            if not u.is_admin:
                flash('This account does not have admin privileges.', 'danger')
                return render_template('auth.html', mode='admin_login')
            _record_login(u)
            db.session.commit()
            login_user(u, remember=True)
            return redirect(url_for('main.admin_page'))
        flash('Admin email or password is incorrect.', 'danger')
    return render_template('auth.html', mode='admin_login')


@auth.post('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))


@api.get('/me')
@login_required
def me():
    return jsonify({'id': current_user.id, 'name': current_user.name, 'email': current_user.email})


@api.get('/skills')
def skill_list():
    return jsonify([{'id': s.id, 'name': s.name, 'category': s.category.name if s.category else ''} for s in Skill.query.order_by(Skill.name)])


@api.post('/skills')
@login_required
def add_skill():
    data = request.get_json(silent=True) or request.form
    name = str(data.get('name', '')).strip()
    direction = data.get('direction')
    proficiency = data.get('proficiency', 3)
    if not name or direction not in ('teach', 'learn'):
        return jsonify(error='Skill and direction are required.'), 400
    try:
        proficiency = int(proficiency)
    except (ValueError, TypeError):
        return jsonify(error='Proficiency must be 1–5.'), 400
    if not 1 <= proficiency <= 5:
        return jsonify(error='Proficiency must be 1–5.'), 400
    skill = Skill.query.filter(func.lower(Skill.name) == name.lower()).first()
    if not skill:
        skill = Skill(name=name[:100])
        db.session.add(skill)
        db.session.flush()
    link = UserSkill.query.filter_by(user_id=current_user.id, skill_id=skill.id, direction=direction).first()
    if link:
        link.proficiency = proficiency
    else:
        db.session.add(UserSkill(user_id=current_user.id, skill_id=skill.id, direction=direction, proficiency=proficiency))
    db.session.flush()

    # Check mutual and one-way relevant matches immediately after saving the skill.
    db.session.expire(current_user, ['skills'])
    mutual = recommendations(current_user, limit=50)
    related = relevant_matches(current_user, limit=50)
    notified_ids = set()
    for partner, _, my_link, their_link in mutual:
        if my_link.skill_id == skill.id or (direction == 'learn' and skill_relevance(their_link.skill, skill) > 0):
            msg = f'{current_user.name} added {skill.name} — you have a mutual skill match!'
            if not Notification.query.filter_by(user_id=partner.id, message=msg, is_read=False).first():
                db.session.add(Notification(user_id=partner.id, message=msg, link='/discover'))
                notified_ids.add(partner.id)
    for partner, _, kind, src_link, dst_link in related:
        if partner.id in notified_ids:
            continue
        if src_link.skill_id == skill.id or dst_link.skill_id == skill.id:
            msg = f'{current_user.name} added {skill.name} — a relevant skill match is ready to view.'
            if not Notification.query.filter_by(user_id=partner.id, message=msg, is_read=False).first():
                db.session.add(Notification(user_id=partner.id, message=msg, link='/discover'))

    db.session.commit()
    top_partner = mutual[0][0].name if mutual else (related[0][0].name if related else None)
    return jsonify(
        ok=True,
        skill=skill.name,
        direction=direction,
        mutual_matches=len(mutual),
        relevant_matches=len(related),
        top_match=top_partner,
    )


@api.delete('/skills/<int:link_id>')
@login_required
def remove_skill(link_id):
    link = UserSkill.query.filter_by(id=link_id, user_id=current_user.id).first_or_404()
    db.session.delete(link)
    db.session.commit()
    return jsonify(ok=True)


@api.put('/profile')
@login_required
def update_profile():
    data = request.get_json(silent=True) or {}
    current_user.name = str(data.get('name', current_user.name)).strip()[:100]
    current_user.college = str(data.get('college', current_user.college)).strip()[:160]
    current_user.department = str(data.get('department', current_user.department)).strip()[:120]
    current_user.academic_year = str(data.get('academic_year', current_user.academic_year)).strip()[:30]
    current_user.bio = str(data.get('bio', current_user.bio)).strip()[:500]
    db.session.commit()
    return jsonify(ok=True)


@api.post('/availability')
@login_required
def add_availability():
    data = request.get_json(silent=True) or {}
    try:
        day = int(data.get('weekday'))
        hour = int(data.get('start_hour'))
    except (ValueError, TypeError):
        return jsonify(error='Choose a valid day and hour.'), 400
    if not 0 <= day <= 6 or not 0 <= hour <= 23:
        return jsonify(error='Choose a valid day and hour.'), 400
    if not Availability.query.filter_by(user_id=current_user.id, weekday=day, start_hour=hour).first():
        db.session.add(Availability(user_id=current_user.id, weekday=day, start_hour=hour))
        db.session.commit()
    return jsonify(ok=True)


@api.post('/requests')
@login_required
def create_request():
    data = request.get_json(silent=True) or {}
    try:
        uid = int(data.get('user_id'))
        teach_id = int(data.get('teach_skill_id'))
        learn_id = int(data.get('learn_skill_id'))
    except (ValueError, TypeError):
        return jsonify(error='Select a valid student and both exchange skills.'), 400
    target = User.query.get_or_404(uid)
    if target.id == current_user.id:
        return jsonify(error='You cannot request an exchange with yourself.'), 400
    has_offer = UserSkill.query.filter_by(user_id=current_user.id, skill_id=teach_id, direction='teach').first()
    their_teach = UserSkill.query.filter_by(user_id=target.id, skill_id=learn_id, direction='teach').first()
    is_mutual = False
    if has_offer and their_teach:
        target_learns = UserSkill.query.filter_by(user_id=target.id, direction='learn').all()
        my_learns = UserSkill.query.filter_by(user_id=current_user.id, direction='learn').all()
        has_need = any(skill_relevance(has_offer.skill, link.skill) > 0 for link in target_learns)
        reciprocal = any(skill_relevance(their_teach.skill, link.skill) > 0 for link in my_learns)
        is_mutual = has_need and reciprocal

    # Also allow connecting on a one-way relevant skill match (teach <-> learn).
    their_learn = UserSkill.query.filter_by(user_id=target.id, skill_id=learn_id, direction='learn').first()
    one_way_teach = bool(has_offer and their_learn and skill_relevance(has_offer.skill, their_learn.skill) > 0)
    their_offer = UserSkill.query.filter_by(user_id=target.id, skill_id=teach_id, direction='teach').first()
    my_learn = UserSkill.query.filter_by(user_id=current_user.id, skill_id=learn_id, direction='learn').first()
    one_way_learn = bool(their_offer and my_learn and skill_relevance(their_offer.skill, my_learn.skill) > 0)

    if not (is_mutual or one_way_teach or one_way_learn):
        return jsonify(error='Request skills must form a relevant or mutual match.'), 400
    if ExchangeRequest.query.filter_by(sender_id=current_user.id, receiver_id=target.id, status='pending').first():
        return jsonify(error='You already have a pending request.'), 409
    req = ExchangeRequest(sender_id=current_user.id, receiver_id=target.id, teach_skill_id=teach_id, learn_skill_id=learn_id)
    db.session.add(req)
    db.session.add(Notification(user_id=target.id, message=f'{current_user.name} sent you a skill exchange request.', link='/dashboard'))
    db.session.commit()
    return jsonify(ok=True), 201


@api.post('/requests/<int:request_id>/<action>')
@login_required
def respond_request(request_id, action):
    req = ExchangeRequest.query.filter_by(id=request_id, receiver_id=current_user.id).first_or_404()
    if req.status != 'pending' or action not in ('accept', 'reject'):
        return jsonify(error='This request can no longer be changed.'), 400
    req.status = 'accepted' if action == 'accept' else 'rejected'
    if action == 'accept':
        ex = Exchange(request=req)
        db.session.add(ex)
        db.session.flush()
        db.session.add(Conversation(exchange_id=ex.id))
        db.session.add(Notification(user_id=req.sender_id, message=f'{current_user.name} accepted your exchange request.', link='/dashboard'))
    db.session.commit()
    return jsonify(ok=True)


@api.get('/requests')
@login_required
def my_requests():
    return jsonify([{'id': r.id, 'from': r.sender.name, 'status': r.status} for r in current_user.received_requests])


@api.post('/exchanges/<int:exchange_id>/sessions')
@login_required
def schedule_session(exchange_id):
    ex = Exchange.query.get_or_404(exchange_id)
    if current_user.id not in (ex.request.sender_id, ex.request.receiver_id):
        abort(403)
    data = request.get_json(silent=True) or {}
    try:
        when = datetime.fromisoformat(data.get('starts_at', '').replace('Z', '+00:00'))
        duration = int(data.get('duration_minutes', 60))
    except (ValueError, TypeError):
        return jsonify(error='Enter a valid date and time.'), 400
    title = str(data.get('title', 'Learning session')).strip()[:150]
    if duration < 15 or duration > 240 or not title:
        return jsonify(error='Session must be 15–240 minutes with a title.'), 400
    db.session.add(LearningSession(exchange_id=ex.id, title=title, starts_at=when, duration_minutes=duration))
    db.session.commit()
    return jsonify(ok=True), 201


@api.post('/exchanges/<int:exchange_id>/goals')
@login_required
def add_goal(exchange_id):
    ex = Exchange.query.get_or_404(exchange_id)
    if current_user.id not in (ex.request.sender_id, ex.request.receiver_id):
        abort(403)
    title = str((request.get_json(silent=True) or {}).get('title', '')).strip()
    if not title or len(title) > 180:
        return jsonify(error='Goal must be 1–180 characters.'), 400
    db.session.add(LearningGoal(exchange_id=ex.id, owner_id=current_user.id, title=title))
    db.session.commit()
    return jsonify(ok=True), 201


@api.post('/goals/<int:goal_id>/toggle')
@login_required
def toggle_goal(goal_id):
    goal = LearningGoal.query.get_or_404(goal_id)
    ex = db.session.get(Exchange, goal.exchange_id)
    if current_user.id not in (ex.request.sender_id, ex.request.receiver_id):
        abort(403)
    goal.completed = not goal.completed
    db.session.commit()
    return jsonify(ok=True, completed=goal.completed)


@api.post('/exchanges/<int:exchange_id>/complete')
@login_required
def complete_exchange(exchange_id):
    ex = Exchange.query.get_or_404(exchange_id)
    if current_user.id not in (ex.request.sender_id, ex.request.receiver_id):
        abort(403)
    ex.status = 'completed'
    db.session.commit()
    return jsonify(ok=True)


@api.post('/exchanges/<int:exchange_id>/reviews')
@login_required
def review_exchange(exchange_id):
    ex = Exchange.query.get_or_404(exchange_id)
    req = ex.request
    if current_user.id not in (req.sender_id, req.receiver_id):
        abort(403)
    if ex.status != 'completed':
        return jsonify(error='Complete the exchange before leaving a review.'), 409
    data = request.get_json(silent=True) or {}
    try:
        rating = int(data.get('rating'))
    except (ValueError, TypeError):
        return jsonify(error='Rating must be 1–5.'), 400
    if not 1 <= rating <= 5:
        return jsonify(error='Rating must be 1–5.'), 400
    reviewee = req.receiver_id if current_user.id == req.sender_id else req.sender_id
    if Review.query.filter_by(exchange_id=ex.id, reviewer_id=current_user.id).first():
        return jsonify(error='You have already reviewed this exchange.'), 409
    db.session.add(Review(exchange_id=ex.id, reviewer_id=current_user.id, reviewee_id=reviewee, rating=rating, body=str(data.get('body', '')).strip()[:800]))
    db.session.commit()
    return jsonify(ok=True), 201


@api.post('/notifications/read')
@login_required
def read_notifications():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify(ok=True)


@main.route('/admin')
@login_required
def admin_page():
    if not current_user.is_admin:
        abort(403)
    return render_template('admin.html')


@api.get('/admin')
@login_required
def admin_stats():
    if not current_user.is_admin:
        abort(403)
    users = User.query.order_by(User.created_at.desc()).all()
    skills = Skill.query.order_by(Skill.name).all()
    user_skills = UserSkill.query.all()
    teach_counts = {}
    learn_counts = {}
    for us in user_skills:
        if us.direction == 'teach':
            teach_counts[us.skill_id] = teach_counts.get(us.skill_id, 0) + 1
        else:
            learn_counts[us.skill_id] = learn_counts.get(us.skill_id, 0) + 1

    recent_logins = (
        LoginEvent.query.order_by(LoginEvent.logged_in_at.desc()).limit(20).all()
    )

    return jsonify(
        users=len(users),
        logged_in_users=sum(1 for u in users if (u.login_count or 0) > 0),
        total_logins=LoginEvent.query.count(),
        skills=len(skills),
        total_user_skills=len(user_skills),
        teach_skills_count=sum(teach_counts.values()),
        learn_skills_count=sum(learn_counts.values()),
        requests=ExchangeRequest.query.count(),
        pending_requests=ExchangeRequest.query.filter_by(status='pending').count(),
        exchanges=Exchange.query.count(),
        reports=Report.query.filter_by(status='open').count(),
        user_list=[
            {
                'id': u.id,
                'name': u.name,
                'email': u.email,
                'college': u.college,
                'department': u.department,
                'is_admin': u.is_admin,
                'active': u.is_active_account,
                'login_count': u.login_count or 0,
                'last_login_at': u.last_login_at.isoformat() if u.last_login_at else None,
                'skills_count': len(u.skills),
                'teach_skills': [{'name': s.skill.name, 'proficiency': s.proficiency} for s in u.skills if s.direction == 'teach'],
                'learn_skills': [{'name': s.skill.name, 'proficiency': s.proficiency} for s in u.skills if s.direction == 'learn'],
                'created_at': u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
        skill_list=[
            {
                'id': s.id,
                'name': s.name,
                'category': s.category.name if s.category else 'Uncategorized',
                'teach_count': teach_counts.get(s.id, 0),
                'learn_count': learn_counts.get(s.id, 0),
                'total_users': teach_counts.get(s.id, 0) + learn_counts.get(s.id, 0),
            }
            for s in skills
        ],
        recent_logins=[
            {
                'id': ev.id,
                'user_name': ev.user.name,
                'email': ev.user.email,
                'is_admin': ev.user.is_admin,
                'logged_in_at': ev.logged_in_at.isoformat(),
            }
            for ev in recent_logins
        ],
        report_list=[
            {
                'id': r.id,
                'reporter': r.reporter.name,
                'reported': r.reported_user.name,
                'reason': r.reason,
                'status': r.status,
            }
            for r in Report.query.order_by(Report.created_at.desc()).all()
        ],
    )


@api.post('/users/<int:user_id>/report')
@login_required
def submit_report(user_id):
    target = User.query.get_or_404(user_id)
    if target.id == current_user.id:
        return jsonify(error='You cannot report yourself.'), 400
    reason = str((request.get_json(silent=True) or {}).get('reason', '')).strip()
    if not reason or len(reason) > 800:
        return jsonify(error='Describe the concern in 1–800 characters.'), 400
    db.session.add(Report(reporter_id=current_user.id, reported_user_id=target.id, reason=reason))
    db.session.add(Notification(user_id=current_user.id, message='Your report was sent to the SkillBridge team.', link='/dashboard'))
    db.session.commit()
    return jsonify(ok=True), 201


def require_admin():
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)


@api.post('/admin/users/<int:user_id>/toggle')
@login_required
def admin_toggle_user(user_id):
    require_admin()
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        return jsonify(error='You cannot deactivate your own admin account.'), 400
    user.is_active_account = not user.is_active_account
    db.session.commit()
    return jsonify(ok=True, active=user.is_active_account)


@api.delete('/admin/skills/<int:skill_id>')
@login_required
def admin_delete_skill(skill_id):
    require_admin()
    skill = Skill.query.get_or_404(skill_id)
    if UserSkill.query.filter_by(skill_id=skill.id).first():
        return jsonify(error='This skill is in use by student profiles and cannot be removed.'), 409
    db.session.delete(skill)
    db.session.commit()
    return jsonify(ok=True)


@api.post('/admin/reports/<int:report_id>/resolve')
@login_required
def admin_resolve_report(report_id):
    require_admin()
    report = Report.query.get_or_404(report_id)
    report.status = 'resolved'
    db.session.commit()
    return jsonify(ok=True)

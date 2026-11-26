from app.extensions import db
from app.models import User, Skill, SkillCategory, UserSkill, Availability, ExchangeRequest, Exchange, Conversation, Notification
from app.matching import score_pair, mutual_skill_pair, relevant_matches


def user(name, email, is_admin=False):
    u = User(name=name, email=email, college='Campus', department='CS', academic_year='2nd year', is_admin=is_admin)
    u.set_password('strong-password-123')
    db.session.add(u)
    db.session.flush()
    return u


def test_mutual_matching_reads_saved_skills(app):
    with app.app_context():
        a = user('A', 'a@example.edu')
        b = user('B', 'b@example.edu')
        java = Skill(name='Java')
        python = Skill(name='Python')
        db.session.add_all([java, python])
        db.session.flush()
        db.session.add_all([
            UserSkill(user_id=a.id, skill_id=java.id, direction='teach', proficiency=5),
            UserSkill(user_id=a.id, skill_id=python.id, direction='learn', proficiency=3),
            UserSkill(user_id=b.id, skill_id=python.id, direction='teach', proficiency=4),
            UserSkill(user_id=b.id, skill_id=java.id, direction='learn', proficiency=3),
            Availability(user_id=a.id, weekday=1, start_hour=12),
            Availability(user_id=b.id, weekday=1, start_hour=12),
        ])
        db.session.commit()
        assert score_pair(a, b) == 88


def test_registration_login_and_profile(client):
    r = client.post('/register', data={'name': 'Student', 'email': 's@example.edu', 'password': 'long-password-1', 'college': 'Campus', 'department': 'CS', 'academic_year': '1st year'}, follow_redirects=True)
    assert r.status_code == 200 and b'Build your profile' in r.data
    assert client.get('/api/me').json['email'] == 's@example.edu'
    client.post('/logout')
    assert client.post('/login', data={'email': 's@example.edu', 'password': 'long-password-1'}).status_code == 302


def test_skill_request_accept_creates_chat(client, app):
    with app.app_context():
        a = user('Alice', 'alice@example.edu')
        b = user('Bob', 'bob@example.edu')
        j = Skill(name='Java')
        p = Skill(name='Python')
        db.session.add_all([j, p])
        db.session.flush()
        db.session.add_all([
            UserSkill(user_id=a.id, skill_id=j.id, direction='teach'),
            UserSkill(user_id=a.id, skill_id=p.id, direction='learn'),
            UserSkill(user_id=b.id, skill_id=p.id, direction='teach'),
            UserSkill(user_id=b.id, skill_id=j.id, direction='learn'),
        ])
        db.session.commit()
        b_id, j_id, p_id = b.id, j.id, p.id
    client.post('/login', data={'email': 'alice@example.edu', 'password': 'strong-password-123'})
    r = client.post('/api/requests', json={'user_id': b_id, 'teach_skill_id': j_id, 'learn_skill_id': p_id})
    assert r.status_code == 201
    client.post('/logout')
    client.post('/login', data={'email': 'bob@example.edu', 'password': 'strong-password-123'})
    assert client.post('/api/requests/1/accept').status_code == 200
    with app.app_context():
        assert Exchange.query.count() == 1 and Conversation.query.count() == 1


def test_rejects_nonmutual_exchange(client, app):
    with app.app_context():
        u = user('A', 'a@x.edu')
        v = user('B', 'b@x.edu')
        s = Skill(name='SQL')
        db.session.add(s)
        db.session.flush()
        db.session.add(UserSkill(user_id=u.id, skill_id=s.id, direction='teach'))
        db.session.commit()
        vid, sid = v.id, s.id
    client.post('/login', data={'email': 'a@x.edu', 'password': 'strong-password-123'})
    assert client.post('/api/requests', json={'user_id': vid, 'teach_skill_id': sid, 'learn_skill_id': sid}).status_code == 400


def test_one_sided_skill_overlap_is_not_a_partner_match(app):
    with app.app_context():
        a = user('A', 'oneway-a@example.edu')
        b = user('B', 'oneway-b@example.edu')
        python = Skill(name='Python')
        db.session.add(python)
        db.session.flush()
        db.session.add_all([
            UserSkill(user_id=a.id, skill_id=python.id, direction='teach'),
            UserSkill(user_id=b.id, skill_id=python.id, direction='learn'),
        ])
        db.session.commit()
        assert score_pair(a, b) is None
        assert mutual_skill_pair(a, b) is None
        rel = relevant_matches(a)
        assert len(rel) == 1 and rel[0][0].id == b.id


def test_discovery_explains_exact_two_way_trade(client, app):
    with app.app_context():
        a = user('A', 'discover-a@example.edu')
        b = user('B', 'discover-b@example.edu')
        java = Skill(name='Java')
        python = Skill(name='Python')
        db.session.add_all([java, python])
        db.session.flush()
        db.session.add_all([
            UserSkill(user_id=a.id, skill_id=java.id, direction='teach'),
            UserSkill(user_id=a.id, skill_id=python.id, direction='learn'),
            UserSkill(user_id=b.id, skill_id=python.id, direction='teach'),
            UserSkill(user_id=b.id, skill_id=java.id, direction='learn'),
        ])
        db.session.commit()
    client.post('/login', data={'email': 'discover-a@example.edu', 'password': 'strong-password-123'})
    discover = client.get('/discover')
    dashboard = client.get('/dashboard')
    assert discover.status_code == 200 and b'YOU TEACH' in discover.data and b'Java' in discover.data and b'Python' in discover.data
    assert dashboard.status_code == 200 and b'Your top matches' in dashboard.data
    filtered = client.get('/discover?q=python&college=campus')
    assert filtered.status_code == 200 and b'YOU TEACH' in filtered.data and b'Java' in filtered.data
    empty = client.get('/discover?q=nonexistent')
    assert empty.status_code == 200 and b'No mutual matches yet' in empty.data


def test_relevant_skill_matching_and_notification_on_add(client, app):
    with app.app_context():
        a = user('Alice', 'rel-a@example.edu')
        b = user('Bob', 'rel-b@example.edu')
        py = Skill(name='Python')
        ui = Skill(name='UI Design')
        db.session.add_all([py, ui])
        db.session.flush()
        db.session.add_all([
            UserSkill(user_id=a.id, skill_id=py.id, direction='teach', proficiency=4),
            UserSkill(user_id=a.id, skill_id=ui.id, direction='learn', proficiency=3),
        ])
        db.session.commit()
        aid = a.id

    client.post('/login', data={'email': 'rel-b@example.edu', 'password': 'strong-password-123'})
    r1 = client.post('/api/skills', json={'name': 'UI/UX Design', 'direction': 'teach', 'proficiency': 5})
    assert r1.status_code == 200 and r1.json['relevant_matches'] == 1
    r2 = client.post('/api/skills', json={'name': 'Python Programming', 'direction': 'learn', 'proficiency': 3})
    assert r2.status_code == 200 and r2.json['mutual_matches'] == 1

    with app.app_context():
        notes = Notification.query.filter_by(user_id=aid).all()
        assert len(notes) >= 1 and 'Bob' in notes[-1].message


def test_admin_login_and_dashboard_metrics(client, app):
    with app.app_context():
        admin = user('Admin User', 'admin@example.edu', is_admin=True)
        student = user('Student One', 'student1@example.edu', is_admin=False)
        py = Skill(name='Python')
        db.session.add(py)
        db.session.flush()
        db.session.add(UserSkill(user_id=student.id, skill_id=py.id, direction='teach', proficiency=4))
        db.session.commit()

    # Non-admin cannot sign in via /admin/login or view /api/admin
    r_denied = client.post('/admin/login', data={'email': 'student1@example.edu', 'password': 'strong-password-123'})
    assert r_denied.status_code == 200 and b'does not have admin privileges' in r_denied.data
    client.post('/login', data={'email': 'student1@example.edu', 'password': 'strong-password-123'})
    assert client.get('/api/admin').status_code == 403
    client.post('/logout')

    # Admin signs in via /admin/login and views metrics
    r_ok = client.post('/admin/login', data={'email': 'admin@example.edu', 'password': 'strong-password-123'})
    assert r_ok.status_code == 302 and '/admin' in r_ok.location
    assert client.get('/admin').status_code == 200
    stats = client.get('/api/admin').json
    assert stats['users'] == 2
    assert stats['logged_in_users'] == 2
    assert stats['total_logins'] == 2
    assert stats['total_user_skills'] == 1
    assert stats['teach_skills_count'] == 1
    assert stats['learn_skills_count'] == 0
    student_row = next(u for u in stats['user_list'] if u['email'] == 'student1@example.edu')
    assert student_row['login_count'] == 1
    assert student_row['skills_count'] == 1
    assert student_row['teach_skills'][0]['name'] == 'Python'


def test_http_chat_messages_across_users(client, app):
    with app.app_context():
        a = user('Alice', 'chat-a@example.edu')
        b = user('Bob', 'chat-b@example.edu')
        j = Skill(name='Java')
        p = Skill(name='Python')
        db.session.add_all([j, p])
        db.session.flush()
        req = ExchangeRequest(sender_id=a.id, receiver_id=b.id, teach_skill_id=j.id, learn_skill_id=p.id, status='accepted')
        db.session.add(req)
        db.session.flush()
        ex = Exchange(request_id=req.id)
        db.session.add(ex)
        db.session.flush()
        conv = Conversation(exchange_id=ex.id)
        db.session.add(conv)
        db.session.commit()
        cid = conv.id

    client.post('/login', data={'email': 'chat-a@example.edu', 'password': 'strong-password-123'})
    r1 = client.post(f'/api/conversations/{cid}/messages', json={'body': 'Hey Bob, ready to swap Python for Java?'})
    assert r1.status_code == 201
    msg_id = r1.json['id']
    client.post('/logout')

    client.post('/login', data={'email': 'chat-b@example.edu', 'password': 'strong-password-123'})
    r2 = client.get(f'/api/conversations/{cid}/messages')
    assert r2.status_code == 200
    assert len(r2.json['messages']) == 1
    assert r2.json['messages'][0]['body'] == 'Hey Bob, ready to swap Python for Java?'
    r3 = client.post(f'/api/conversations/{cid}/messages', json={'body': 'Yes! Let us start now.'})
    assert r3.status_code == 201
    r4 = client.get(f'/api/conversations/{cid}/messages?after={msg_id}')
    assert r4.status_code == 200
    assert len(r4.json['messages']) == 1 and r4.json['messages'][0]['sender'] == 'Bob'

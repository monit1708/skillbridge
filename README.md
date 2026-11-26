# SkillBridge

A responsive student-to-student skill exchange built with Flask, PostgreSQL, SQLAlchemy, Flask-SocketIO, Bootstrap 5, and Bootstrap Icons. Match scores are computed from persisted skill and availability records; there are no generated profiles or AI services.

## Local setup

Requires Python 3.10+ and PostgreSQL 14+ for a PostgreSQL deployment. A SQLite database is used by default for a quick local run and automated tests.

```sh
cd SkillBridge
python3 -m venv .venv
source .venv/bin/activate
./.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
# Set a unique SECRET_KEY and a reachable DATABASE_URL in .env
```

For PostgreSQL, create the `skillbridge` database and role, then set `DATABASE_URL=postgresql+psycopg://...` in `.env`. Do not use the example password or development secret in deployment. Enable HTTPS and set `COOKIE_SECURE=1` in production.

## Database and run

```sh
./.venv/bin/python -m flask --app run.py db upgrade
./.venv/bin/python -m flask --app manage.py seed       # optional starter skill catalog; no sample users
./.venv/bin/python run.py
```

The repository includes an Alembic environment and baseline at `migrations/versions/0001_initial.py`; after installing dependencies, `./.venv/bin/python -m flask --app run.py db upgrade` applies the schema.

Open http://127.0.0.1:5000. Create accounts using the registration page. Add skills to teach and learn plus shared availability to receive match recommendations.

## Features

- Password hashing (Werkzeug), session authentication, CSRF protection, input validation, ownership checks, secure cookie settings, and admin-only metrics endpoint.
- Normalized tables for users, skill categories/catalog, user skills, availability, requests, exchanges, conversations, messages, sessions, goals, reviews, and notifications.
- Reciprocal matching from actual database rows. Score weights: reciprocal coverage 60%, proficiency 25%, overlapping time slots 15%. Missing availability contributes zero. Candidates without reciprocal coverage are not recommended.
- Request accept/reject, private exchange chat over Socket.IO, scheduling, learning goals, reviews, notifications, and admin aggregate stats API.
- Responsive dashboard, discovery search, profile management, and a persisted dark mode preference.

## Migrations

A baseline migration is included at `migrations/versions/0001_initial.py`. For future schema changes, use `./.venv/bin/python -m flask --app run.py db migrate -m "description"`, inspect the generated migration, then apply it with `./.venv/bin/python -m flask --app run.py db upgrade`.

## Test

```sh
pytest
```

Tests use an isolated in-memory SQLite database. PostgreSQL deployments should run the migration command against their configured `DATABASE_URL` and may additionally run integration checks against a dedicated test database.

## Production notes

Run behind a production WSGI server that supports Socket.IO (for example, `gunicorn -k eventlet -w 1 run:app` after setting a strong `SECRET_KEY`, PostgreSQL URL, HTTPS, and `COOKIE_SECURE=1`). For multiple workers, configure a Socket.IO message queue. The admin endpoint is available to accounts explicitly flagged `is_admin`; provision initial admins through a trusted database operation. SkillBridge does not seed fake students.

from run import app
from app.extensions import db
from app.models import Skill, SkillCategory, User
import click


@app.cli.command('seed')
def seed():
    """Add starter skill categories and skills (never creates sample users)."""
    catalog = {
        'Technology': ['Python', 'Java', 'Web Development', 'Data Analysis', 'SQL'],
        'Design': ['UI/UX Design', 'Graphic Design', 'Figma'],
        'Languages': ['English', 'Spanish', 'Japanese'],
        'Business': ['Public Speaking', 'Marketing', 'Excel'],
        'Creative': ['Photography', 'Video Editing', 'Guitar'],
    }
    for name, items in catalog.items():
        category = SkillCategory.query.filter_by(name=name).first() or SkillCategory(name=name)
        db.session.add(category)
        db.session.flush()
        for item in items:
            if not Skill.query.filter_by(name=item).first():
                db.session.add(Skill(name=item, category=category))
    db.session.commit()
    click.echo('Starter skill catalog seeded.')


@app.cli.command('create-admin')
@click.option('--email', prompt=True, help='Admin email address')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Admin password (10+ chars)')
@click.option('--name', default='SkillBridge Admin', help='Admin display name')
def create_admin(email, password, name):
    """Create or promote an admin user account."""
    normalized = email.strip().lower()
    if len(password) < 10:
        raise click.ClickException('Password must be at least 10 characters.')
    user = User.query.filter_by(email=normalized).first()
    if user:
        user.is_admin = True
        user.is_active_account = True
        user.set_password(password)
        if name:
            user.name = name.strip()[:100]
        action = 'updated and promoted to admin'
    else:
        user = User(
            name=name.strip()[:100] or 'SkillBridge Admin',
            email=normalized,
            college='SkillBridge',
            department='Administration',
            academic_year='Staff',
            is_admin=True,
            is_active_account=True,
        )
        user.set_password(password)
        db.session.add(user)
        action = 'created as admin'
    db.session.commit()
    click.echo(f'Admin account {normalized} {action}.')

import os
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config
from .extensions import db, migrate, login_manager, socketio, csrf


def create_app(test_config=None):
    kwargs = {'instance_path': '/tmp/instance'} if os.getenv('VERCEL') else {}
    app = Flask(__name__, **kwargs)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    os.makedirs(app.instance_path, exist_ok=True)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    async_mode = 'threading' if os.getenv('VERCEL') else None
    socketio.init_app(app, cors_allowed_origins=[], async_mode=async_mode)
    csrf.init_app(app)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from .routes import main, auth, api
    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(api, url_prefix='/api')

    from .chat import register_chat
    register_chat(socketio)

    @app.errorhandler(404)
    def not_found(_):
        return {'error': 'Not found'}, 404

    @app.errorhandler(500)
    def server_error(_):
        db.session.rollback()
        return {'error': 'Something went wrong. Please try again.'}, 500

    if os.getenv('VERCEL') and app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite:////tmp'):
        with app.app_context():
            db.create_all()

    return app

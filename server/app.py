"""
ContentFlow Pro License Server
Flask application for managing license activation and validation
"""
from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from models import db
from routes import api
import os

def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)

    # Configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///licenses.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['JSON_SORT_KEYS'] = False

    # Initialize database
    db.init_app(app)

    # Initialize rate limiter
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"],
        storage_uri="memory://"
    )

    # Apply rate limiting to API routes
    limiter.limit("10 per minute")(api)

    # Register blueprints
    app.register_blueprint(api, url_prefix='/api')

    # Create tables
    with app.app_context():
        db.create_all()
        print("✅ Database tables created successfully")

    @app.route('/')
    def index():
        return {
            'service': 'ContentFlow Pro License Server',
            'version': '1.0.0',
            'status': 'running',
            'endpoints': {
                'health': '/api/health',
                'activate': '/api/license/activate',
                'validate': '/api/license/validate',
                'deactivate': '/api/license/deactivate',
                'status': '/api/license/status',
                'admin_generate': '/api/admin/generate'
            }
        }

    return app

if __name__ == '__main__':
    app = create_app()
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'False').lower() == 'true'

    print(f"""
    ╔════════════════════════════════════════════════════════════╗
    ║   ContentFlow Pro License Server                           ║
    ║   Running on: http://localhost:{port}                        ║
    ║   Debug Mode: {debug}                                         ║
    ╚════════════════════════════════════════════════════════════╝
    """)

    app.run(host='0.0.0.0', port=port, debug=debug)

from pathlib import Path

from flask import Flask
from flask_cors import CORS

def create_app(testing=False) -> Flask:
    """
    Flask application factory.
    Args:
        testing: If True, uses test DB pool and skips seed data.
    """
    project_root = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        template_folder=str(project_root / "frontend" / "templates"),
        static_folder=str(project_root / "frontend" / "static"),
        static_url_path="/static"
    )

    from backend.config import Config
    app.secret_key = Config.SECRET_KEY

    CORS(app)

    # Initialize DB pool
    from backend.database.connection import init_pool, init_test_pool, execute_schema
    if testing:
        init_test_pool()
    else:
        init_pool()
    execute_schema()

    # Rebuild in-memory heap from DB
    if not testing:
        from backend.services.patient_service import rebuild_heap
        rebuild_heap()

    # Register blueprints
    from backend.routes.patient_routes import patient_bp
    from backend.routes.health_routes  import health_bp
    app.register_blueprint(patient_bp, url_prefix="/api")
    app.register_blueprint(health_bp,  url_prefix="/api")

    # Serve frontend
    from flask import render_template
    @app.route("/")
    def index():
        return render_template("index.html")

    # Global error handlers
    @app.errorhandler(404)
    def not_found(e):
        from flask import jsonify
        return jsonify({"error": "Endpoint not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        from flask import jsonify
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(500)
    def internal_error(e):
        from flask import jsonify
        return jsonify({"error": "Internal server error"}), 500

    return app

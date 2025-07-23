from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from app.models import db
from user_api import user_blueprint
from transactions_api import transaction_bp
from dashboard_api import dashboard_blueprint
from ocr_api import ocr_blueprint
from dotenv import load_dotenv
import os

# ✅ Load .env file
load_dotenv()

# ✅ Ambil dari environment
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
db_name = os.getenv("DB_NAME")

# ✅ Konfigurasi Flask & DB
app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "fallback-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = f"mysql+mysqlconnector://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# ✅ Init ekstensi
db.init_app(app)
jwt = JWTManager(app)
CORS(app, origins="*")

# ✅ Daftarkan blueprint
app.register_blueprint(user_blueprint, url_prefix='/user')
app.register_blueprint(transaction_bp, url_prefix='/transactions')
app.register_blueprint(ocr_blueprint, url_prefix='/ocr')
app.register_blueprint(dashboard_blueprint)

@app.route('/')
def index():
    return jsonify({"message": "Welcome! Available prefixes: /user, /transactions, /dashboard"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)

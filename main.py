from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from dashboard_api import dashboard_blueprint



# Impor semua blueprint Anda, termasuk yang baru
from user_api import user_blueprint 

# Initialize the Flask application and JWT manager
app = Flask(__name__)

# Configure the JWT secret key
app.config['JWT_SECRET_KEY'] = 'your_jwt_secret_key'  # Replace with your actual secret key

# Initialize the JWT manager
jwt = JWTManager(app)

CORS(app, origins="*")

# Register Blueprints
app.register_blueprint(user_blueprint, url_prefix='/user')
app.register_blueprint(dashboard_blueprint)

# Root endpoint (optional)
@app.route('/')
def index():
    return jsonify({"message": "Welcome! Available prefixes: /user"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)  # ubah ke 8000 

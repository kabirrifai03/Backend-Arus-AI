from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from koneksi import get_conn

dashboard_blueprint = Blueprint('dashboard', __name__)

@dashboard_blueprint.route('/dashboard/summary', methods=['GET'])
@jwt_required()
def dashboard_summary():
    user_id = get_jwt_identity()

    try:
        with get_conn() as conn:
            cur = conn.cursor(dictionary=True)

            # Total aplikasi
            cur.execute("SELECT COUNT(*) as total FROM applications WHERE user_id = %s", (user_id,))
            total_applications = cur.fetchone()['total']

            # Jumlah fraud
            cur.execute("SELECT COUNT(*) as fraud FROM applications WHERE user_id = %s AND is_fraud = 1", (user_id,))
            fraud_count = cur.fetchone()['fraud']

            # Fraud rate
            fraud_rate = int((fraud_count / total_applications) * 100) if total_applications > 0 else 0

            # Chart data (per bulan)
            cur.execute("""
                SELECT DATE_FORMAT(date, '%%b') as month, COUNT(*) as value
                FROM applications
                WHERE user_id = %s
                GROUP BY MONTH(date)
                ORDER BY MONTH(date)
            """, (user_id,))
            chart_data = cur.fetchall()

            # Customer composition
            cur.execute("""
                SELECT category AS name, COUNT(*) as value
                FROM customers
                WHERE user_id = %s
                GROUP BY category
            """, (user_id,))
            customer_composition = cur.fetchall()

            # Recent activities
            cur.execute("""
                SELECT id, title, timestamp, description
                FROM activities
                WHERE user_id = %s
                ORDER BY timestamp DESC
                LIMIT 5
            """, (user_id,))
            recent_activities = cur.fetchall()

            # Latest applications
            cur.execute("""
                SELECT id, borrower, amount, status, date
                FROM applications
                WHERE user_id = %s
                ORDER BY date DESC
                LIMIT 5
            """, (user_id,))
            latest_applications = cur.fetchall()

            return jsonify({
                "fraud_count": fraud_count,
                "total_applications": total_applications,
                "fraud_rate": fraud_rate,
                "growth_percentage": 15,  # hardcoded sementara
                "chart_data": chart_data,
                "customer_composition": customer_composition,
                "recent_activities": recent_activities,
                "latest_applications": latest_applications
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dashboard_blueprint.route('/summary', methods=['GET'])
def get_summary():
    conn = get_conn()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM summary_data")
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(results)
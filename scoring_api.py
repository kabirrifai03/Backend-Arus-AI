# scoring_api.py

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func, case
from datetime import datetime, timedelta
import numpy as np
from sklearn.linear_model import LinearRegression
import re

# Impor dari proyek yang sudah ada
from app.models import db, Transaction

scoring_blueprint = Blueprint('scoring', __name__)

# --- SEMUA FUNGSI KALKULASI (calculate_... ) TETAP SAMA SEPERTI SEBELUMNYA ---
# (Fungsi-fungsi ini tidak perlu diubah, jadi saya tidak menampilkannya lagi agar ringkas)

def _get_daily_net_income(user_id, days=60):
    # ... (kode tidak berubah)
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days - 1)
    results = db.session.query(
        func.date(Transaction.date).label('tx_date'),
        func.sum(case((Transaction.type == 'pemasukan', Transaction.amount), else_=0)).label('income'),
        func.sum(case((Transaction.type == 'pengeluaran', Transaction.amount), else_=0)).label('expense')
    ).filter(
        Transaction.user_id == user_id,
        Transaction.date.between(start_date, end_date)
    ).group_by('tx_date').order_by('tx_date').all()
    daily_profits_map = {res.tx_date: res.income - res.expense for res in results}
    profit_series = []
    for i in range(days):
        current_date = start_date + timedelta(days=i)
        profit = daily_profits_map.get(current_date, 0)
        profit_series.append(profit)
    return np.array(profit_series)

def calculate_profitability_score(user_id):
    # ... (kode tidak berubah)
    total_income = db.session.query(func.sum(Transaction.amount)).filter_by(user_id=user_id, type='pemasukan').scalar() or 0
    total_expense = db.session.query(func.sum(Transaction.amount)).filter_by(user_id=user_id, type='pengeluaran').scalar() or 0
    if total_income == 0: return 0
    margin = ((total_income - total_expense) / total_income) * 100
    if margin > 20: return 90
    if 10 <= margin <= 20: return 70
    if 1 <= margin < 10: return 45
    if margin == 0: return 20
    return 0

def calculate_stability_score(user_id):
    # ... (kode tidak berubah)
    profit_series = _get_daily_net_income(user_id, days=60)
    if len(profit_series) < 7: return 0
    mean_profit = np.mean(profit_series)
    std_dev = np.std(profit_series)
    if mean_profit <= 0: return 10
    cv = std_dev / mean_profit
    if cv < 0.3: return 95
    if 0.3 <= cv < 0.7: return 80
    if 0.7 <= cv < 1.2: return 60
    return 30

def calculate_trend_score(user_id):
    # ... (kode tidak berubah)
    profit_series = _get_daily_net_income(user_id, days=60)
    if len(profit_series) < 14: return 50
    mean_profit = np.mean(profit_series)
    if mean_profit <= 0: return 10
    X = np.arange(len(profit_series)).reshape(-1, 1)
    y = profit_series
    model = LinearRegression()
    model.fit(X, y)
    slope = model.coef_[0]
    normalized_trend = (slope / mean_profit) * 100
    if normalized_trend > 0.5: return 95
    if 0 < normalized_trend <= 0.5: return 80
    if normalized_trend == 0: return 60
    return 30

def calculate_income_quality_score(user_id):
    # ... (kode tidak berubah)
    non_sales_keywords = ['suntikan', 'pinjaman', 'setoran', 'transfer pribadi', 'modal']
    income_transactions = Transaction.query.filter_by(user_id=user_id, type='pemasukan').all()
    if not income_transactions: return 0
    total_income = 0
    sales_income = 0
    for tx in income_transactions:
        total_income += tx.amount
        if not any(keyword in tx.description.lower() for keyword in non_sales_keywords):
            sales_income += tx.amount
    if total_income == 0: return 0
    quality_ratio = (sales_income / total_income) * 100
    if quality_ratio > 95: return 95
    if 80 <= quality_ratio <= 95: return 80
    if 60 <= quality_ratio < 80: return 60
    return 30

def calculate_load_management_score(user_id):
    # ... (kode tidak berubah)
    efficiency_score = calculate_profitability_score(user_id)
    expense_txs = db.session.query(
        func.date(Transaction.date).label('tx_date'),
        func.sum(Transaction.amount).label('daily_expense')
    ).filter(
        Transaction.user_id == user_id,
        Transaction.type == 'pengeluaran'
    ).group_by('tx_date').all()
    if len(expense_txs) < 7:
        predictability_score = 50
    else:
        daily_expenses = [tx.daily_expense for tx in expense_txs]
        mean_expense = np.mean(daily_expenses)
        std_expense = np.std(daily_expenses)
        if mean_expense == 0:
             predictability_score = 100
        else:
            cv_expense = std_expense / mean_expense
            if cv_expense < 0.4: predictability_score = 90
            elif cv_expense < 0.8: predictability_score = 70
            else: predictability_score = 40
    final_score = (0.5 * efficiency_score) + (0.5 * predictability_score)
    return final_score

def calculate_bill_payment_score(late_in_last_3_months, total_late, monthly_bill_cv, bill_to_income_ratio):
    # ... (kode tidak berubah)
    if late_in_last_3_months: score_ketepatan = 40
    elif total_late > 0: score_ketepatan = 75
    else: score_ketepatan = 100
    if monthly_bill_cv < 0.1: score_kestabilan = 90
    elif monthly_bill_cv < 0.25: score_kestabilan = 65
    else: score_kestabilan = 30
    if bill_to_income_ratio < 0.1: score_rasio = 100
    elif bill_to_income_ratio < 0.25: score_rasio = 80
    elif bill_to_income_ratio < 0.4: score_rasio = 50
    else: score_rasio = 20
    final_score = (0.5 * score_ketepatan) + (0.25 * score_kestabilan) + (0.25 * score_rasio)
    return final_score

def calculate_mobile_usage_score(avg_monthly_topup, topup_cv, number_age_years, has_banking_app, has_gambling_app):
    # ... (kode tidak berubah)
    if avg_monthly_topup > 150000 and topup_cv < 0.2: score_topup = 100
    elif avg_monthly_topup > 100000 and topup_cv < 0.3: score_topup = 80
    elif avg_monthly_topup > 50000 or topup_cv < 0.5: score_topup = 60
    else: score_topup = 40
    if number_age_years > 5: score_lama_nomor = 100
    elif number_age_years >= 2: score_lama_nomor = 80
    elif number_age_years >= 1: score_lama_nomor = 60
    else: score_lama_nomor = 40
    score_aplikasi = 60
    if has_banking_app: score_aplikasi += 20
    if has_gambling_app: score_aplikasi -= 40
    score_aplikasi = max(0, min(100, score_aplikasi))
    final_score = (0.5 * score_topup) + (0.3 * score_lama_nomor) + (0.2 * score_aplikasi)
    return final_score

def calculate_tax_score(has_npwp, provides_npwp):
    # ... (kode tidak berubah)
    if has_npwp and provides_npwp: return 80
    if has_npwp and not provides_npwp: return 40
    if not has_npwp: return 20
    return 20

def calculate_credit_history_score(has_failed_loan, active_loans_count):
    # ... (kode tidak berubah)
    if has_failed_loan: return 0
    if active_loans_count == 0: return 100
    if active_loans_count == 1: return 75
    if active_loans_count >= 2: return 40
    return 100

# --- Bagian 3: API Endpoint Utama (YANG DIPERBARUI) ---

@scoring_blueprint.route('/health-score', methods=['POST']) # ✅ UBAH DARI GET KE POST
@jwt_required()
def get_business_health_score():
    user_id = get_jwt_identity()
    
    # ✅ Ambil data dari body JSON, bukan lagi dari query parameter
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body JSON tidak ditemukan atau kosong."}), 400

    try:
        # --- Hitung P&L Score (bobot 70%) ---
        # (Perhitungan ini tidak berubah, karena mengambil data dari DB)
        dna_scores = {
            "profitability": calculate_profitability_score(user_id),
            "stability": calculate_stability_score(user_id),
            "trend": calculate_trend_score(user_id),
            "income_quality": calculate_income_quality_score(user_id),
            "load_management": calculate_load_management_score(user_id)
        }
        pnl_score_component = sum(score * 0.14 for score in dna_scores.values())

        # --- Hitung ICS Score (bobot 30%) ---
        # ✅ Ambil data dari dictionary 'data', gunakan default value jika tidak ada
        ics_scores = {
            "bill_payment": calculate_bill_payment_score(
                data.get("bill_late_in_3m", False), data.get("bill_total_late", 0),
                data.get("bill_cv", 0.3), data.get("bill_ratio", 0.2)
            ),
            "mobile_usage": calculate_mobile_usage_score(
                data.get("mobile_avg_topup", 120000), data.get("mobile_topup_cv", 0.25),
                data.get("mobile_number_age", 3), data.get("mobile_has_banking", True),
                data.get("mobile_has_gambling", False)
            ),
            "tax_history": calculate_tax_score(
                data.get("tax_has_npwp", True), data.get("tax_provides_npwp", True)
            ),
            "credit_history": calculate_credit_history_score(
                data.get("credit_has_failed", False), data.get("credit_active_loans", 0)
            )
        }
        ics_score_component = sum(score * 0.075 for score in ics_scores.values())

        # --- Hitung Skor Akhir ---
        final_health_score = pnl_score_component + ics_score_component

        return jsonify({
            "final_health_score": round(final_health_score, 2),
            "details": {
                "pnl_score_contribution": round(pnl_score_component, 2),
                "ics_score_contribution": round(ics_score_component, 2),
                "pnl_dna_breakdown": {k: round(v, 2) for k, v in dna_scores.items()},
                "ics_breakdown": {k: round(v, 2) for k, v in ics_scores.items()}
            },
            "message": "Health score calculated successfully."
        }), 200

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
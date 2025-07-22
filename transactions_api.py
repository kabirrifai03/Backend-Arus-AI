from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import db, Transaction  # ⬅️ ambil db dari 1 tempat saja
from datetime import datetime
from sqlalchemy import func, case
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import timedelta
import pandas as pd
from io import BytesIO
from flask import send_file



transaction_bp = Blueprint('transactions', __name__)

@transaction_bp.route('/add', methods=['POST'])
@jwt_required()
def add_transaction():
    data = request.json
    user_id = get_jwt_identity()
    
    try:
        for idx, item in enumerate(data['items']):
            # Ambil tanggal dari item atau global
            date_str = item.get('date') or data.get('date')
            if not date_str:
                raise ValueError(f"Tanggal transaksi tidak ditemukan di baris {idx + 1}")
            
            # Validasi format tanggal
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                raise ValueError(f"Format tanggal tidak valid di baris {idx + 1}: {date_str}")
            
            # Simpan ke DB
            new_tx = Transaction(
                user_id=user_id,
                type=data['type'],
                description=item['description'],
                amount=item['amount'],
                date=date_obj
            )
            db.session.add(new_tx)

        db.session.commit()
        return jsonify({'message': 'Transaksi berhasil ditambahkan'}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400





@transaction_bp.route('/chart', methods=['GET'])
@jwt_required()
def get_transaction_chart():
    user_id = get_jwt_identity()
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    resolution = request.args.get('resolution', 'daily')

    try:
        # Tentukan ekspresi period berdasarkan resolusi
        if resolution == 'daily':
            period_expr = func.date(Transaction.date)
        elif resolution == 'weekly':
            period_expr = func.yearweek(Transaction.date)
        elif resolution == 'monthly':
            period_expr = func.date_format(Transaction.date, '%Y-%m')
        elif resolution == 'yearly':
            period_expr = func.year(Transaction.date)
        else:
            return jsonify({'error': 'Resolusi tidak valid'}), 400

        # Query berdasarkan periode dan user_id
        query = db.session.query(
            period_expr.label('period'),
            func.sum(case((Transaction.type == 'pemasukan', Transaction.amount), else_=0)).label('income'),
            func.sum(case((Transaction.type == 'pengeluaran', Transaction.amount), else_=0)).label('expense')
        ).filter(Transaction.user_id == user_id)

        if start_date:
            query = query.filter(Transaction.date >= start_date)
        if end_date:
            query = query.filter(Transaction.date <= end_date)

        query = query.group_by('period').order_by('period')
        results = query.all()

        chart_data = []
        for row in results:
            if resolution == 'daily':
                label = row.period.strftime("%Y-%m-%d")
            elif resolution == 'weekly':
                label = f"Minggu ke-{str(row.period)[-2:]}, {str(row.period)[:4]}"
            elif resolution == 'monthly':
                label = row.period  # Sudah dalam format '%Y-%m'
            elif resolution == 'yearly':
                label = str(row.period)

            chart_data.append({
                'date': label,
                'income': float(row.income),
                'expense': float(row.expense)
            })

        return jsonify(chart_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@transaction_bp.route("/report", methods=["GET"])
@jwt_required()
def download_report():
    user_id = get_jwt_identity()
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    try:
        query = Transaction.query.filter_by(user_id=user_id)
        if start_date:
            query = query.filter(Transaction.date >= start_date)
        if end_date:
            query = query.filter(Transaction.date <= end_date)

        transactions = query.order_by(Transaction.date).all()

        data = [{
            "Tanggal": tx.date.strftime("%Y-%m-%d"),
            "Jenis": tx.type,
            "Deskripsi": tx.description,
            "Jumlah": float(tx.amount)
        } for tx in transactions]

        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Laporan Transaksi")

        output.seek(0)
        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True, download_name="Laporan_Transaksi.xlsx")

    except Exception as e:
        return jsonify({"error": str(e)}), 500

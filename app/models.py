from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'akun'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

class Transaction(db.Model):
    __tablename__ = 'transactions'  # ✅ BENAR, sama dengan nama tabel di MySQL

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('akun.id'), nullable=False)
    type = db.Column(db.String(10), nullable=False)
    description = db.Column(db.String(255))
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)


class Application(db.Model):
    __tablename__ = 'applications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('akun.id'), nullable=False)
    borrower = db.Column(db.String(100))
    amount = db.Column(db.Float)
    status = db.Column(db.String(20))
    date = db.Column(db.Date)
    is_fraud = db.Column(db.Boolean)

class Activity(db.Model):
    __tablename__ = 'activities'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('akun.id'))
    title = db.Column(db.String(100))
    description = db.Column(db.Text)
    timestamp = db.Column(db.DateTime)

class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('akun.id'))
    category = db.Column(db.String(50))

class SummaryData(db.Model):
    __tablename__ = 'summary_data'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50))
    value = db.Column(db.String(255))

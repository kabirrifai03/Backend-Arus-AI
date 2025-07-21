import mysql.connector
from mysql.connector import pooling, Error
from contextlib import contextmanager
import os
from dotenv import load_dotenv

load_dotenv()

HOST        = os.getenv('DB_HOST')
PORT        = int(os.getenv('DB_PORT', 3306))
DATABASE    = os.getenv('DB_NAME')  # ✅ sesuai dengan .env
USER        = os.getenv('DB_USER')
PASSWORD    = os.getenv('DB_PASSWORD')
POOL_SIZE   = int(os.getenv('DB_POOL_SIZE', 5))
SSL_FILENAME = os.getenv('SSL_CERT_FILENAME')  # optional

use_ssl = SSL_FILENAME is not None and SSL_FILENAME.strip() != ""

if use_ssl:
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        SSL_CERT_PATH = os.path.join(current_dir, SSL_FILENAME)
        if not os.path.exists(SSL_CERT_PATH):
            raise FileNotFoundError(f"SSL cert file not found: {SSL_CERT_PATH}")
    except NameError:
        SSL_CERT_PATH = SSL_FILENAME
else:
    SSL_CERT_PATH = None

try:
    pool_config = {
        "pool_name": "mypool",
        "pool_size": POOL_SIZE,
        "host": HOST,
        "port": PORT,
        "database": DATABASE,
        "user": USER,
        "password": PASSWORD,
        "charset": "utf8"
    }

    if use_ssl:
        pool_config.update({
            "ssl_ca": SSL_CERT_PATH,
            "ssl_verify_cert": False,
            "tls_versions": ['TLSv1.2']
        })

    connection_pool = pooling.MySQLConnectionPool(**pool_config)
    print("✅ Connection pool created successfully.")
except Error as err:
    print(f"❌ Error creating connection pool: {err}")
    exit(1)

@contextmanager
def get_conn():
    conn = None
    try:
        conn = connection_pool.get_connection()
        conn.autocommit = False 
        yield conn
    except Error as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

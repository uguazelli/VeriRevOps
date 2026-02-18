import os
import psycopg2

# Default credentials from docker-compose if not set in env
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")


def get_postgres_connection():
    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        port=POSTGRES_PORT
    )
    return conn


def create_database_if_not_exists():
    try:
        # Connect to default 'postgres' database to check/create target DB
        # We cannot use get_postgres_connection() here because it connects to the target DB
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            database="postgres",
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            port=POSTGRES_PORT
        )
        conn.autocommit = True
        cur = conn.cursor()

        # Check if database exists
        cur.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{POSTGRES_DB}'")
        exists = cur.fetchone()

        if not exists:
            print(f"Database '{POSTGRES_DB}' does not exist. Creating...")
            cur.execute(f"CREATE DATABASE {POSTGRES_DB}")
            print(f"Database '{POSTGRES_DB}' created successfully.")
        else:
            print(f"Database '{POSTGRES_DB}' already exists.")

        cur.close()
        conn.close()
        return True, "Database check/creation successful"
    except Exception as e:
        print(f"Error checking/creating database: {e}")
        return False, str(e)


from app.core.queries import (
    CREATE_TENANTS_TABLE,
    CREATE_SUBSCRIPTIONS_TABLE,
    CREATE_CHAT_SESSIONS_TABLE,
    CREATE_CHAT_MESSAGES_TABLE
)

def create_tables_if_not_exist():
    try:
        conn = get_postgres_connection()
        conn.autocommit = True
        cur = conn.cursor()

        # Tenants
        cur.execute(CREATE_TENANTS_TABLE)

        # Subscriptions
        cur.execute(CREATE_SUBSCRIPTIONS_TABLE)

        # Chat Sessions
        cur.execute(CREATE_CHAT_SESSIONS_TABLE)

        # Chat Messages
        cur.execute(CREATE_CHAT_MESSAGES_TABLE)

        print("Tables created (if not existed) successfully.")
        cur.close()
        conn.close()
        return True, "Table creation successful"
    except Exception as e:
        print(f"Error creating tables: {e}")
        return False, str(e)


def check_db_connection():
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        return True, "Database connection successful"
    except Exception as e:
        return False, str(e)


def execute_read_query(query: str, params: tuple = None) -> list:
    """
    Executes a SELECT query and returns a list of tuples.
    """
    conn = None
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        return rows
    except Exception as e:
        print(f"Error executing read query: {e}")
        raise e
    finally:
        if conn:
            conn.close()


def execute_write_query(query: str, params: tuple = None) -> object:
    """
    Executes an INSERT/UPDATE/DELETE query.
    Returns the first column of the first row if RETURNING is used,
    otherwise returns the number of rows affected.
    """
    conn = None
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute(query, params)

        if "RETURNING" in query.upper():
             result = cur.fetchone() # Returns a tuple
        else:
             result = cur.rowcount

        conn.commit()
        cur.close()
        return result
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error executing write query: {e}")
        raise e
    finally:
        if conn:
            conn.close()
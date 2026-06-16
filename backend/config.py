from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    # Gemini
    GOOGLE_API_KEY   = os.getenv("GOOGLE_API_KEY")

    # PostgreSQL
    DB_HOST          = os.getenv("DB_HOST", "localhost")
    DB_PORT          = int(os.getenv("DB_PORT", 5432))
    DB_NAME          = os.getenv("DB_NAME", "hospital_queue")
    DB_USER          = os.getenv("DB_USER", "postgres")
    DB_PASSWORD      = os.getenv("DB_PASSWORD", "")

    # Test DB
    TEST_DB_NAME     = os.getenv("TEST_DB_NAME", "hospital_queue_test")

    # Flask
    SECRET_KEY       = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
    PORT             = int(os.getenv("FLASK_PORT", 5000))
    DEBUG            = os.getenv("FLASK_ENV", "development") == "development"

    @classmethod
    def get_dsn(cls, test=False):
        """Return psycopg2 DSN dict for production or test database."""
        return {
            "host"    : cls.DB_HOST,
            "port"    : cls.DB_PORT,
            "dbname"  : cls.TEST_DB_NAME if test else cls.DB_NAME,
            "user"    : cls.DB_USER,
            "password": cls.DB_PASSWORD
        }

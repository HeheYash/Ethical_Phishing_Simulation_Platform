import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///phishing_platform.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Email configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')

    # Application settings
    BASE_URL = os.environ.get('BASE_URL') or 'http://localhost:5000'
    SESSION_TIMEOUT = int(os.environ.get('SESSION_TIMEOUT') or 3600)
    RATE_LIMIT_PER_MINUTE = int(os.environ.get('RATE_LIMIT_PER_MINUTE') or 60)

    # Security and ethics
    CAMPAIGN_CONSENT_REQUIRED = os.environ.get('CAMPAIGN_CONSENT_REQUIRED', 'true').lower() in ['true', 'on', '1']
    DATA_RETENTION_DAYS = int(os.environ.get('DATA_RETENTION_DAYS') or 90)
    MAX_EMAILS_PER_HOUR = int(os.environ.get('MAX_EMAILS_PER_HOUR') or 100)

    # Redis configuration for Celery
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'

    # Upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = 'uploads'

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
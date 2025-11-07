from flask import current_app
from app import db
from models import create_sample_data

def init_db():
    """Initialize the database with tables and sample data"""
    with current_app.app_context():
        # Create all tables
        db.create_all()

        # Create sample data if database is empty
        from models import User, Template, Target

        if not User.query.first():
            create_sample_data()
            current_app.logger.info("Sample data created successfully")
        else:
            current_app.logger.info("Database already contains data")

def reset_db():
    """Reset the database (drop and recreate all tables)"""
    with current_app.app_context():
        db.drop_all()
        db.create_all()
        create_sample_data()
        current_app.logger.info("Database reset completed")
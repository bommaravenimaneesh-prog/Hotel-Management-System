from app import app, db
from sqlalchemy import text

with app.app_context():
    try:
        db.session.execute(text("ALTER TABLE booking ADD COLUMN payment_type VARCHAR(50) DEFAULT 'Card';"))
        db.session.commit()
        print("Successfully added payment_type to booking table.")
    except Exception as e:
        db.session.rollback()
        print(f"Error, column might already exist: {e}")

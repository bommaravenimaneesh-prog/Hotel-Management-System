from app import app, db
from sqlalchemy import text

with app.app_context():
    queries = [
        "ALTER TABLE food_item ADD COLUMN image_url VARCHAR(255);",
        "ALTER TABLE food_order ADD COLUMN custom_request VARCHAR(255);",
        "ALTER TABLE food_order MODIFY food_item_id INTEGER NULL;",
    ]
    for q in queries:
        try:
            db.session.execute(text(q))
            db.session.commit()
            print("Success:", q)
        except Exception as e:
            db.session.rollback()
            print("Failed (probably already applied):", q)
    
    # Update default images
    try:
        db.session.execute(text("UPDATE food_item SET image_url='https://images.unsplash.com/photo-1528735602780-2552fd46c7af?w=400&q=80' WHERE name='Club Sandwich'"))
        db.session.execute(text("UPDATE food_item SET image_url='https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=400&q=80' WHERE name='Margherita Pizza'"))
        db.session.execute(text("UPDATE food_item SET image_url='https://images.unsplash.com/photo-1550304943-4f24f54ddde9?w=400&q=80' WHERE name='Caesar Salad'"))
        db.session.commit()
        print("Updated images")
    except Exception as e:
        db.session.rollback()
        print("Failed to update images", e)

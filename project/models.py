from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='Guest') # Admin, Receptionist, Guest

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(10), unique=True, nullable=False)
    type = db.Column(db.String(50), nullable=False) # Single, Double, Deluxe, Suite
    price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Available') # Available, Booked, Occupied, Maintenance

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Confirmed') # Confirmed, Checked-In, Checked-Out, Cancelled
    payment_type = db.Column(db.String(50), nullable=False, default='Card') # Card, Cash, UPI
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref=db.backref('bookings', lazy=True))
    room = db.relationship('Room', backref=db.backref('bookings', lazy=True))

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    room_charges = db.Column(db.Float, nullable=False)
    extra_charges = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, nullable=False)
    payment_status = db.Column(db.String(20), nullable=False, default='Pending') # Pending, Paid
    
    booking = db.relationship('Booking', backref=db.backref('invoice', uselist=False))

class FoodItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(255), nullable=True)
    is_available = db.Column(db.Boolean, default=True)

class FoodOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    food_item_id = db.Column(db.Integer, db.ForeignKey('food_item.id'), nullable=True) # Now optional
    custom_request = db.Column(db.String(255), nullable=True) # Custom order text
    quantity = db.Column(db.Integer, nullable=False, default=1)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Pending') # Pending, Accepted, Delivered
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    booking = db.relationship('Booking', backref=db.backref('food_orders', lazy=True))
    food_item = db.relationship('FoodItem')

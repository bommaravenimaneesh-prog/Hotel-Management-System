import os
from datetime import datetime, timezone
import bcrypt
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_socketio import SocketIO, emit
from sqlalchemy import or_, and_, func

from models import db, User, Room, Booking, Invoice, FoodItem, FoodOrder

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-hotel-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:root@127.0.0.1:3306/hotel_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins='*')

# Ensure tables exist
with app.app_context():
    db.create_all()
    # Create an admin user if not exists
    if not User.query.filter_by(role='Admin').first():
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw('admin'.encode('utf-8'), salt)
        admin = User(name='Admin', email='admin@hotel.com', password_hash=hashed.decode('utf-8'), role='Admin')
        db.session.add(admin)
        db.session.commit()
    
    if not FoodItem.query.first():
        db.session.add_all([
            FoodItem(name='Club Sandwich', description='Classic turkey and bacon club', price=15.0),
            FoodItem(name='Margherita Pizza', description='Fresh mozzarella and basil', price=18.0),
            FoodItem(name='Caesar Salad', description='Crispy romaine with parmesan', price=12.0)
        ])
        db.session.commit()

# --- ROUTES ---

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('index.html', user=session)

@app.route('/login')
def login_page():
    return render_template('login.html')

# --- API ENDPOINTS ---

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    name, email, password, role = data.get('name'), data.get('email'), data.get('password'), data.get('role', 'Guest')
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'User already exists'}), 400
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    user = User(name=name, email=email, password_hash=hashed.decode('utf-8'), role=role)
    db.session.add(user)
    db.session.commit()
    return jsonify({'message': 'Registered successfully'})

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(email=data.get('email')).first()
    if user and bcrypt.checkpw(data.get('password').encode('utf-8'), user.password_hash.encode('utf-8')):
        session['user_id'] = user.id
        session['role'] = user.role
        session['name'] = user.name
        return jsonify({'message': 'Logged in', 'role': user.role})
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out'})

@app.route('/api/rooms', methods=['GET', 'POST'])
def manage_rooms():
    if request.method == 'POST':
        if session.get('role') not in ['Admin', 'Receptionist']:
            return jsonify({'error': 'Unauthorized'}), 403
        data = request.json
        room = Room(number=data['number'], type=data['type'], price=data['price'], status=data.get('status', 'Available'))
        db.session.add(room)
        db.session.commit()
        socketio.emit('room_update', {'action': 'add', 'room': {'id': room.id, 'number': room.number, 'status': room.status}})
        return jsonify({'message': 'Room added'})
    
    rooms = Room.query.all()
    room_data = [{'id': r.id, 'number': r.number, 'type': r.type, 'price': r.price, 'status': r.status} for r in rooms]
    return jsonify(room_data)

@app.route('/api/rooms/<int:room_id>', methods=['PUT', 'DELETE'])
def update_room(room_id):
    if session.get('role') not in ['Admin', 'Receptionist']:
        return jsonify({'error': 'Unauthorized'}), 403
    room = Room.query.get_or_404(room_id)
    if request.method == 'PUT':
        data = request.json
        if 'status' in data: room.status = data['status']
        if 'price' in data: room.price = data['price']
        if 'type' in data: room.type = data['type']
        db.session.commit()
        socketio.emit('room_update', {'action': 'update', 'room': {'id': room.id, 'number': room.number, 'status': room.status}})
        return jsonify({'message': 'Room updated'})
    elif request.method == 'DELETE':
        db.session.delete(room)
        db.session.commit()
        socketio.emit('room_update', {'action': 'delete', 'room_id': room_id})
        return jsonify({'message': 'Room deleted'})

@app.route('/api/bookings', methods=['GET', 'POST'])
def manage_bookings():
    if request.method == 'POST':
        if 'user_id' not in session: return jsonify({'error': 'Unauthorized'}), 401
        data = request.json
        start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
        end_date = datetime.strptime(data['end_date'], '%Y-%m-%d')
        room_id = data['room_id']
        
        # Prevent double booking
        overlapping = Booking.query.filter(
            Booking.room_id == room_id,
            Booking.status.in_(['Confirmed', 'Checked-In']),
            Booking.start_date < end_date,
            Booking.end_date > start_date
        ).first()

        if overlapping:
            return jsonify({'error': 'Room already booked for these dates'}), 400

        # Change room status if booked today
        room = Room.query.get(room_id)
        if start_date.date() == datetime.now(timezone.utc).date():
            room.status = 'Booked'

        payment_type = data.get('payment_type', 'Card')
        booking = Booking(user_id=session['user_id'], room_id=room_id, start_date=start_date, end_date=end_date, payment_type=payment_type)
        db.session.add(booking)
        db.session.commit()

        # Emit real-time notification
        socketio.emit('notification', {'message': f'New booking for Room {room.number}'}, broadcast=True)
        socketio.emit('room_update', {'action': 'update', 'room': {'id': room.id, 'number': room.number, 'status': room.status}})
        return jsonify({'message': 'Booking confirmed'})

    bookings = Booking.query.all()
    res = [{'id': b.id, 'room_id': b.room_id, 'start_date': b.start_date.isoformat(), 'end_date': b.end_date.isoformat(), 'status': b.status, 'payment_type': b.payment_type} for b in bookings]
    return jsonify(res)

@app.route('/api/bookings/<int:booking_id>/checkin', methods=['POST'])
def checkin(booking_id):
    if session.get('role') not in ['Admin', 'Receptionist']: return jsonify({'error': 'Unauthorized'}), 403
    booking = Booking.query.get_or_404(booking_id)
    if booking.status != 'Confirmed': return jsonify({'error': 'Invalid state'}), 400
    
    booking.status = 'Checked-In'
    booking.room.status = 'Occupied'
    db.session.commit()
    
    socketio.emit('room_update', {'action': 'update', 'room': {'id': booking.room.id, 'status': 'Occupied'}})
    socketio.emit('notification', {'message': f'Room {booking.room.number} checked in.'})
    return jsonify({'message': 'Checked In'})

@app.route('/api/bookings/<int:booking_id>/checkout', methods=['POST'])
def checkout(booking_id):
    if session.get('role') not in ['Admin', 'Receptionist']: return jsonify({'error': 'Unauthorized'}), 403
    booking = Booking.query.get_or_404(booking_id)
    if booking.status != 'Checked-In': return jsonify({'error': 'Invalid state'}), 400
    
    # Generate Invoice
    days = (booking.end_date - booking.start_date).days or 1
    room_charges = float(days * booking.room.price)
    
    extra_charges = sum([order.total_price for order in booking.food_orders])
    
    taxes = (room_charges + extra_charges) * 0.1 # 10% tax
    total = room_charges + extra_charges + taxes

    invoice = Invoice(booking_id=booking.id, room_charges=room_charges, extra_charges=extra_charges, total=total, payment_status='Paid')
    db.session.add(invoice)

    booking.status = 'Checked-Out'
    booking.room.status = 'Available'
    db.session.commit()

    socketio.emit('room_update', {'action': 'update', 'room': {'id': booking.room.id, 'status': 'Available'}})
    socketio.emit('notification', {'message': f'Room {booking.room.number} checked out. Bill: ${total}'})
    return jsonify({'message': 'Checked out successfully. Bill generated.', 'total': total})

@app.route('/api/admin/stats', methods=['GET'])
def admin_stats():
    if session.get('role') != 'Admin': return jsonify({'error': 'Unauthorized'}), 403
    total_rooms = Room.query.count()
    occupied = Room.query.filter_by(status='Occupied').count()
    available = Room.query.filter_by(status='Available').count()
    total_bookings = Booking.query.filter(func.date(Booking.created_at) == datetime.now(timezone.utc).date()).count()
    revenue = db.session.query(func.sum(Invoice.total)).filter_by(payment_status='Paid').scalar() or 0

    return jsonify({
        'total_rooms': total_rooms,
        'occupied': occupied,
        'available': available,
        'today_bookings': total_bookings,
        'revenue': revenue
    })

@app.route('/api/admin/staff', methods=['POST'])
def add_staff():
    if session.get('role') != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403
    data = request.json
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 'Receptionist')
    
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'User already exists'}), 400
        
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    user = User(name=name, email=email, password_hash=hashed.decode('utf-8'), role=role)
    db.session.add(user)
    db.session.commit()
    return jsonify({'message': f'{role} account created successfully'})

@app.route('/api/user/invoices', methods=['GET'])
def get_user_invoices():
    if 'user_id' not in session: return jsonify({'error': 'Unauthorized'}), 401
    bookings = Booking.query.filter_by(user_id=session['user_id']).all()
    invoices = Invoice.query.filter(Invoice.booking_id.in_([b.id for b in bookings])).all()
    res = [{
        'id': i.id,
        'room': i.booking.room.number,
        'room_charges': i.room_charges,
        'extra_charges': i.extra_charges,
        'total': i.total,
        'date': i.booking.end_date.isoformat()
    } for i in invoices]
    return jsonify(res)

@app.route('/api/food', methods=['GET'])
def get_food():
    items = FoodItem.query.filter_by(is_available=True).all()
    return jsonify([{'id': i.id, 'name': i.name, 'description': i.description, 'price': i.price, 'image_url': i.image_url} for i in items])

@app.route('/api/food/order', methods=['POST'])
def order_food():
    if 'user_id' not in session: return jsonify({'error': 'Unauthorized'}), 401
    booking = Booking.query.filter_by(user_id=session['user_id'], status='Checked-In').first()
    if not booking: return jsonify({'error': 'No active room found. You must be Checked-In to order food.'}), 400
    
    data = request.json
    food_id = data.get('food_id')
    custom_request = data.get('custom_request')
    qty = data.get('quantity', 1)
    
    if food_id:
        food = FoodItem.query.get(food_id)
        if not food: return jsonify({'error': 'Food not found'}), 404
        order = FoodOrder(booking_id=booking.id, food_item_id=food.id, quantity=qty, total_price=food.price * qty)
    elif custom_request:
        order = FoodOrder(booking_id=booking.id, custom_request=custom_request, quantity=qty, total_price=200.0 * qty) # Default 200 base price
    else:
        return jsonify({'error': 'Must provide food_id or custom_request'}), 400

    db.session.add(order)
    db.session.commit()
    
    socketio.emit('notification', {'message': f'New food order for Room {booking.room.number}'}, broadcast=True)
    return jsonify({'message': 'Food ordered successfully!'})

@app.route('/api/admin/food_orders', methods=['GET'])
def get_food_orders():
    if session.get('role') not in ['Admin', 'Receptionist']: return jsonify({'error': 'Unauthorized'}), 403
    orders = FoodOrder.query.filter(FoodOrder.status.in_(['Pending', 'Accepted'])).all()
    res = [{
        'id': o.id, 'room': o.booking.room.number, 'food': o.food_item.name if o.food_item else f"Custom: {o.custom_request}",
        'quantity': o.quantity, 'total': o.total_price, 'status': o.status
    } for o in orders]
    return jsonify(res)

@app.route('/api/admin/food_orders/<int:order_id>/accept', methods=['POST'])
def accept_food(order_id):
    if session.get('role') not in ['Admin', 'Receptionist']: return jsonify({'error': 'Unauthorized'}), 403
    order = FoodOrder.query.get(order_id)
    if order and order.status == 'Pending':
        order.status = 'Accepted'
        db.session.commit()
        return jsonify({'message': 'Order Accepted & Preparing'})
    return jsonify({'error': 'Order not found or invalid status'}), 404

@app.route('/api/admin/food_orders/<int:order_id>/deliver', methods=['POST'])
def deliver_food(order_id):
    if session.get('role') not in ['Admin', 'Receptionist']: return jsonify({'error': 'Unauthorized'}), 403
    order = FoodOrder.query.get(order_id)
    if order and order.status == 'Accepted':
        order.status = 'Delivered'
        db.session.commit()
        return jsonify({'message': 'Order marked as Delivered'})
    return jsonify({'error': 'Order not found or invalid status (must be Accepted first)'}), 404

# --- SOCKET IO EVENTS ---

@socketio.on('connect')
def test_connect():
    print('Client connected')

@socketio.on('disconnect')
def test_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)

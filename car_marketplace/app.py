from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import random
from datetime import datetime

# App initialization
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///marketplace.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- Database Models ---

class User(UserMixin, db.Model):
    """User model for Dealers"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    whatsapp_number = db.Column(db.String(20), nullable=False)
    cars = db.relationship('Car', backref='dealer', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Car(db.Model):
    """Car model for listings"""
    id = db.Column(db.Integer, primary_key=True)
    make = db.Column(db.String(100), nullable=False)
    model = db.Column(db.String(100), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    mileage = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(255), nullable=True)
    whatsapp_number = db.Column(db.String(20), nullable=False)
    is_sold = db.Column(db.Boolean, default=False, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Routes ---

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        whatsapp_number = request.form.get('whatsapp_number')
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists.', 'danger')
            return redirect(url_for('signup'))
        new_user = User(username=username, whatsapp_number=whatsapp_number)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('login'))
        login_user(user)
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/dashboard')
@login_required
def dashboard():
    cars = Car.query.filter_by(user_id=current_user.id).order_by(Car.is_sold, Car.id.desc()).all()
    return render_template('dashboard.html', cars=cars)

@app.route('/car/add', methods=['GET', 'POST'])
@login_required
def add_car():
    if request.method == 'POST':
        new_car = Car(
            make=request.form['make'],
            model=request.form['model'],
            year=int(request.form['year']),
            mileage=int(request.form['mileage']),
            price=float(request.form['price']),
            description=request.form['description'],
            image_url=request.form['image_url'],
            whatsapp_number=request.form['whatsapp_number'],
            user_id=current_user.id
        )
        db.session.add(new_car)
        db.session.commit()
        flash('New car listing added successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('car_form.html')

@app.route('/car/<int:car_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_car(car_id):
    car = Car.query.get_or_404(car_id)
    if car.user_id != current_user.id:
        flash('You are not authorized to edit this listing.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        car.make = request.form['make']
        car.model = request.form['model']
        car.year = int(request.form['year'])
        car.mileage = int(request.form['mileage'])
        car.price = float(request.form['price'])
        car.description = request.form['description']
        car.image_url = request.form['image_url']
        car.whatsapp_number = request.form['whatsapp_number']
        db.session.commit()
        flash('Car listing updated successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('car_form.html', car=car)

@app.route('/car/<int:car_id>/delete', methods=['POST'])
@login_required
def delete_car(car_id):
    car = Car.query.get_or_404(car_id)
    if car.user_id != current_user.id:
        flash('You are not authorized to delete this listing.', 'danger')
        return redirect(url_for('dashboard'))

    db.session.delete(car)
    db.session.commit()
    flash('Car listing deleted successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/car/<int:car_id>/sold', methods=['GET'])
@login_required
def mark_sold(car_id):
    car = Car.query.get_or_404(car_id)
    if car.user_id != current_user.id:
        flash('You are not authorized to modify this listing.', 'danger')
        return redirect(url_for('dashboard'))

    car.is_sold = not car.is_sold
    db.session.commit()
    status = "sold" if car.is_sold else "unsold"
    flash(f'Car marked as {status}!', 'success')
    return redirect(url_for('dashboard'))

# --- Public Routes ---
@app.route('/browse')
def browse_cars():
    query = Car.query.filter_by(is_sold=False)

    # Search and Filter
    if request.args.get('make'):
        query = query.filter(Car.make.ilike(f"%{request.args.get('make')}%"))
    if request.args.get('model'):
        query = query.filter(Car.model.ilike(f"%{request.args.get('model')}%"))
    if request.args.get('year'):
        query = query.filter_by(year=int(request.args.get('year')))
    if request.args.get('max_price'):
        query = query.filter(Car.price <= float(request.args.get('max_price')))

    cars = query.order_by(Car.id.desc()).all()
    return render_template('browse.html', cars=cars)

@app.route('/car/<int:car_id>')
def car_detail(car_id):
    car = Car.query.get_or_404(car_id)
    return render_template('car_detail.html', car=car)

@app.route('/dealer/<string:username>')
def dealer_page(username):
    dealer = User.query.filter_by(username=username).first_or_404()
    cars = Car.query.filter_by(user_id=dealer.id).order_by(Car.is_sold, Car.id.desc()).all()
    return render_template('dealer_page.html', dealer=dealer, cars=cars)

# --- AI Tool ---
@app.route('/suggest_price', methods=['GET', 'POST'])
def suggest_price():
    if request.method == 'POST':
        make = request.form.get('make')
        model = request.form.get('model')
        year = int(request.form.get('year'))

        # Simple "AI" logic
        base_price = 30000
        # Hashing the make and model to get a consistent "random" base
        base_price += (hash(make.lower()) % 5000) + (hash(model.lower()) % 5000)

        # Depreciation based on age
        current_year = datetime.now().year
        age = current_year - year
        depreciation = age * 1500

        suggested_price = base_price - depreciation - random.randint(0, 2000)

        if suggested_price < 1500:
            suggested_price = 1500 + random.randint(0, 1000)

        return render_template('suggest_price.html', suggested_price=suggested_price, make=make, model=model, year=year)

    return render_template('suggest_price.html')


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)
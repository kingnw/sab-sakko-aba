from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# Initialize the SQLAlchemy database instance
db = SQLAlchemy()

class User(UserMixin, db.Model):
    """Model for storing user details."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def __init__(self, username, password):
        """Initializes a new user with a hashed password."""
        self.username = username
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check if the provided password matches the stored hash."""
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def create_user(username, password):
        """Creates a new user and adds to the database."""
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        return new_user

    @staticmethod
    def get(username):
        """Fetch a user by username."""
        return User.query.filter_by(username=username).first()

    @staticmethod
    def get_by_id(user_id):
        """Fetch a user by their user ID."""
        return User.query.get(int(user_id))

class UserMovies(db.Model):
    """Model for storing user's movies in watchlist or favorites."""
    __tablename__ = 'user_movies'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    movie_id = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(50), nullable=False)  # 'watchlist' or 'favorites'

    # Relationship to access the user who added the movie
    user = db.relationship('User', backref=db.backref('user_movies', lazy=True))

class Review(db.Model):
    """Model for storing user reviews and ratings for movies."""
    __tablename__ = 'reviews'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    movie_id = db.Column(db.Integer, nullable=False)
    rating = db.Column(db.Float, nullable=False)
    review_text = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to access the user who made the review
    user = db.relationship('User', backref=db.backref('reviews', lazy=True))

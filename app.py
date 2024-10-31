from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from auth import auth_blueprint
from models import db, User, UserMovies, Review
from recommendation import get_movie_recommendations
import requests

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a strong secret key

# Configure SQLAlchemy database URI
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy and Flask-Login
db.init_app(app)
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

# TMDB API Key
API_KEY = '9ba93d1cf5e3054788a377f636ea1033'  # Consider using environment variables for security

# Load user callback for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Register the auth blueprint
app.register_blueprint(auth_blueprint, url_prefix='/auth')

# TMDB API Functions
def get_top_rated_movies():
    url = f'https://api.themoviedb.org/3/movie/top_rated?api_key={API_KEY}&language=en-US&page=1'
    response = requests.get(url)
    return process_movie_results(response, include_backdrop=False)

def get_new_released_movies():
    url = f'https://api.themoviedb.org/3/movie/now_playing?api_key={API_KEY}&language=en-US&page=1'
    response = requests.get(url)
    return process_movie_results(response, include_backdrop=False)

def get_trending_movies():
    url = f'https://api.themoviedb.org/3/trending/movie/week?api_key={API_KEY}'
    response = requests.get(url)
    return process_movie_results(response, include_backdrop=True)  # Include backdrops for trending movies

def get_genres():
    """Fetches a list of genres from the TMDB API."""
    url = f'https://api.themoviedb.org/3/genre/movie/list?api_key={API_KEY}&language=en-US'
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get('genres', [])
    return []

def search_movie(movie_title, release_year=None, rating=None, genre=None, language=None):
    url = f'https://api.themoviedb.org/3/search/movie?api_key={API_KEY}&query={movie_title}&page=1&include_adult=false'
    response = requests.get(url)
    if response.status_code == 200:
        results = response.json().get('results', [])
        filtered_results = []
        
        for movie in results:
            # Apply filters
            if release_year:
                movie_release_year = movie.get('release_date', '').split('-')[0]
                if movie_release_year != str(release_year):
                    continue
            if rating:
                if float(movie.get('vote_average', 0)) < float(rating):
                    continue
            if genre:
                if int(genre) not in movie.get('genre_ids', []):
                    continue
            if language:
                if movie.get('original_language') != language:
                    continue

            # Add poster and rating fields
            movie['rating'] = movie.get('vote_average', 'N/A')
            poster_path = movie.get('poster_path')
            movie['poster'] = f"https://image.tmdb.org/t/p/original{poster_path}" if poster_path else "https://via.placeholder.com/500x750?text=No+Image"
            filtered_results.append(movie)
        
        return filtered_results
    return []

def get_movie_details(movie_id):
    url = f'https://api.themoviedb.org/3/movie/{movie_id}?api_key={API_KEY}&language=en-US'
    response = requests.get(url)
    if response.status_code == 200:
        movie = response.json()
        movie['rating'] = movie.get('vote_average', 'N/A')
        poster_path = movie.get('poster_path')
        movie['poster'] = f"https://image.tmdb.org/t/p/original{poster_path}" if poster_path else "https://via.placeholder.com/500x750?text=No+Image"
        return movie
    return None

def get_recommendations(movie_id):
    """Fetches recommendations for a given movie ID."""
    url = f'https://api.themoviedb.org/3/movie/{movie_id}/recommendations?api_key={API_KEY}'
    response = requests.get(url)
    return process_movie_results(response, include_backdrop=False)

def process_movie_results(response, include_backdrop=False):
    if response.status_code == 200:
        results = response.json().get('results', [])
        for movie in results:
            movie['rating'] = movie.get('vote_average', 'N/A')
            # Use higher resolution poster images
            poster_path = movie.get('poster_path')
            movie['poster'] = f"https://image.tmdb.org/t/p/original{poster_path}" if poster_path else "https://via.placeholder.com/500x750?text=No+Image"
            # Backdrop images for carousel
            if include_backdrop:
                backdrop_path = movie.get('backdrop_path')
                movie['backdrop'] = f"https://image.tmdb.org/t/p/original{backdrop_path}" if backdrop_path else "https://via.placeholder.com/1280x720?text=No+Image"
        return results
    return []

# Calculate average rating for a movie
def calculate_avg_rating(movie_id):
    reviews = Review.query.filter_by(movie_id=movie_id).all()
    if reviews:
        avg_rating = sum([review.rating for review in reviews]) / len(reviews)
        return round(avg_rating, 1)
    return "No ratings yet"

# Routes for Watchlist and Favorites
@app.route('/<category>/add/<int:movie_id>', methods=['POST'])
@login_required
def add_movie(category, movie_id):
    if category not in ['watchlist', 'favorites']:
        flash("Invalid category.", "danger")
        return redirect(url_for('index'))

    existing_entry = UserMovies.query.filter_by(user_id=current_user.id, movie_id=movie_id, category=category).first()
    if not existing_entry:
        new_entry = UserMovies(user_id=current_user.id, movie_id=movie_id, category=category)
        try:
            db.session.add(new_entry)
            db.session.commit()
            flash(f"Movie added to {category}.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error adding movie to {category}: {str(e)}", "danger")
    else:
        flash("Movie is already in your list.", "info")

    return redirect(url_for(f'view_{category}'))

@app.route('/watchlist')
@login_required
def view_watchlist():
    watchlist_movies = UserMovies.query.filter_by(user_id=current_user.id, category='watchlist').all()
    movies = [get_movie_details(movie.movie_id) for movie in watchlist_movies if get_movie_details(movie.movie_id)]
    if not movies:
        flash("Your watchlist is empty.", "info")
    return render_template('watchlist.html', movies=movies, category="Watchlist")

@app.route('/favorites')
@login_required
def view_favorites():
    favorite_movies = UserMovies.query.filter_by(user_id=current_user.id, category='favorites').all()
    movies = [get_movie_details(movie.movie_id) for movie in favorite_movies if get_movie_details(movie.movie_id)]
    if not movies:
        flash("Your favorites list is empty.", "info")
    return render_template('favorites.html', movies=movies, category="Favorites")

# Route to recommend movies with search and filters
@app.route('/recommend', methods=['POST'])
def recommend():
    # Collect parameters from POST for filter functionality
    movie_title = request.form.get('movie_title', '')
    release_year = request.form.get('release_year', '')
    rating = request.form.get('rating', '')
    genre = request.form.get('genre', '')
    language = request.form.get('language', '')

    # Fetch genres for filter dropdown
    genres = get_genres()

    # Fetch search results based on filters
    search_results = search_movie(movie_title, release_year, rating, genre, language)
    
    # Only get recommendations if there's a movie title to base recommendations on
    recommendations = []
    if movie_title and search_results:
        recommendations = get_recommendations(search_results[0]['id'])

    # Always fetch trending movies to display if recommendations are absent
    trending_movies = get_trending_movies()
    most_watched_movies = get_top_rated_movies()
    new_released_movies = get_new_released_movies()

    return render_template(
        'index.html',
        search_results=search_results,
        recommendations=recommendations,
        search_query=movie_title,
        genres=genres,
        trending_movies=trending_movies,
        most_watched_movies=most_watched_movies,
        new_released_movies=new_released_movies
    )

# Autocomplete Route
@app.route('/autocomplete', methods=['GET'])
def autocomplete():
    query = request.args.get('q', '')
    if not query:
        return jsonify([])

    url = f'https://api.themoviedb.org/3/search/movie?api_key={API_KEY}&query={query}&page=1&include_adult=false'
    response = requests.get(url)
    
    if response.status_code == 200:
        results = response.json().get('results', [])
        suggestions = [{'label': movie['title'], 'value': movie['title'], 'id': movie['id']} for movie in results[:10]]
        return jsonify(suggestions)
    else:
        return jsonify([])

# Home route displaying trending movies, most watched, and new released movies
@app.route('/')
def index():
    trending_movies = get_trending_movies()
    most_watched_movies = get_top_rated_movies()
    new_released_movies = get_new_released_movies()
    genres = get_genres()
    return render_template('index.html',
                           trending_movies=trending_movies,
                           most_watched_movies=most_watched_movies,
                           new_released_movies=new_released_movies,
                           genres=genres)

# Route to display top-rated movies
@app.route('/top-rated')
def top_rated():
    top_rated_movies = get_top_rated_movies()
    return render_template('top_rated.html', top_rated_movies=top_rated_movies)

# Route to display newly released movies
@app.route('/new-released')
def new_released():
    new_released_movies = get_new_released_movies()
    return render_template('new_released.html', new_released_movies=new_released_movies)

# Route to display movie details with reviews and content-based recommendations
@app.route('/movie/<int:movie_id>', methods=['GET', 'POST'])
def movie_details(movie_id):
    movie = get_movie_details(movie_id)
    if not movie:
        return render_template('404.html'), 404

    reviews = Review.query.filter_by(movie_id=movie_id).order_by(Review.created_at.desc()).all()
    avg_rating = calculate_avg_rating(movie_id)
    recommendations = get_movie_recommendations(movie['title'])

    if request.method == 'POST' and current_user.is_authenticated:
        rating = request.form.get('rating')
        review_text = request.form.get('review_text')

        if rating:
            new_review = Review(user_id=current_user.id, movie_id=movie_id, rating=float(rating), review_text=review_text)
            db.session.add(new_review)
            db.session.commit()
            flash("Review submitted successfully!", "success")
            return redirect(url_for('movie_details', movie_id=movie_id))

    return render_template('movie_details.html', movie=movie, reviews=reviews, avg_rating=avg_rating, recommendations=recommendations)

# Initialize database tables if they do not exist
with app.app_context():
    db.create_all()

# Start the Flask app
if __name__ == '__main__':
    app.run(debug=True, port=5001)

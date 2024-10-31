from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from auth import auth_blueprint
from models import db, User, UserMovies, Review
from recommendation import get_movie_recommendations
import requests
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key')  # Use environment variable for security

# Configure SQLAlchemy database URI
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy and Flask-Login
db.init_app(app)
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

# TMDB API Key (Use environment variable for security)
API_KEY = os.environ.get('TMDB_API_KEY', '9ba93d1cf5e3054788a377f636ea1033')
TMDB_BASE_URL = 'https://api.themoviedb.org/3'

# Load user callback for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Register the auth blueprint
app.register_blueprint(auth_blueprint, url_prefix='/auth')

# TMDB API Functions
def get_top_rated_movies():
    url = f'{TMDB_BASE_URL}/movie/top_rated'
    params = {
        'api_key': API_KEY,
        'language': 'en-US',
        'page': 1
    }
    response = requests.get(url, params=params)
    return process_movie_results(response, include_backdrop=False)

def get_new_released_movies():
    url = f'{TMDB_BASE_URL}/movie/now_playing'
    params = {
        'api_key': API_KEY,
        'language': 'en-US',
        'page': 1
    }
    response = requests.get(url, params=params)
    return process_movie_results(response, include_backdrop=False)

def get_trending_movies():
    url = f'{TMDB_BASE_URL}/trending/movie/week'
    params = {
        'api_key': API_KEY,
    }
    response = requests.get(url, params=params)
    return process_movie_results(response, include_backdrop=True)

def get_genres():
    """Fetches a list of genres from the TMDB API."""
    url = f'{TMDB_BASE_URL}/genre/movie/list'
    params = {
        'api_key': API_KEY,
        'language': 'en-US'
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json().get('genres', [])
    return []

def search_movie(movie_title, filters=None):
    """Searches for movies based on title and optional filters."""
    url = f'{TMDB_BASE_URL}/search/movie'
    params = {
        'api_key': API_KEY,
        'language': 'en-US',
        'query': movie_title,
        'page': 1,
        'include_adult': False
    }

    if filters:
        if 'release_year_min' in filters and filters['release_year_min']:
            params['primary_release_date.gte'] = f"{filters['release_year_min']}-01-01"
        if 'release_year_max' in filters and filters['release_year_max']:
            params['primary_release_date.lte'] = f"{filters['release_year_max']}-12-31"
        if 'rating_min' in filters and filters['rating_min']:
            params['vote_average.gte'] = filters['rating_min']
        if 'rating_max' in filters and filters['rating_max']:
            params['vote_average.lte'] = filters['rating_max']
        if 'genres' in filters and filters['genres']:
            # TMDB allows filtering by genres using with_genres
            # The genres should be a comma-separated string of genre IDs
            params['with_genres'] = ','.join(filters['genres'])
        if 'language' in filters and filters['language']:
            params['with_original_language'] = filters['language']
        if 'sort_by' in filters and filters['sort_by']:
            params['sort_by'] = filters['sort_by']

    response = requests.get(url, params=params)
    if response.status_code == 200:
        return process_movie_results(response, include_backdrop=False)
    return []

def get_movie_details(movie_id):
    """Fetches detailed information for a specific movie."""
    url = f'{TMDB_BASE_URL}/movie/{movie_id}'
    params = {
        'api_key': API_KEY,
        'language': 'en-US'
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        movie = response.json()
        movie['rating'] = movie.get('vote_average', 'N/A')
        poster_path = movie.get('poster_path')
        movie['poster'] = f"https://image.tmdb.org/t/p/original{poster_path}" if poster_path else "https://via.placeholder.com/500x750?text=No+Image"
        backdrop_path = movie.get('backdrop_path')
        movie['backdrop'] = f"https://image.tmdb.org/t/p/original{backdrop_path}" if backdrop_path else "https://via.placeholder.com/1280x720?text=No+Image"
        return movie
    return None

def get_recommendations(movie_id):
    """Fetches recommendations for a given movie ID."""
    url = f'{TMDB_BASE_URL}/movie/{movie_id}/recommendations'
    params = {
        'api_key': API_KEY,
        'language': 'en-US',
        'page': 1
    }
    response = requests.get(url, params=params)
    return process_movie_results(response, include_backdrop=False)

def process_movie_results(response, include_backdrop=False):
    """Processes movie results from TMDB API responses."""
    if response.status_code == 200:
        results = response.json().get('results', [])
        for movie in results:
            movie['rating'] = movie.get('vote_average', 'N/A')
            poster_path = movie.get('poster_path')
            movie['poster'] = f"https://image.tmdb.org/t/p/original{poster_path}" if poster_path else "https://via.placeholder.com/500x750?text=No+Image"
            if include_backdrop:
                backdrop_path = movie.get('backdrop_path')
                movie['backdrop'] = f"https://image.tmdb.org/t/p/original{backdrop_path}" if backdrop_path else "https://via.placeholder.com/1280x720?text=No+Image"
        return results
    return []

def calculate_avg_rating(movie_id):
    """Calculates the average rating for a movie based on user reviews."""
    reviews = Review.query.filter_by(movie_id=movie_id).all()
    if reviews:
        avg_rating = sum([review.rating for review in reviews]) / len(reviews)
        return round(avg_rating, 1)
    return "No ratings yet"

# Route to add a movie to Watchlist or Favorites
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

# Route to remove a movie from Watchlist or Favorites
@app.route('/<category>/remove/<int:movie_id>', methods=['POST'])
@login_required
def remove_movie(category, movie_id):
    if category not in ['watchlist', 'favorites']:
        flash("Invalid category.", "danger")
        return redirect(url_for('index'))
    
    entry = UserMovies.query.filter_by(user_id=current_user.id, movie_id=movie_id, category=category).first()
    if entry:
        try:
            db.session.delete(entry)
            db.session.commit()
            flash(f"Movie removed from {category}.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error removing movie from {category}: {str(e)}", "danger")
    else:
        flash("Movie not found in your list.", "warning")
    
    return redirect(url_for(f'view_{category}'))

# Route to view Watchlist
@app.route('/watchlist')
@login_required
def view_watchlist():
    watchlist_movies = UserMovies.query.filter_by(user_id=current_user.id, category='watchlist').all()
    movies = [get_movie_details(movie.movie_id) for movie in watchlist_movies if get_movie_details(movie.movie_id)]
    if not movies:
        flash("Your watchlist is empty.", "info")
    return render_template('watchlist.html', movies=movies, category="Watchlist")

# Route to view Favorites
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
    # Extract search and filter parameters from the form
    movie_title = request.form.get('movie_title', '')
    release_year_min = request.form.get('release_year_min', '')
    release_year_max = request.form.get('release_year_max', '')
    rating_min = request.form.get('rating_min', '')
    rating_max = request.form.get('rating_max', '')
    genres = request.form.getlist('genres')  # For multiple genres
    language = request.form.get('language', '')
    sort_by = request.form.get('sort_by', '')

    genres_list = get_genres()

    # Prepare filters dictionary
    filters = {
        'release_year_min': release_year_min,
        'release_year_max': release_year_max,
        'rating_min': rating_min,
        'rating_max': rating_max,
        'genres': genres,
        'language': language,
        'sort_by': sort_by
    }

    # Perform movie search with filters
    search_results = search_movie(movie_title, filters=filters)

    # Fetch recommendations based on the first search result
    recommendations = []
    if movie_title and search_results:
        recommendations = get_recommendations(search_results[0]['id'])

    # Fetch other movie categories
    trending_movies = get_trending_movies()
    most_watched_movies = get_top_rated_movies()
    new_released_movies = get_new_released_movies()

    return render_template(
        'index.html',
        search_results=search_results,
        recommendations=recommendations,
        search_query=movie_title,
        genres=genres_list,
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

    url = f'{TMDB_BASE_URL}/search/movie'
    params = {
        'api_key': API_KEY,
        'language': 'en-US',
        'query': query,
        'page': 1,
        'include_adult': False
    }
    response = requests.get(url, params=params)
    
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
    genres = get_genres()
    return render_template('top_rated.html', top_rated_movies=top_rated_movies, genres=genres)

# Route to display newly released movies
@app.route('/new-released')
def new_released():
    new_released_movies = get_new_released_movies()
    genres = get_genres()
    return render_template('new_released.html', new_released_movies=new_released_movies, genres=genres)

# Route to display trending movies
@app.route('/trending')
def trending():
    trending_movies = get_trending_movies()
    genres = get_genres()
    return render_template('trending.html', trending_movies=trending_movies, genres=genres)

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
            try:
                rating_value = float(rating)
                if 0 <= rating_value <= 10:
                    new_review = Review(user_id=current_user.id, movie_id=movie_id, rating=rating_value, review_text=review_text)
                    db.session.add(new_review)
                    db.session.commit()
                    flash("Review submitted successfully!", "success")
                else:
                    flash("Rating must be between 0 and 10.", "warning")
            except ValueError:
                flash("Invalid rating value.", "danger")
            return redirect(url_for('movie_details', movie_id=movie_id))
        else:
            flash("Please provide a rating.", "warning")

    return render_template('movie_details.html', movie=movie, reviews=reviews, avg_rating=avg_rating, recommendations=recommendations)

# Route to display filters page
@app.route('/filters')
def filters():
    genres = get_genres()
    return render_template('filters.html', genres=genres)

# Route to display filtered Watchlist (Optional Enhancement)
@app.route('/filter_watchlist', methods=['GET'])
@login_required
def filter_watchlist():
    sortby = request.args.get('sortby')
    movies = get_filtered_watchlist(current_user.id, sortby)
    return render_template('watchlist.html', movies=movies, category="Watchlist")

# Route to display filtered Favorites (Optional Enhancement)
@app.route('/filter_favorites', methods=['GET'])
@login_required
def filter_favorites():
    sortby = request.args.get('sortby')
    movies = get_filtered_watchlist(current_user.id, sortby, category='favorites')
    return render_template('favorites.html', movies=movies, category="Favorites")

# Helper function to get filtered watchlist or favorites
def get_filtered_watchlist(user_id, sortby, category='watchlist'):
    watchlist_movies = UserMovies.query.filter_by(user_id=user_id, category=category).all()
    movies = [get_movie_details(movie.movie_id) for movie in watchlist_movies if get_movie_details(movie.movie_id)]
    
    if sortby:
        if sortby == 'rating_desc':
            movies.sort(key=lambda x: x.get('rating', 0), reverse=True)
        elif sortby == 'rating_asc':
            movies.sort(key=lambda x: x.get('rating', 0))
        elif sortby == 'release_date_desc':
            movies.sort(key=lambda x: x.get('release_date', ''), reverse=True)
        elif sortby == 'release_date_asc':
            movies.sort(key=lambda x: x.get('release_date', ''))
        elif sortby == 'title_asc':
            movies.sort(key=lambda x: x.get('title', '').lower())
        elif sortby == 'title_desc':
            movies.sort(key=lambda x: x.get('title', '').lower(), reverse=True)
    return movies

# Initialize database tables if they do not exist
with app.app_context():
    db.create_all()

# Start the Flask app
if __name__ == '__main__':
    app.run(debug=True, port=5004)

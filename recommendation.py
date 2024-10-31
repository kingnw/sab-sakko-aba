import requests
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

API_KEY = '9ba93d1cf5e3054788a377f636ea1033'  # Replace with your TMDB API key

def fetch_movie_data(movie_title):
    """Fetches movie data from TMDB API based on movie title."""
    url = f'https://api.themoviedb.org/3/search/movie?api_key={API_KEY}&query={movie_title}'
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get('results', [])
    else:
        return []

def fetch_movie_details(movie_id):
    """Fetches detailed data of a movie by its ID from TMDB API."""
    url = f'https://api.themoviedb.org/3/movie/{movie_id}?api_key={API_KEY}&language=en-US'
    response = requests.get(url)
    if response.status_code == 200:
        movie = response.json()
        movie['rating'] = movie.get('vote_average', 'N/A')
        poster_path = movie.get('poster_path')
        movie['poster'] = f"https://image.tmdb.org/t/p/w300{poster_path}" if poster_path else "https://via.placeholder.com/300x450?text=No+Image"
        return movie
    return None

def create_movie_dataset(movie_list):
    """Creates a DataFrame from a list of movie details, used for similarity calculations."""
    movies = []
    for movie in movie_list:
        details = fetch_movie_details(movie['id'])
        if details:
            movies.append({
                'id': details['id'],
                'title': details['title'],
                'genres': " ".join([genre['name'] for genre in details.get('genres', [])]),
                'overview': details.get('overview', ''),
                'rating': details.get('rating', 'N/A'),
                'poster': details.get('poster')
            })
    return pd.DataFrame(movies)

def preprocess_movie_data(movies_df):
    """Prepares and combines text features for content filtering."""
    # Fill NaNs in overview
    movies_df['overview'] = movies_df['overview'].fillna('')
    # Combine genres and overview for each movie into a single text feature
    movies_df['content'] = movies_df['genres'] + " " + movies_df['overview']
    return movies_df

def calculate_similarity(movies_df):
    """Calculates cosine similarity between movies based on TF-IDF vectors of the content features."""
    tfidf = TfidfVectorizer(stop_words='english')
    tfidf_matrix = tfidf.fit_transform(movies_df['content'])
    cosine_sim = linear_kernel(tfidf_matrix, tfidf_matrix)
    return cosine_sim

def get_content_recommendations(movie_id, movies_df, cosine_sim, num_recommendations=10):
    """Fetches content-based recommendations for a given movie."""
    indices = pd.Series(movies_df.index, index=movies_df['id']).drop_duplicates()
    idx = indices[movie_id]

    # Get similarity scores for all movies
    sim_scores = list(enumerate(cosine_sim[idx]))

    # Sort by similarity score and select the top results
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
    sim_scores = sim_scores[1:num_recommendations + 1]  # Exclude the first entry (the movie itself)

    # Get the recommended movie indices
    movie_indices = [i[0] for i in sim_scores]
    return movies_df.iloc[movie_indices][['id', 'title', 'rating', 'poster']].to_dict(orient='records')

def get_movie_recommendations(movie_title, num_recommendations=10):
    """Main function to fetch content-based movie recommendations."""
    # Fetch initial movies matching the title
    movie_list = fetch_movie_data(movie_title)
    if not movie_list:
        return []

    # Create a DataFrame of movies and preprocess the data
    movies_df = create_movie_dataset(movie_list)
    movies_df = preprocess_movie_data(movies_df)

    # Calculate similarity matrix
    cosine_sim = calculate_similarity(movies_df)

    # Get the movie ID of the first match to generate recommendations
    first_movie_id = movie_list[0]['id']
    return get_content_recommendations(first_movie_id, movies_df, cosine_sim, num_recommendations)

# Example usage
if __name__ == '__main__':
    movie_title = 'Inception'  # Example movie title
    recommendations = get_movie_recommendations(movie_title)
    for rec in recommendations:
        print(f"Title: {rec['title']}, Rating: {rec['rating']}, Poster URL: {rec['poster']}")

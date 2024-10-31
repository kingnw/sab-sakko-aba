import requests

API_KEY = '9ba93d1cf5e3054788a377f636ea1033'  # Replace with your TMDB API key

def search_movie(movie_title):
    url = f'https://api.themoviedb.org/3/search/movie?api_key={API_KEY}&query={movie_title}'
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get('results', [])
    else:
        return []

def get_recommendations(movie_id):
    url = f'https://api.themoviedb.org/3/movie/{movie_id}/recommendations?api_key={API_KEY}'
    response = requests.get(url)
    
    if response.status_code == 200:
        results = response.json().get('results', [])
        for movie in results:
            movie['rating'] = movie.get('vote_average', 'N/A')
            poster_path = movie.get('poster_path')
            if poster_path:
                # Construct the full image URL with the proper base URL and size (e.g., w200)
                movie['poster'] = f"https://image.tmdb.org/t/p/w200{poster_path}"
            else:
                # Use a placeholder if no poster is available
                movie['poster'] = "https://via.placeholder.com/200x300?text=No+Image"
        return results
    else:
        return []

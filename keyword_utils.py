import requests
import json
import urllib.parse

def get_youtube_suggestions(keyword):
    """
    Fetches search suggestions from YouTube's public autosuggest API.
    Returns a list of suggestion strings.
    """
    # Use client=firefox for easier JSON parsing
    encoded_kw = urllib.parse.quote(keyword)
    url = f"http://suggestqueries.google.com/complete/search?client=firefox&ds=yt&q={encoded_kw}"
    try:
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            data = response.json()
            if len(data) > 1:
                return data[1] # List of suggestions
    except Exception as e:
        print(f"Suggestion fetch failed for {keyword}: {e}")
    
    return []

def get_related_keywords(keyword, limit=5):
    """
    Fetches related keywords (synonyms/associations) using Datamuse API.
    Note: Datamuse is primarily English-based. 
    For Japanese, this might return limited results or require English input.
    """
    encoded_kw = urllib.parse.quote(keyword)
    url = f"https://api.datamuse.com/words?ml={encoded_kw}&limit={limit}"
    
    related = []
    try:
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            data = response.json()
            # data is list of dicts: [{'word': 'bitcoin', 'score': 123}, ...]
            related = [item['word'] for item in data]
    except Exception as e:
        print(f"Related keywords fetch failed for {keyword}: {e}")
        
    return related

import requests
import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io
import base64
import os

# Store client ID and secret as constants
CLIENT_ID = "58eac4fba0e84fd493f46d22bc12522c"
CLIENT_SECRET = "09eeeb1b3d034e23994761b959e1f876"

def get_spotify_token():
    url = "https://accounts.spotify.com/api/token"
    auth_string = f"{CLIENT_ID}:{CLIENT_SECRET}"
    auth_bytes = auth_string.encode("utf-8")
    auth_base64 = base64.b64encode(auth_bytes).decode("utf-8")
    
    headers = {"Authorization": f"Basic {auth_base64}"}
    data = {"grant_type": "client_credentials"}
    
    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        error_message = response.json().get("error_description", "Unknown error")
        st.error(f"Authentication failed: {error_message}")
        return None

def fetch_album_tracks(token, artist_name, album_name):
    url = "https://api.spotify.com/v1/search"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"q": f"artist:{artist_name} album:{album_name}", "type": "album", "limit": 1}
    
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        if data["albums"]["items"]:
            album_id = data["albums"]["items"][0]["id"]
            album_cover = data["albums"]["items"][0]["images"][0]["url"]
            tracks_url = f"https://api.spotify.com/v1/albums/{album_id}/tracks?limit=30"
            tracks_response = requests.get(tracks_url, headers=headers)
            if tracks_response.status_code == 200:
                tracks_data = tracks_response.json()
                return [track["name"] for track in tracks_data["items"]], album_cover
    return [], None

def categorize_rating(rating):
    if rating <= 3.0:
        return "Bad", "#FF4500"
    elif rating <= 6.0:
        return "Meh", "#FFA500"
    elif rating <= 7.0:
        return "Good", "#FFD700"
    elif rating <= 9.0:
        return "Great", "#00BFFF"
    else:
        return "Amazing", "#32CD32"

def create_graphic(album_cover, album_name, artist_name, tracks, ratings):
    rating_colors = {
        "Amazing": "#32CD32",
        "Great": "#00BFFF",
        "Good": "#FFD700",
        "Meh": "#FFA500",
        "Bad": "#FF4500",
        "Skit": "#808080",
    }
    
    response = requests.get(album_cover)
    album_image = Image.open(io.BytesIO(response.content)).resize((800, 800))
    blurred_background = album_image.filter(ImageFilter.GaussianBlur(20))
    
    image = Image.new("RGB", (800, 800))
    image.paste(blurred_background, (0, 0))
    draw = ImageDraw.Draw(image)
    
    title_font = ImageFont.load_default()
    track_font = ImageFont.load_default()
    bold_font = ImageFont.load_default()
    
    avg_rating = sum(ratings) / len(ratings) if ratings else 0
    draw.text((560, 260), f"Rating: {round(avg_rating, 2)}/10", fill="black", font=bold_font)
    
    tracklist_start_y = 170
    y_spacing = max(600 // max(len(tracks), 1), 20)
    
    for i, (track, rating) in enumerate(zip(tracks, ratings), start=1):
        y = tracklist_start_y + i * y_spacing
        category, fill_color = categorize_rating(rating)
        draw.rectangle([30, y, 530, y + y_spacing - 5], fill=fill_color, outline="black", width=3)
        draw.text((40, y), f"{i}. {track}", fill="black", font=track_font)
    
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

def main():
    st.title("Album Rating App")
    
    if 'ratings' not in st.session_state:
        st.session_state['ratings'] = []
    if 'tracks' not in st.session_state:
        st.session_state['tracks'] = []
    if 'album_cover' not in st.session_state:
        st.session_state['album_cover'] = None
    
    artist_name = st.text_input("Artist Name")
    album_name = st.text_input("Album Name")
    
    if st.button("Fetch Songs"):
        if artist_name and album_name:
            token = get_spotify_token()
            if token:
                tracks, album_cover = fetch_album_tracks(token, artist_name, album_name)
                if tracks:
                    st.session_state['tracks'] = tracks
                    st.session_state['album_cover'] = album_cover
                    st.session_state['ratings'] = [5.0 for _ in tracks]
                    st.success(f"Fetched {len(tracks)} songs successfully!")
                else:
                    st.error("Could not fetch songs. Please check the artist and album names.")
        else:
            st.error("Please fill in all fields.")
    
    if st.session_state['tracks']:
        st.write("## Rate Songs")
        for i, track in enumerate(st.session_state['tracks']):
            st.session_state['ratings'][i] = st.slider(
                f"Rate '{track}'", 0.0, 10.0, 5.0, 0.1, key=f"rating_{i}")
        
        if st.button("Generate Graphic"):
            graphic = create_graphic(st.session_state['album_cover'], album_name, artist_name, st.session_state['tracks'], st.session_state['ratings'])
            st.image(graphic, caption="Your Album Ratings", use_container_width=True)

if __name__ == "__main__":
    main()



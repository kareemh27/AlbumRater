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

    headers = {
        "Authorization": f"Basic {auth_base64}"
    }
    data = {"grant_type": "client_credentials"}

    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        error_message = response.json().get("error_description", "Unknown error")
        st.error(f"Authentication failed: {error_message}")
        return None

import re  # Import regex module for text cleaning

def clean_track_name(track_name):
    """Removes featured and with artists from track names without removing valid 'with' in titles."""
    track_name = re.sub(r"\(feat[^\)]+\)", "", track_name, flags=re.IGNORECASE)  # Remove (feat Artist)
    track_name = re.sub(r"\(with [^\)]+\)", "", track_name, flags=re.IGNORECASE)  # Remove (with Artist)
    track_name = re.sub(r"\[feat[^\]]+\]", "", track_name, flags=re.IGNORECASE)  # Remove [feat Artist]
    track_name = re.sub(r"\[with [^\]]+\]", "", track_name, flags=re.IGNORECASE)  # Remove [with Artist]
    track_name = re.sub(r"feat[^\)]+$", "", track_name, flags=re.IGNORECASE)     # Remove feat Artist at the end
    track_name = re.sub(r"with [^\)]+$", "", track_name, flags=re.IGNORECASE)     # Remove with Artist at the end
    return track_name.strip()

def fetch_album_tracks(token, artist_name, album_name):
    url = "https://api.spotify.com/v1/search"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    params = {
        "q": f"artist:{artist_name} album:{album_name}",
        "type": "album",
        "limit": 1
    }

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
                # Clean track names
                return [clean_track_name(track["name"]) for track in tracks_data["items"]], album_cover
    return [], None

    
# Define paths to the Arial font files
FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
FONT_PATH_REGULAR = os.path.join(FONT_DIR, "arial.ttf")
FONT_PATH_BOLD = os.path.join(FONT_DIR, "arialbd.ttf")

def get_font(size, bold=False):
    """Load font from the fonts directory, or fallback to a default."""
    font_path = FONT_PATH_BOLD if bold else FONT_PATH_REGULAR

    if os.path.exists(font_path):  # Check if the font file exists
        return ImageFont.truetype(font_path, size)
    else:
        print(f"⚠️ Font file not found: {font_path}, using default font.")
        return ImageFont.load_default()
        
def create_graphic(album_cover, album_name, artist_name, tracks, ratings):
    rating_colors = {
        "Amazing": "#32CD32",  # Green
        "Great": "#00BFFF",    # Blue
        "Good": "#FFD700",     # Yellow
        "Meh": "#FFA500",      # Orange
        "Bad": "#FF4500",      # Red
        "Skit": "#808080",     # Gray
    }

    rating_map = {
        10: "Amazing",
        8: "Great",
        6: "Good",
        4: "Meh",
        2: "Bad",
        0: "Skit",
    }

    # Load album cover and blur it
    response = requests.get(album_cover)
    album_image = Image.open(io.BytesIO(response.content)).resize((800, 800))
    blurred_background = album_image.filter(ImageFilter.GaussianBlur(20))

    # Create base image
    image = Image.new("RGB", (800, 800))
    image.paste(blurred_background, (0, 0))
    draw = ImageDraw.Draw(image)

    # Font styles
    title_font = get_font(36)
    track_font = get_font(20, bold=True)
    bold_font = get_font(24, bold=True)

    # Artist and Album Title
    draw.rectangle([30, 30, 530, 120], fill="#FFE4B5", outline="black", width=3)
    draw.text((40, 40), artist_name, fill="white", font=bold_font, stroke_width=2, stroke_fill="black")
    draw.rectangle([30, 125, 530, 165], fill="#FFFACD", outline="black", width=3)
    draw.text((40, 130), album_name, fill="black", font=bold_font)

    # Album cover with border
    album_thumbnail = album_image.resize((200, 200))
    image.paste(album_thumbnail, (550, 40))
    draw.rectangle([550, 40, 750, 240], outline="black", width=3)

    # Album Rating
    avg_rating = sum(ratings) / len(ratings) if ratings else 0
    draw.rectangle([550, 250, 750, 300], fill="#E6E6FA", outline="black", width=3)
    draw.text((560, 260), f"Rating: {round(avg_rating, 2)}/10", fill="black", font=bold_font)

    # Adjust box height and spacing based on track count
    tracklist_start_y = 170
    num_tracks = len(tracks)

    if num_tracks <= 10:
        box_height = 40
        spacing = 5
    elif num_tracks <= 24:
        box_height = 30
        spacing = 4
    elif num_tracks <= 30:
        box_height = 25
        spacing = 3
    else:
        total_space = 600  # Total vertical space for tracks
        box_height = max(total_space // num_tracks, 15)
        spacing = 2

    # Draw each track with adjusted box height and spacing
    for i, (track, rating) in enumerate(zip(tracks, ratings), start=1):
        y = tracklist_start_y + (i - 1) * (box_height + spacing)
        rating_label = rating_map[rating]
        fill_color = rating_colors[rating_label]
        draw.rectangle([30, y, 530, y + box_height], fill=fill_color, outline="black", width=3)
        draw.text((40, y + 5), f"{i}. {track}", fill="black", font=track_font)

    # Rating Key
    key_start_y = tracklist_start_y + (num_tracks * (box_height + spacing)) + 20
    for label, color in rating_colors.items():
        value = next((k for k, v in rating_map.items() if v == label), None)
        draw.rectangle([550, key_start_y, 750, key_start_y + 30], fill=color, outline="black", width=3)
        if value is not None:
            draw.text((560, key_start_y + 5), f"{label}: {value}", fill="black", font=bold_font)
        key_start_y += 40

    # Convert to streamlit compatible format
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
            with st.spinner("Authenticating with Spotify..."):
                token = get_spotify_token()
                if token:
                    with st.spinner("Fetching songs..."):
                        tracks, album_cover = fetch_album_tracks(token, artist_name, album_name)
                        if tracks:
                            st.session_state['tracks'] = tracks
                            st.session_state['album_cover'] = album_cover
                            st.session_state['ratings'] = [10 for _ in tracks]
                            st.success(f"Fetched {len(tracks)} songs successfully!")
                        else:
                            st.error("Could not fetch songs. Please check the artist and album names.")
        else:
            st.error("Please fill in all fields.")

    if st.session_state['tracks']:
        st.write("## Rate Songs")
        for i, track in enumerate(st.session_state['tracks']):
            st.session_state['ratings'][i] = st.selectbox(f"Rate '{track}'", [10, 8, 6, 4, 2, 0], key=f"rating_{i}")

        if st.button("Generate Graphic"):
            graphic = create_graphic(st.session_state['album_cover'], album_name, artist_name, st.session_state['tracks'], st.session_state['ratings'])
            st.image(graphic, caption="Your Album Ratings", use_container_width=True)

if __name__ == "__main__":
    main()




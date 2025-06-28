import streamlit as st
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io
import base64
import re
from pathlib import Path

# Font directory
FONT_DIR = Path("fonts")

def clean_track_name(name):
    # Remove (feat. ...), [feat. ...], (with ...), [with ...]
    return re.sub(r"[\(\[]\s*(feat\.|with)[^\)\]]*[\)\]]", "", name, flags=re.IGNORECASE).strip()

# Spotify credentials
CLIENT_ID = "58eac4fba0e84fd493f46d22bc12522c"
CLIENT_SECRET = "09eeeb1b3d034e23994761b959e1f876"

# Rating color system and label ranges
rating_colors = {
    "Amazing": "#32CD32",
    "Great": "#00BFFF",
    "Good": "#FFD700",
    "Meh": "#FFA500",
    "Bad": "#FF4500",
    "Skit": "#808080",
}

label_ranges = {
    "Amazing": "9–10",
    "Great": "7–9",
    "Good": "5–7",
    "Meh": "3–5",
    "Bad": "0–3",
    "Skit": "S"
}

def get_rating_label(value, is_skit=False):
    if is_skit:
        return "Skit"
    if value >= 9:
        return "Amazing"
    elif value >= 7:
        return "Great"
    elif value >= 5:
        return "Good"
    elif value >= 3:
        return "Meh"
    else:
        return "Bad"

def get_spotify_token():
    url = "https://accounts.spotify.com/api/token"
    auth_string = f"{CLIENT_ID}:{CLIENT_SECRET}"
    auth_base64 = base64.b64encode(auth_string.encode()).decode()

    headers = {"Authorization": f"Basic {auth_base64}"}
    data = {"grant_type": "client_credentials"}

    response = requests.post(url, headers=headers, data=data)
    if response.ok:
        return response.json().get("access_token")
    else:
        st.error("Spotify authentication failed.")
        return None

def fetch_album_tracks(token, artist_name, album_name):
    headers = {"Authorization": f"Bearer {token}"}

    # Step 1: Get artist ID
    search_artist = requests.get(
        "https://api.spotify.com/v1/search",
        headers=headers,
        params={"q": artist_name, "type": "artist", "limit": 1}
    )
    if not search_artist.ok or not search_artist.json()["artists"]["items"]:
        return [], None

    artist_id = search_artist.json()["artists"]["items"][0]["id"]

    # Step 2: Get all albums from artist
    albums = []
    seen_names = set()
    offset = 0
    while True:
        album_response = requests.get(
            f"https://api.spotify.com/v1/artists/{artist_id}/albums",
            headers=headers,
            params={"limit": 50, "offset": offset, "include_groups": "album"}
        )
        if not album_response.ok:
            break
        album_data = album_response.json()["items"]
        if not album_data:
            break
        for item in album_data:
            name = item["name"]
            if name.lower() not in seen_names:
                albums.append(item)
                seen_names.add(name.lower())
        if album_response.json().get("next") is None:
            break
        offset += 50

    # Step 3: Match the album name
    album_match = None
    album_name_lower = album_name.lower().strip()
    for album in albums:
        if album["name"].lower().strip() == album_name_lower:
            album_match = album
            break

    # Step 4: If no exact match, fallback to fuzzy match
    if not album_match:
        for album in albums:
            if album_name_lower in album["name"].lower():
                album_match = album
                break

    if not album_match:
        return [], None

    album_id = album_match["id"]
    album_cover = album_match["images"][0]["url"]

    # Step 5: Paginate track fetch
    tracks = []
    offset = 0
    limit = 50
    while True:
        track_response = requests.get(
            f"https://api.spotify.com/v1/albums/{album_id}/tracks",
            headers=headers,
            params={"limit": limit, "offset": offset}
        )
        if not track_response.ok:
            break
        data = track_response.json()
        items = data.get("items", [])
        if not items:
            break
        tracks.extend([clean_track_name(t["name"]) for t in items])
        if data.get("next") is None:
            break
        offset += limit

    return tracks, album_cover


def fetch_artist_albums(token, artist_name):
    url = "https://api.spotify.com/v1/search"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "q": artist_name,
        "type": "artist",
        "limit": 1
    }
    response = requests.get(url, headers=headers, params=params)

    if response.ok and response.json()["artists"]["items"]:
        artist_id = response.json()["artists"]["items"][0]["id"]
        albums_url = f"https://api.spotify.com/v1/artists/{artist_id}/albums"
        albums_response = requests.get(albums_url, headers=headers, params={"limit": 50, "include_groups": "album"})
        if albums_response.ok:
            seen = set()
            albums = []
            for item in albums_response.json()["items"]:
                name = item["name"]
                if name not in seen:
                    seen.add(name)
                    albums.append(name)
            return sorted(albums)
    return []


def create_graphic(album_cover, album_name, artist_name, tracks, ratings):
    response = requests.get(album_cover)
    album_image = Image.open(io.BytesIO(response.content)).resize((800, 800))
    blurred = album_image.filter(ImageFilter.GaussianBlur(20))

    image = Image.new("RGB", (800, 800))
    image.paste(blurred)
    draw = ImageDraw.Draw(image)

    def load_font(font_filename, size):
        try:
            return ImageFont.truetype(str(FONT_DIR / font_filename), size)
        except IOError:
            return ImageFont.load_default()
    
    artist_font = load_font("arialbd.ttf", 38)   # Bold
    album_font = load_font("ariali.ttf", 30)     # Italic
    rating_font = load_font("arial.ttf", 22)
    
    track_count = len(tracks)
    track_font_size = 15 if track_count >= 25 else 18
    track_font = load_font("arialbd.ttf", track_font_size)
    
    key_font = load_font("arialbd.ttf", 22)

    lavender = "#E6E6FA"
    text_color = "black"

    def draw_centered_text(draw_obj, box, text, font, fill):
        bbox = draw_obj.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = box[0] + (box[2] - box[0] - text_width) / 2
        y = box[1] + (box[3] - box[1] - text_height) / 2
        draw_obj.text((x, y), text, font=font, fill=fill)

    # Header blocks
    artist_box = [30, 30, 530, 100]
    album_box = [30, 105, 530, 165]
    rating_box = [550, 250, 750, 300]

    draw.rectangle(artist_box, fill=lavender, outline="black", width=3)
    draw.rectangle(album_box, fill=lavender, outline="black", width=3)
    draw.rectangle(rating_box, fill=lavender, outline="black", width=3)

    draw_centered_text(draw, artist_box, artist_name, artist_font, text_color)
    draw_centered_text(draw, album_box, album_name, album_font, text_color)

    # Album art
    thumbnail = album_image.resize((200, 200))
    image.paste(thumbnail, (550, 40))
    draw.rectangle([550, 40, 750, 240], outline="black", width=3)

    # Rating
    valid_ratings = [r for i, r in enumerate(ratings) if not st.session_state.get(f"skit_{i}", False)]
    avg_rating = round(sum(valid_ratings) / len(valid_ratings), 2) if valid_ratings else 0
    draw_centered_text(draw, rating_box, f"Rating: {avg_rating}/10", key_font, text_color)

    # Tracks
    track_start_y = 180
    max_track_area = 600
    bottom_padding = 40
    
    max_drawable_height = 800 - track_start_y - bottom_padding
    y_spacing = max(min(max_drawable_height // max(len(tracks), 1), 40), 20)
    
    for i, (track, rating) in enumerate(zip(tracks, ratings)):
        y = track_start_y + i * y_spacing
        is_skit = st.session_state.get(f"skit_{i}", False)
        label = get_rating_label(rating, is_skit)
        color = rating_colors[label]
        draw.rectangle([30, y, 530, y + y_spacing - 5], fill=color, outline="black", width=2)
        draw.text((40, y), f"{i + 1}. {track}", fill="black", font=track_font)

    # Rating Key
    key_y = 310
    for label in rating_colors:
        box = [550, key_y, 750, key_y + 30]
        draw.rectangle(box, fill=rating_colors[label], outline="black", width=2)
        text = f"{label}: {label_ranges[label]}"
        draw_centered_text(draw, box, text, key_font, "black")
        key_y += 40

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def main():
    st.set_page_config(page_title="Album Rating App", layout="wide")
    st.title("🎵 Album Rating Generator")

    with st.sidebar:
        st.header("Enter Album Info")
    
        artist_name = st.text_input("Artist Name")
        album_name = None
        fetch = False  # Initialize here
    
        if artist_name:
            if 'token' not in st.session_state:
                st.session_state['token'] = get_spotify_token()
    
            token = st.session_state['token']
            if token:
                albums = fetch_artist_albums(token, artist_name)
                if albums:
                    album_name = st.selectbox("Select an Album", albums)
                    fetch = st.button("Fetch Songs")
                else:
                    st.warning("No albums found for that artist.")
            else:
                st.error("Spotify authentication failed.")

    if fetch:
        if artist_name and album_name:
            token = get_spotify_token()
            if token:
                tracks, cover = fetch_album_tracks(token, artist_name, album_name)
                if tracks:
                    st.session_state['tracks'] = tracks
                    st.session_state['album_cover'] = cover
                    st.session_state['ratings'] = [10.0] * len(tracks)
                    st.success(f"Loaded {len(tracks)} tracks!")
                else:
                    st.error("No album found.")
        else:
            st.warning("Please provide both artist and album name.")

    if 'tracks' in st.session_state and st.session_state['tracks']:
        st.subheader("Rate Each Track")

        for i, track in enumerate(st.session_state['tracks']):
            cols = st.columns([4, 1])
            with cols[0]:
                st.session_state['ratings'][i] = st.slider(
                    label=track, min_value=0.0, max_value=10.0, step=0.5,
                    value=st.session_state['ratings'][i], key=f"rating_slider_{i}")
            with cols[1]:
                st.checkbox("Skit", key=f"skit_{i}")

        if st.button("🎨 Generate Rating Graphic"):
            image_buffer = create_graphic(
                st.session_state['album_cover'],
                album_name,
                artist_name,
                st.session_state['tracks'],
                st.session_state['ratings']
            )
            st.image(image_buffer, caption="Album Ratings", use_container_width=True)
            st.download_button("📥 Download Image", data=image_buffer, file_name="album_ratings.png", mime="image/png")

if __name__ == "__main__":
    main()



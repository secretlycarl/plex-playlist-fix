import os
import json
import logging
import csv
import sys
import string
import unidecode
from typing import List
from typing import Dict
from difflib import SequenceMatcher

import plexapi
from plexapi.server import PlexServer
from plexapi.exceptions import BadRequest, NotFound

from helperClasses import Playlist, UserInputs

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

def load_config():
    try:
        config_file_path = "/app/config.json"  # Full path to config.json within the container
        with open(config_file_path, "r") as config_file:
            config = json.load(config_file)
        return config
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading config.json: {e}")
        exit(1)

def prompt_plex_libraries(plex: PlexServer) -> PlexServer:
    """Prompt user to select Plex library before proceeding."""
    libraries = plex.library.sections()
    print("Available Plex Libraries:")
    for idx, library in enumerate(libraries, start=1):
        print(f"{idx}. {library.title}")

    choice = UserInputs.input("Enter the number of the correct library: ")
    if choice.isdigit() and 1 <= int(choice) <= len(libraries):
        library = libraries[int(choice) - 1]
        print(f"You selected library: {library.title}")
        confirmation = UserInputs.input("Continue with this library (y/N)? ")
        if confirmation.lower() != 'y':
            print("Aborting...")
            exit(0)
        else:
            return library
    else:
        print("Invalid choice. Aborting...")
        exit(0)

def _get_available_plex_tracks(plex: PlexServer, songs: List[Dict[str, str]], playlist_name: str) -> List:
    plex_tracks, missing_tracks, found_tracks = [], [], []
    current_playlist_songs = get_current_playlist_songs(plex, playlist_name)
    for song in songs:
        sanitized_artist = sanitize_string(song['artist'])
        track_string = f"{sanitized_artist} - {song['title']}"
        if track_string in current_playlist_songs:
            continue
        search = []
        try:
            # Search for the artist first
            artist_results = plex.library.section('Music').search(title=sanitized_artist, libtype='artist')
            logging.info(f"Searching for artist: {sanitized_artist}")
            if artist_results:
                # Search for the track within the artist's tracks using get_best_matching_track
                best_match = get_best_matching_track(song['title'], artist_results[0].tracks())
                if best_match:
                    found_tracks.append(song)  # Add the song to the found_tracks list
                    plex_tracks.append(best_match)  # Store the matching Plex Track object
                    logging.info(f"Found track: {track_string}")
                else:
                    logging.info(f"Track not found: {track_string}")
                    missing_tracks.append(song)
            else:
                logging.info(f"Artist not found: {sanitized_artist}")
                missing_tracks.append(song)
        except BadRequest:
            logging.info("Failed to search %s by %s on Plex", song['title'], sanitized_artist)
            missing_tracks.append(song)
            continue

    return plex_tracks, missing_tracks, found_tracks  # Return the found_tracks list
    
def read_csv_files(csv_directory):
    playlist_data = {}
    
    if not os.path.exists(csv_directory):
        raise FileNotFoundError(f"Directory not found: {csv_directory}")
    
    if not os.listdir(csv_directory):
        print(f"CSV directory '{csv_directory}' is empty.")
        return playlist_data
    
    for file_name in os.listdir(csv_directory):
        if file_name.endswith(".csv"):
            playlist_name = os.path.splitext(file_name)[0]
            with open(os.path.join(csv_directory, file_name), "r", newline='') as csv_file:
                csv_reader = csv.DictReader(csv_file)
                songs = [{ 'title': row['title'], 'artist': row['artist'] } for row in csv_reader]
                playlist_data[playlist_name] = songs
                logging.info(f"Read {len(songs)} songs from {file_name}:")
                for song in songs:
                    logging.info(f"  {song}")
    
    return playlist_data

def fetch_playlist(plex, playlist_name, playlist_type='audio'):
    try:
        playlists = plex.playlists()
        for playlist in playlists:
            if playlist.title == playlist_name and playlist.playlistType == playlist_type:
                return playlist
        return None
    except NotFound:
        logging.info(f"Playlist {playlist_name} not found.")
        return None

def get_current_playlist_songs(plex, playlist_name):
    playlist = fetch_playlist(plex, playlist_name)
    if not playlist:
        logging.error(f"Playlist {playlist_name} does not exist.")
        return []
    return [f"{item.artist().title} - {item.title}" for item in playlist.items()]

def get_best_matching_track(title: str, plex_tracks: List) -> dict:
    best_match = None
    highest_ratio = 0

    for plex_track in plex_tracks:
        sanitized_title = sanitize_string(plex_track.title)
        ratio = SequenceMatcher(None, title, sanitized_title).ratio()
        ### delete hashes for more logging info
        ### logging.info(f"Matching {title} with {sanitized_title}, ratio: {ratio}")
        if ratio > highest_ratio:
            highest_ratio = ratio
            best_match = plex_track

    return best_match

def sanitize_string(input_string: str) -> str:
    # Create a translation table mapping every punctuation character to None, except for periods
    translator = str.maketrans('', '', string.punctuation.replace(".", ""))

    # Use the table to remove all punctuation from the input_string
    sanitized_string = input_string.translate(translator)

    # Remove question marks
    sanitized_string = sanitized_string.replace("?", "")
    sanitized_string = sanitized_string.replace("¿", "")

    # Convert accented letters to their unaccented versions
    sanitized_string = unidecode.unidecode(sanitized_string)

    return sanitized_string

def add_tracks_to_playlist(plex, playlist_name, tracks):
    playlist = fetch_playlist(plex, playlist_name)
    if not playlist:
        logging.error(f"Playlist {playlist_name} does not exist.")
        return

    if not tracks:
        logging.info("No tracks to add.")
        return

    # Get current playlist tracks
    current_playlist_tracks = [f"{item.artist().title} - {item.title}" for item in playlist.items()]

    # Filter out tracks that are already in the playlist
    tracks_to_add = [track for track in tracks if f"{track['artist']} - {track['title']}" not in current_playlist_tracks]

    # Fetch Track objects from Plex
    track_objects = []
    for track in tracks_to_add:
        sanitized_artist = sanitize_string(track['artist'])
        artist_results = plex.library.section('Music').searchArtists(title=sanitized_artist)
        if artist_results:
            artist_tracks = artist_results[0].tracks()
            best_match = get_best_matching_track(track['title'], artist_tracks)
            if best_match:
                track_objects.append(best_match)
            else:
                logging.error(f"Track {track['title']} by {track['artist']} not found in Plex library.")
        else:
            logging.error(f"Artist {sanitized_artist} not found. {track['title']} by {track['artist']} not added.")
    try:
        playlist.addItems(track_objects)
        logging.info(f"Successfully added {len(track_objects)} tracks to playlist.")
        return len(track_objects)  # Return the number of successfully added tracks
    except Exception as e:
        logging.error(f"Failed to add tracks to playlist: {e}")
        return 0  # Return 0 if no tracks were added due to an error

def confirm_and_add_tracks(plex, playlist_name, missing_tracks, found_tracks, csv_directory):
    playlist = fetch_playlist(plex, playlist_name)
    if not playlist:
        logging.error(f"Playlist {playlist_name} does not exist and will not be created.")
        return

    tracks_to_add = found_tracks  # Use the found_tracks list when creating tracks_to_add

    if tracks_to_add:
        confirmation = UserInputs.input(f"Add {len(tracks_to_add)} tracks to playlist (y/N)? ")
        if confirmation.lower() == 'y':
            num_added_tracks = add_tracks_to_playlist(plex, playlist_name, tracks_to_add)  # Get the number of added tracks
            logging.info(f"Added {num_added_tracks} tracks to the playlist {playlist_name}.")  # Log the number of added tracks

            # Remove successfully added tracks from CSV
            csv_file_path = os.path.join(csv_directory, f"{playlist_name}.csv")
            with open(csv_file_path, "r") as csv_file:
                csv_reader = csv.DictReader(csv_file)
                remaining_tracks = [row for row in csv_reader if {'title': row['title'], 'artist': row['artist']} not in tracks_to_add]

            # Write remaining tracks back to CSV
            with open(csv_file_path, "w", newline='') as csv_file:
                fieldnames = ['title', 'artist']
                csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                csv_writer.writeheader()
                # Only consider 'title' and 'artist' fields for each track
                remaining_tracks_filtered = [{'title': track['title'], 'artist': track['artist']} for track in remaining_tracks]
                csv_writer.writerows(remaining_tracks_filtered)
        else:
            logging.info("No new tracks were added.")

def main():
    config = load_config()
    csv_directory = config.get("directories", {}).get("csv")
    plex_api = config.get("plex_api")
    plex_url = plex_api.get("base_url")
    plex_token = plex_api.get("token")

    plex = PlexServer(plex_url, plex_token)
    selected_library = prompt_plex_libraries(plex)
    playlist_data = read_csv_files(csv_directory)

    if playlist_data:
        for playlist_name, songs in playlist_data.items():
            confirmation = UserInputs.input(f"Do you want to process the CSV for playlist {playlist_name} (y/N)? ")
            if confirmation.lower() != 'y':
                logging.info(f"Skipping CSV for playlist {playlist_name}.")
                continue
            logging.info(f"Processing playlist: {playlist_name}")
            available_tracks, missing_tracks, found_tracks = _get_available_plex_tracks(plex, songs, playlist_name)
            confirm_and_add_tracks(plex, playlist_name, missing_tracks, found_tracks, csv_directory)

    print("All CSVs processed.")

if __name__ == "__main__":
    main()

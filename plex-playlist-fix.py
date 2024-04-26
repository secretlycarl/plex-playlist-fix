import os
import json
import logging
import csv
import sys
from typing import List
from difflib import SequenceMatcher

import plexapi
from plexapi.server import PlexServer
from plexapi.exceptions import BadRequest, NotFound

from helperClasses import Playlist, Track, UserInputs

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

def prompt_plex_libraries(plex: PlexServer) -> None:
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
        print("Invalid choice. Aborting...")
        exit(0)

def _get_available_plex_tracks(plex: PlexServer, tracks: List[Track]) -> List:
    plex_tracks, missing_tracks = [], []
    for track in tracks:
        search = []
        try:
            search = plex.search(f"{track.title} {track.artist}", mediatype="track", limit=5)
            if not search:
                search = plex.search(track.title, mediatype="track", limit=5)
        except BadRequest:
            logging.info("Failed to search %s by %s on Plex", track.title, track.artist)
            missing_tracks.append(track)
            continue

        found = False
        for s in search:
            artist_similarity = SequenceMatcher(None, s.artist().title.lower(), track.artist.lower()).quick_ratio()
            if artist_similarity >= 0.9:
                confirmation = UserInputs.input(f"Found {s.title} by {s.artist().title} for {track.title} by {track.artist}, is this correct? (y/N): ")
                if confirmation.lower() == 'y':
                    plex_tracks.append(s)
                    found = True
                    break

        if not found:
            missing_tracks.append(track)

    return plex_tracks, missing_tracks
    
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
                playlist_data[playlist_name] = [row for row in csv_reader]
    
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

def add_tracks_to_playlist(plex, playlist, tracks):
    if not tracks:
        logging.info("No tracks to add.")
        return
    uris = [track.uri for track in tracks if track.uri]
    for uri in uris:
        try:
            playlist.addItems([uri], playQueueID=playlist.playQueueID)
            logging.info(f"Successfully added track with URI {uri} to playlist.")
        except Exception as e:
            logging.error(f"Failed to add track with URI {uri} to playlist: {e}")

def confirm_and_add_tracks(plex, playlist_name, missing_tracks):
    playlist = fetch_playlist(plex, playlist_name)
    if not playlist:
        logging.error(f"Playlist {playlist_name} does not exist and will not be created.")
        return

    tracks_to_add = []
    for track in missing_tracks:
        confirmation = UserInputs.input(f"Add track {track.title} by {track.artist} to playlist (y/N)? ")
        if confirmation.lower() == 'y':
            tracks_to_add.append(track)

    if tracks_to_add:
        add_tracks_to_playlist(plex, playlist, tracks_to_add)
        logging.info(f"Added {len(tracks_to_add)} tracks to the playlist {playlist_name}.")
    else:
        logging.info("No new tracks were added.")

def main():
    config = load_config()
    csv_directory = config.get("directories", {}).get("csv")
    plex_api = config.get("plex_api")
    plex_url = plex_api.get("base_url")
    plex_token = plex_api.get("token")

    plex = PlexServer(plex_url, plex_token)
    prompt_plex_libraries(plex)  # Ensure this is called to select the library
    playlist_data = read_csv_files(csv_directory)

    if playlist_data:
        for playlist_name, songs in playlist_data.items():
            logging.info(f"Processing playlist: {playlist_name}")
            tracks = [Track(title=song['title'], artist=song['artist']) for song in songs]
            available_tracks, missing_tracks = _get_available_plex_tracks(plex, tracks)
            confirm_and_add_tracks(plex, playlist_name, missing_tracks)

if __name__ == "__main__":
    main()

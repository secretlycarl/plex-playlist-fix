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
    """Search and return list of tracks available in Plex."""
    plex_tracks, missing_tracks = [], []
    for track in tracks:
        search = []
        try:
            search = plex.search(track.title, mediatype="track", limit=5)
        except BadRequest:
            logging.info("Failed to search %s on Plex", track.title)
        if not search or len(track.title.split("(")) > 1:
            logging.info("Retrying search for %s", track.title)
            try:
                search += plex.search(
                    track.title.split("(")[0], mediatype="track", limit=5
                )
                logging.info("Search for %s successful", track.title)
            except BadRequest:
                logging.info("Unable to query %s on Plex", track.title)

        found = False
        if search:
            for s in search:
                artist_similarity = SequenceMatcher(
                    None, s.artist().title.lower(), track.artist.lower()
                ).quick_ratio()

                if artist_similarity >= 0.9:
                    plex_tracks.append(s)
                    found = True
                    break

        if not found:
            missing_tracks.append(track)

    return plex_tracks, missing_tracks

def read_csv_files(csv_directory):
    """Read CSV files from specified directory."""
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

def get_playlist_by_name(plex: PlexServer, playlist_name: str):
    playlists = plex.playlists()
    for playlist in playlists:
        if playlist.title == playlist_name:
            return playlist
    return None

def _update_plex_playlist(plex: PlexServer, available_tracks: List, playlist_name: str) -> None:
    """Update existing Plex playlist by adding new tracks, with user confirmation."""
    try:
        plex_playlist = plex.playlist(playlist_name)
        logging.info(f"Playlist {playlist_name} found.")
    except NotFound:
        logging.error(f"Playlist {playlist_name} not found. No updates made.")
        return

    current_track_ids = {item.ratingKey for item in plex_playlist.items()}
    logging.info(f"Current track IDs in playlist: {current_track_ids}")
    tracks_to_add = []

    for track in available_tracks:
        if track.ratingKey not in current_track_ids:
            logging.info(f"Track {track.title} by {track.artist} is not in the playlist, prompting for addition.")
            user_confirm = input(f"Add '{track.title}' by '{track.artist}' to playlist '{playlist_name}'? (y/N): ")
            if user_confirm.lower() == 'y':
                tracks_to_add.append(track)
                logging.info(f"Track {track.title} approved by user for addition.")
            else:
                logging.info(f"User declined to add track {track.title}.")
        else:
            logging.info(f"Track {track.title} by {track.artist} already in playlist.")

    if tracks_to_add:
        plex_playlist.addItems(tracks_to_add)
        logging.info(f"Added {len(tracks_to_add)} new tracks to playlist {playlist_name}.")
    else:
        logging.info(f"No new tracks were added to playlist {playlist_name}.")

def main():
    config = load_config()
    csv_directory = config.get("directories", {}).get("csv")
    print(f"CSV Directory: {csv_directory}")

    plex_api = config.get("plex_api")
    plex_url = plex_api.get("base_url")
    plex_token = plex_api.get("token")

    try:
        plex = PlexServer(plex_url, plex_token)
        prompt_plex_libraries(plex)
    except Exception as e:
        logging.error(f"Error connecting to Plex server: {e}")
        return

    playlist_data = read_csv_files(csv_directory)

    if playlist_data:
        for playlist_name, songs in playlist_data.items():
            logging.info(f"Processing playlist: {playlist_name}")
            tracks = [Track(title=song['title'], artist=song['artist']) for song in songs]

            available_tracks, missing_tracks = _get_available_plex_tracks(plex, tracks)
            if available_tracks:
                _update_plex_playlist(plex, available_tracks, playlist_name, append=True)  # Set append based on your needs
            else:
                logging.info(f"No new tracks were added to the playlist {playlist_name}.")

            if missing_tracks:
                print(f"Missing tracks for playlist {playlist_name}:")
                for track in missing_tracks:
                    print(f"{track.title} by {track.artist}")

if __name__ == "__main__":
    main()

import os
import json
import csv
import logging
import pathlib
import sys
from typing import List
from plexapi.server import PlexServer
from plexapi.exceptions import BadRequest, NotFound
from difflib import SequenceMatcher
from helperClasses import Playlist, Track, UserInputs

logging.basicConfig(level=logging.INFO)

MUSIC_DIR = ""  # Define the music directory

def load_config():
    try:
        config_file_path = "/app/config.json"  # Full path to config.json within the container
        with open(config_file_path, "r") as config_file:
            config = json.load(config_file)
        return config
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading config.json: {e}")
        exit(1)

def _get_available_plex_tracks(plex: PlexServer, tracks: List[Track]) -> List:
    """Search and return list of tracks available in Plex.

    Args:
        plex (PlexServer): A configured PlexServer instance
        tracks (List[Track]): list of track objects

    Returns:
        List: of plex track objects
    """
    plex_tracks = []
    for track in tracks:
        try:
            search = plex.search(track.title, mediatype="track", limit=5)
        except BadRequest:
            logging.info("Failed to search %s on Plex", track.title)
            continue

        if search:
            for s in search:
                plex_tracks.append(s)

    return plex_tracks

def _update_plex_playlist(plex: PlexServer, available_tracks: List, playlist_name: str) -> None:
    """Update existing Plex playlist with new tracks and metadata.

    Args:
        plex (PlexServer): A configured PlexServer instance
        available_tracks (List): list of plex track objects
        playlist_name (str): Name of the playlist to update
    """
    playlist = plex.playlist(playlist_name)
    if playlist:
        try:
            playlist.addItems(available_tracks)
            logging.info("Updated Plex playlist '%s' with new tracks", playlist_name)
        except Exception as e:
            logging.error("Error updating Plex playlist: %s", e)
    else:
        logging.error("Playlist '%s' not found on Plex server", playlist_name)

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

def search_local_music(search_term):
    matched_files = []
    for root, dirs, files in os.walk(MUSIC_DIR):
        for file in files:
            file_name = os.path.splitext(file)[0]
            if search_term.lower() in file_name.lower():
                matched_files.append(os.path.join(root, file))
    return matched_files

def add_song_to_plex(plex_server, playlist_name, song_path):
    playlist = plex_server.playlist(playlist_name)
    if playlist:
        try:
            abs_song_path = os.path.join(MUSIC_DIR, song_path)
            media_results = plex_server.search(abs_song_path)
            if media_results:
                playlist.addItems([media_results[0]])
                print(f"Song added to Plex playlist '{playlist_name}' successfully.")
            else:
                print(f"Error: Media not found in Plex library for '{abs_song_path}'")
        except Exception as e:
            logging.error(f"Error communicating with Plex server: {e}")
    else:
        print(f"Playlist '{playlist_name}' not found on Plex server.")

def main():
    config = load_config()
    csv_directory = config.get("directories", {}).get("csv")
    print(f"CSV Directory: {csv_directory}")

    csv_directory = csv_directory.replace("\\", "/")

    plex_api = config.get("plex_api")
    plex_url = plex_api.get("base_url")
    plex_token = plex_api.get("token")

    directories = config.get("directories")
    global MUSIC_DIR
    MUSIC_DIR = directories.get("music")

    plex = PlexServer(plex_url, plex_token)

    playlist_data = read_csv_files(csv_directory)

    if playlist_data:
        for playlist_name, songs in playlist_data.items():
            logging.info(f"Processing playlist: {playlist_name}")
            
            tracks = [Track(**entry) for entry in songs]
            available_tracks = _get_available_plex_tracks(plex, tracks)
            
            if available_tracks:
                for entry in songs:
                    artist = entry.get("artist")
                    title = entry.get("title")

                    search_term = f"{artist} - {title}"
                    matched_files = search_local_music(search_term)

                    if matched_files:
                        print(f"Found {len(matched_files)} match(es) for '{artist} - {title}' in '{playlist_name}':")
                        for idx, file_path in enumerate(matched_files, start=1):
                            print(f"{idx}. {os.path.basename(file_path)}")
                        
                        choice = UserInputs.input("Enter the number of the correct file or 'n' to skip: ")
                        if choice.isdigit() and 1 <= int(choice) <= len(matched_files):
                            confirmation = UserInputs.input(f"Confirm adding '{matched_files[int(choice) - 1]}' to playlist '{playlist_name}' (y/N)? ")
                            
                            if confirmation.lower() == 'y':
                                try:
                                    add_song_to_plex(plex, playlist_name, matched_files[int(choice) - 1])
                                except Exception as e:
                                    logging.error(f"Error adding song to Plex: {e}")
                            else:
                                print("Skipping...")
                        else:
                            print("Skipped.")
                    else:
                        print(f"No matching files found for '{artist} - {title}' in '{playlist_name}'.")
                    
                _update_plex_playlist(plex, available_tracks, playlist_name)
            else:
                logging.info(f"No tracks found on Plex for playlist: {playlist_name}")

if __name__ == "__main__":
    main()

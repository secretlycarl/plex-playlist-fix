from dataclasses import dataclass

@dataclass
class Track:
    title: str
    artist: str
    album: str
    url: str

@dataclass
class Playlist:
    id: str
    name: str
    description: str
    poster: str

@dataclass
class UserInputs:
    plex_url: str
    plex_token: str

    @staticmethod
    def input(message):
        return input(message)

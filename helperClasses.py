from dataclasses import dataclass

@dataclass
class Track:
  """Holds information about a music track."""
  title: str
  artist: str

@dataclass
class Playlist:
  """Holds information about a Plex playlist."""
  id: str  # This attribute might not be used depending on your implementation
  name: str  # Use 'name' instead of 'title' for consistency with Plex

@dataclass
class UserInputs:
  """Provides methods for user input."""
  plex_url: str
  plex_token: str

  @staticmethod
  def input(message):
    """Prompts the user for input with the given message."""
    return input(message)

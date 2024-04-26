# plex-playlist-fix
companion for [plex-playlist-sync](https://github.com/rnagabhyrava/plex-playlist-sync) that adds missing songs to plex playlists

CURRENTLY A WORK IN PROGRESS, NOT YET WORKING COMPLETELY

This script is meant to be used in conjunction with plex-playlist-sync in Docker. It's probably possible to combine them into one but I don't have the skills for that. This script will read through the CSV files of missing songs generated by plex-playlist-sync (or any csv with title, artist etc, though the code would have to be changed), search for matching songs in your plex library, and then add them to the appropriate Plex playlist.

It is almost complete but I'm struggling to configure the Plex stuff so it adds the songs. It can parse the CSV and match them to songs in plex but then it stops. 

Need to fix the final few steps (prompting user to confirm matches,  adding to a playlist, then going on to scan the next CSV)

The current output looks like this:
```
CSV Directory: /app/csv
Available Plex Libraries:
1. Music
2. Shows
3. Music
Enter the number of the correct library: 3
You selected library: Music
Continue with this library (y/N)? y
INFO:root:Processing playlist: test1
INFO:root:Retrying search for [song title]
INFO:root:Search for [song title] successful
[repeats for all songs]
INFO:root:No new tracks were added to the playlist test1.
[List of song titles]
PS C:\Users\user\Documents\plex-playlist-fix>

```

# Usage

Set up the config file with your Plex info

Set up the run command to mount the folder with CSVs from plex-playlist-sync

Build the docker image

Run the docker run command

I combined the build & run commands in the file but they can be split

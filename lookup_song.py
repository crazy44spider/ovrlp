
import os
import requests
from dotenv import load_dotenv

# Load our API key from the .env file
load_dotenv()
api_key = os.getenv("GETSONGBPM_KEY")

# GetSongBPM API endpoint
url = "https://api.getsong.co/search/"


# Search for a song using its title and artist
def search_song(song_name, artist_name):
    params = {
        "type": "both",
        "lookup": f"song:{song_name} artist:{artist_name}"
    }

    # Send a request to the API
    try:
        response = requests.get(
            url,
            headers={"X-API-KEY": api_key},
            params=params,
            timeout=15
        )

        # Check whether we've been rate-limited
        if response.status_code == 429:
            print("GetSongBPM is rate-limiting requests.")
            print("Try again later.")
            return None

        # Check for other HTTP errors
        response.raise_for_status()

        # Convert the response into Python data
        data = response.json()

        # Return the first matching song
        if data.get("search"):
            return data["search"][0]

        return None

    except requests.exceptions.RequestException as error:
        print("API request failed:", error)
        return None


# Ask for the first song
print("FIRST SONG")
name1 = input("Enter a song: ")
artist1 = input("Enter an artist: ")

# Ask for the second song
print("\nSECOND SONG")
name2 = input("Enter a song: ")
artist2 = input("Enter an artist: ")

# Search for both songs
song1 = search_song(name1, artist1)
song2 = search_song(name2, artist2)

# Display both songs
if song1 and song2:
    print("\n--- OvrLP Comparison ---")

    print("Song 1:", song1["title"])
    print("Artist:", song1["artist"]["name"])
    print("BPM:", song1["tempo"])
    print("Key:", song1["key_of"])

    print()

    print("Song 2:", song2["title"])
    print("Artist:", song2["artist"]["name"])
    print("BPM:", song2["tempo"])
    print("Key:", song2["key_of"])

else:
    print("\nCould not retrieve both songs.")

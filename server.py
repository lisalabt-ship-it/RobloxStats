from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import urlopen
import json
import os

UNIVERSE_ID = "10768969887"


class Handler(SimpleHTTPRequestHandler):

    def do_GET(self):

        if self.path == "/api/stats":

            try:
                # Informations du jeu
                game_url = (
                    "https://games.roblox.com/v1/games"
                    "?universeIds=" + UNIVERSE_ID
                )

                with urlopen(game_url, timeout=10) as response:
                    game_data = json.loads(
                        response.read().decode("utf-8")
                    )

                # Likes / dislikes
                votes_url = (
                    "https://games.roblox.com/v1/games/votes"
                    "?universeIds=" + UNIVERSE_ID
                )

                with urlopen(votes_url, timeout=10) as response:
                    votes_data = json.loads(
                        response.read().decode("utf-8")
                    )

                game = game_data["data"][0]
                votes = votes_data["data"][0]

                result = {
                    "playing": game["playing"],
                    "visits": game["visits"],
                    "favorites": game["favoritedCount"],
                    "likes": votes["upVotes"],
                    "dislikes": votes["downVotes"]
                }

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()

                self.wfile.write(
                    json.dumps(result).encode("utf-8")
                )

            except Exception as e:

                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()

                self.wfile.write(
                    json.dumps({
                        "error": str(e)
                    }).encode("utf-8")
                )

        else:
            super().do_GET()


# Render fournit automatiquement le port
PORT = int(os.environ.get("PORT", 8000))

server = ThreadingHTTPServer(
    ("0.0.0.0", PORT),
    Handler
)

print(f"Site lancé sur le port {PORT}")

server.serve_forever()
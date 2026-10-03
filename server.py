from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import urlopen, Request
from urllib.error import HTTPError
import json
import os
from datetime import datetime, timedelta, timezone
import time

UNIVERSE_ID = "10768969887"
ROBLOX_API_KEY = os.environ.get("ROBLOX_API_KEY")

ANALYTICS_URL = (
    "https://apis.roblox.com/analytics-query-api/v1/"
    f"universes/{UNIVERSE_ID}/metrics"
)


def recuperer_revenu():
    if not ROBLOX_API_KEY:
        raise Exception("ROBLOX_API_KEY n'est pas configurée dans Render.")

    maintenant = datetime.now(timezone.utc)

    # On demande les 30 derniers jours
    debut = maintenant - timedelta(days=30)

    payload = {
        "metric": "DailyRevenue",
        "granularity": "OneDay",
        "startTime": debut.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endTime": maintenant.strftime("%Y-%m-%dT%H:%M:%SZ")
    }

    request = Request(
        ANALYTICS_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-api-key": ROBLOX_API_KEY,
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urlopen(request, timeout=20) as response:
            status = response.status
            data = json.loads(response.read().decode("utf-8"))

    except HTTPError as e:
        erreur = e.read().decode("utf-8", errors="replace")
        raise Exception(f"Roblox API {e.code}: {erreur}")

    # Roblox peut renvoyer 202 pour une requête longue
    if status == 202 or data.get("done") is False:
        path = data.get("path")

        if not path:
            raise Exception("Roblox n'a pas fourni de chemin de résultat.")

        if path.startswith("http"):
            result_url = path
        else:
            result_url = (
                "https://apis.roblox.com/analytics-query-api/"
                + path.lstrip("/")
            )

        for _ in range(20):
            poll_request = Request(
                result_url,
                headers={
                    "x-api-key": ROBLOX_API_KEY
                },
                method="GET"
            )

            try:
                with urlopen(poll_request, timeout=20) as response:
                    result = json.loads(
                        response.read().decode("utf-8")
                    )
            except HTTPError as e:
                erreur = e.read().decode("utf-8", errors="replace")
                raise Exception(
                    f"Roblox API {e.code}: {erreur}"
                )

            if result.get("done") is True:
                data = result
                break

            time.sleep(2)

        else:
            raise Exception(
                "La requête Roblox prend trop de temps."
            )

    # Récupération des points
    values = data.get("response", {}).get("values", [])

    total = 0

    for serie in values:
        for point in serie.get("dataPoints", []):
            valeur = point.get("value", 0)

            try:
                total += float(valeur)
            except (TypeError, ValueError):
                pass

    return round(total)


class Handler(SimpleHTTPRequestHandler):

    def do_GET(self):

        if self.path == "/api/stats":

            try:
                # Informations générales du jeu
                game_url = (
                    "https://games.roblox.com/v1/games"
                    f"?universeIds={UNIVERSE_ID}"
                )

                with urlopen(game_url, timeout=10) as response:
                    game_data = json.loads(
                        response.read().decode("utf-8")
                    )

                # Likes / dislikes
                votes_url = (
                    "https://games.roblox.com/v1/games/votes"
                    f"?universeIds={UNIVERSE_ID}"
                )

                with urlopen(votes_url, timeout=10) as response:
                    votes_data = json.loads(
                        response.read().decode("utf-8")
                    )

                game = game_data["data"][0]
                votes = votes_data["data"][0]

                # Revenu des 30 derniers jours
                revenu_30_jours = recuperer_revenu()

                result = {
                    "playing": game["playing"],
                    "visits": game["visits"],
                    "favorites": game["favoritedCount"],
                    "likes": votes["upVotes"],
                    "dislikes": votes["downVotes"],
                    "revenue30days": revenu_30_jours
                }

                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "application/json"
                )
                self.send_header(
                    "Cache-Control",
                    "no-cache"
                )
                self.end_headers()

                self.wfile.write(
                    json.dumps(result).encode("utf-8")
                )

            except Exception as e:

                self.send_response(500)
                self.send_header(
                    "Content-Type",
                    "application/json"
                )
                self.end_headers()

                self.wfile.write(
                    json.dumps({
                        "error": str(e)
                    }).encode("utf-8")
                )

        else:
            super().do_GET()


PORT = int(os.environ.get("PORT", 8000))

server = ThreadingHTTPServer(
    ("0.0.0.0", PORT),
    Handler
)

print(f"Site lancé sur le port {PORT}")

server.serve_forever()

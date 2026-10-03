from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
import json
import os
import traceback
from datetime import datetime, timedelta, timezone
import time

UNIVERSE_ID = "10768969887"
ROBLOX_API_KEY = os.environ.get("ROBLOX_API_KEY")


def get_json(url, method="GET", body=None, headers=None):
    request = Request(
        url,
        data=body,
        headers=headers or {},
        method=method
    )

    try:
        with urlopen(request, timeout=30) as response:
            status = response.status
            raw = response.read().decode("utf-8")
            return status, json.loads(raw)

    except HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            details = json.loads(raw)
        except:
            details = {"message": raw}

        raise Exception(
            f"HTTP {e.code} sur {url} : {json.dumps(details, ensure_ascii=False)}"
        )

    except URLError as e:
        raise Exception(f"Erreur réseau : {e}")


def recuperer_revenu():
    if not ROBLOX_API_KEY:
        raise Exception(
            "ROBLOX_API_KEY est absente dans les variables Render."
        )

    maintenant = datetime.now(timezone.utc)
    debut = maintenant - timedelta(days=30)

    payload = {
        "metric": "DailyRevenue",
        "granularity": "OneDay",
        "startTime": debut.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endTime": maintenant.strftime("%Y-%m-%dT%H:%M:%SZ")
    }

    url = (
        "https://apis.roblox.com/analytics-query-api/v1/"
        f"universes/{UNIVERSE_ID}/metrics"
    )

    status, data = get_json(
        url,
        method="POST",
        body=json.dumps(payload).encode("utf-8"),
        headers={
            "x-api-key": ROBLOX_API_KEY,
            "Content-Type": "application/json"
        }
    )

    print("Analytics status:", status)
    print("Analytics response:", json.dumps(data, ensure_ascii=False))

    # Requête terminée immédiatement
    if data.get("done") is True:
        if "error" in data:
            raise Exception(
                "Roblox Analytics : " +
                json.dumps(data["error"], ensure_ascii=False)
            )

        return additionner_resultats(data)

    # Requête longue
    path = data.get("path")

    if not path:
        raise Exception(
            "Roblox n'a pas renvoyé de path pour l'opération."
        )

    result_url = (
        "https://apis.roblox.com/analytics-query-api/" +
        path.lstrip("/")
    )

    for _ in range(30):

        time.sleep(2)

        status, result = get_json(
            result_url,
            method="GET",
            headers={
                "x-api-key": ROBLOX_API_KEY
            }
        )

        print("Polling analytics:", status)
        print(json.dumps(result, ensure_ascii=False))

        if result.get("done") is True:

            if "error" in result:
                raise Exception(
                    "Roblox Analytics : " +
                    json.dumps(result["error"], ensure_ascii=False)
                )

            return additionner_resultats(result)

    raise Exception(
        "Roblox Analytics n'a pas terminé après 60 secondes."
    )


def additionner_resultats(data):
    total = 0

    values = data.get("response", {}).get("values", [])

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
                # Statistiques générales
                game_url = (
                    "https://games.roblox.com/v1/games"
                    f"?universeIds={UNIVERSE_ID}"
                )

                _, game_data = get_json(game_url)

                # Likes / dislikes
                votes_url = (
                    "https://games.roblox.com/v1/games/votes"
                    f"?universeIds={UNIVERSE_ID}"
                )

                _, votes_data = get_json(votes_url)

                game = game_data["data"][0]
                votes = votes_data["data"][0]

                # Revenu
                try:
                    revenu = recuperer_revenu()
                    revenu_error = None
                except Exception as e:
                    revenu = None
                    revenu_error = str(e)

                    print("ERREUR REVENUE:")
                    traceback.print_exc()

                result = {
                    "playing": game["playing"],
                    "visits": game["visits"],
                    "favorites": game["favoritedCount"],
                    "likes": votes["upVotes"],
                    "dislikes": votes["downVotes"],
                    "revenue30days": revenu,
                    "revenueError": revenu_error
                }

                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "application/json; charset=utf-8"
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

                print("ERREUR GENERALE:")
                traceback.print_exc()

                self.send_response(500)
                self.send_header(
                    "Content-Type",
                    "application/json; charset=utf-8"
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

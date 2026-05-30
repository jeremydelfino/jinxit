"""
Debug — quelles tables ont vraiment les picks/bans en 2024-2026 ?
"""
import sys
import os
import time
sys.path.insert(0, ".")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from mwcleric.auth_credentials import AuthCredentials
from mwrogue.esports_client import EsportsClient

creds = AuthCredentials(
    username=os.environ["LEAGUEPEDIA_USERNAME"],
    password=os.environ["LEAGUEPEDIA_PASSWORD"],
)
client = EsportsClient("lol", credentials=creds)
print("✅ Login OK\n")


def run(label, **kwargs):
    print(f"--- {label} ---")
    try:
        rows = client.cargo_client.query(**kwargs)
        print(f"  ✅ {len(rows)} rows")
        for r in rows[:1]:
            print(f"    {dict(r)}")
    except Exception as e:
        print(f"  ❌ {e}")
    print()
    time.sleep(8)


for team in ["Karmine Corp", "G2 Esports", "T1"]:
    rows = client.cargo_client.query(
        tables="ScoreboardGames",
        fields="Team1,Team2,Team1Picks,Team2Picks,DateTime_UTC=date",
        where=f'(Team1="{team}" OR Team2="{team}") AND DateTime_UTC >= "2025-11-01"',
        order_by="DateTime_UTC DESC", limit="10",
    )
    print(team, "→", len(rows), "games")

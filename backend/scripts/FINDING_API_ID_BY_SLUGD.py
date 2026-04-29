import asyncio
import httpx

# Ta liste de slugs à vérifier
SLUGS_A_TROUVER = [
    'T1-academy'
]

async def generer_fichier_ids():
    # Exactement la config de ton lolesports.py / esport-sync.py
    url = "https://esports-api.lolesports.com/persisted/gw/getTeams"
    api_key = "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"

    async with httpx.AsyncClient(timeout=12) as client:
        print("⏳ Récupération des données depuis l'API...")
        r = await client.get(
            url,
            headers={"x-api-key": api_key},
            params={"hl": "fr-FR"}
        )
        r.raise_for_status()
        data = r.json()

    teams = data.get("data", {}).get("teams", [])
    
    # On map tous les slugs avec leurs IDs pour que la recherche soit instantanée
    mapping = {t["slug"]: t["id"] for t in teams}

    fichier_sortie = "mes_ids_equipes.txt"
    
    print("📝 Écriture dans le fichier...\n")
    with open(fichier_sortie, "w", encoding="utf-8") as f:
        for slug in SLUGS_A_TROUVER:
            # S'il ne trouve pas le slug exact, il renverra une chaîne vide
            api_id = mapping.get(slug, "")
            ligne = f'{slug}="{api_id}"\n'
            
            f.write(ligne)
            print(ligne.strip()) # Je te l'affiche aussi dans la console pour vérifier

    print(f"\n✅ Fichier '{fichier_sortie}' créé avec succès à la racine de ton dossier !")

if __name__ == "__main__":
    asyncio.run(generer_fichier_ids())
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models.pro_player import ProPlayer

BASE = "https://lol.fandom.com/wiki/Special:FilePath/"

TEAM_LOGOS = {
    "T1":                   BASE + "T1logo_profile.png",
    "Gen.G":                BASE + "Gen.Glogo_profile.png",
    "Hanwha Life Esports":  BASE + "Hanwha_Life_Esportslogo_profile.png",
    "KT Rolster":           BASE + "KT_Rolsterlogo_profile.png",
    "DRX":                  BASE + "DRXlogo_profile.png",
    "Dplus KIA":            BASE + "Dplus_KIAlogo_profile.png",
    "Nongshim RedForce":    BASE + "Nongshim_RedForcelogo_profile.png",
    "FEARX":                BASE + "FEARXlogo_profile.png",
    "HANJIN BRION":         BASE + "HANJIN_BRIONlogo_profile.png",
    "DN SOOPers":           BASE + "DN_SOOPerslogo_profile.png",
    "G2 Esports":           BASE + "G2_Esportslogo_profile.png",
    "Fnatic":               BASE + "Fnaticlogo_profile.png",
    "Karmine Corp":         BASE + "Karmine_Corplogo_profile.png",
    "Movistar KOI":         BASE + "Movistar_KOIlogo_profile.png",
    "GIANTX":               BASE + "GIANTXlogo_profile.png",
    "Team Vitality":        BASE + "Team_Vitalitylogo_profile.png",
    "Shifters":             BASE + "Shifterslogo_profile.png",
    "SK Gaming":            BASE + "SK_Gaminglogo_profile.png",
    "Team Heretics":        BASE + "Team_Hereticslogo_profile.png",
    "Natus Vincere":        BASE + "Natus_Vincerelogo_profile.png",
}

def set_logos():
    db = SessionLocal()
    updated = 0
    not_found = []

    pros = db.query(ProPlayer).filter(ProPlayer.is_active == True).all()

    for pro in pros:
        logo = TEAM_LOGOS.get(pro.team)
        if logo:
            pro.team_logo_url = logo
            updated += 1
        else:
            not_found.append(pro.team)

    db.commit()
    db.close()

    print(f"✅ {updated} joueurs mis à jour")
    if not_found:
        print(f"⚠️  Équipes sans logo : {set(not_found)}")

if __name__ == "__main__":
    set_logos()
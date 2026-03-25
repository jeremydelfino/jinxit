# backend/scripts/set_pro_photos.py
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models.pro_player import ProPlayer

BASE = "https://lol.fandom.com/wiki/Special:FilePath/"

PHOTOS = {
    # (name, team): url
    # ── DN SOOPers ──
    ("Clozer",      "DN SOOPers"):          BASE + "DNS_Clozer_2026_Split_1.png",
    ("deokdam",     "DN SOOPers"):          BASE + "DNS_deokdam_2026_Split_1.png",
    ("DuDu",        "DN SOOPers"):          BASE + "DNS_DuDu_2026_Split_1.png",
    ("Peter",       "DN SOOPers"):          BASE + "DNS_Peter_2026_Split_1.png",
    ("Pyosik",      "DN SOOPers"):          BASE + "DNS_Pyosik_2026_Split_1.png",
    # ── Dplus KIA ──
    ("Career",      "Dplus KIA"):           BASE + "DK_Career_2026_Split_1.png",
    ("Lucid",       "Dplus KIA"):           BASE + "DK_Lucid_2026_Split_1.png",
    ("ShowMaker",   "Dplus KIA"):           BASE + "DK_ShowMaker_2026_Split_1.png",
    ("Siwoo",       "Dplus KIA"):           BASE + "DK_Siwoo_2026_Split_1.png",
    ("Smash",       "Dplus KIA"):           BASE + "DK_Smash_2026_Split_1.png",
    # ── DRX ──
    ("Andil",       "DRX"):                 BASE + "DRX_Andil_2026_Split_1.png",
    ("Jiwoo",       "DRX"):                 BASE + "DRX_Jiwoo_2026_Split_1.png",
    ("Rich",        "DRX"):                 BASE + "DRX_Rich_2026_Split_1.png",
    ("ucal",        "DRX"):                 BASE + "DRX_ucal_2026_Split_1.png",
    ("Vincenzo",    "DRX"):                 BASE + "DRX_Vincenzo_2026_Split_1.png",
    # ── FEARX ──
    ("Clear",       "FEARX"):               BASE + "FOX_Clear_2026_Split_1.png",
    ("Kellin",      "FEARX"):               BASE + "FOX_Kellin_2026_Split_1.png",
    ("Raptor",      "FEARX"):               BASE + "FOX_Raptor_2026_Split_1.png",
    ("VicLa",       "FEARX"):               BASE + "FOX_VicLa_2026_Split_1.png",
    # ── Fnatic ──
    ("Empyros",     "Fnatic"):              BASE + "FNC_Empyros_2026_Split_1.png",
    ("Lospa",       "Fnatic"):              BASE + "FNC_Lospa_2026_Split_1.png",
    ("Razork",      "Fnatic"):              BASE + "FNC_Razork_2026_Split_1.png",
    ("Upset",       "Fnatic"):              BASE + "FNC_Upset_2026_Split_1.png",
    ("Vladi",       "Fnatic"):              BASE + "FNC_Vladi_2026_Split_1.png",
    # ── G2 Esports ──
    ("BrokenBlade", "G2 Esports"):          BASE + "G2_BrokenBlade_2026_Split_1.png",
    ("Caps",        "G2 Esports"):          BASE + "G2_Caps_2026_Split_1.png",
    ("Hans Sama",   "G2 Esports"):          BASE + "G2_Hans_Sama_2026_Split_1.png",
    ("Labrov",      "G2 Esports"):          BASE + "G2_Labrov_2026_Split_1.png",
    ("SkewMond",    "G2 Esports"):          BASE + "G2_SkewMond_2026_Split_1.png",
    # ── Gen.G ──
    ("Canyon",      "Gen.G"):               BASE + "GEN_Canyon_2026_Split_1.png",
    ("Chovy",       "Gen.G"):               BASE + "GEN_Chovy_2026_Split_1.png",
    ("Kiin",        "Gen.G"):               BASE + "GEN_Kiin_2026_Split_1.png",
    ("Lehends",     "Gen.G"):               BASE + "GEN_Lehends_2026_Split_1.png",
    ("Ruler",       "Gen.G"):               BASE + "GEN_Ruler_2026_Split_1.png",
    # ── GIANTX ──
    ("ISMA",        "GIANTX"):              BASE + "GX_ISMA_2026_Split_1.png",
    ("Jackies",     "GIANTX"):              BASE + "GX_Jackies_2026_Split_1.png",
    ("Jun",         "GIANTX"):              BASE + "GX_Jun_2026_Split_1.png",
    ("Lot",         "GIANTX"):              BASE + "GX_Lot_2026_Split_1.png",
    ("Noah",        "GIANTX"):              BASE + "GX_Noah_2026_Split_1.png",
    # ── Hanwha Life Esports ──
    ("Delight",     "Hanwha Life Esports"): BASE + "HLE_Delight_2026_Split_1.png",
    ("Gumayusi",    "Hanwha Life Esports"): BASE + "HLE_Gumayusi_2026_Split_1.png",
    ("Kanavi",      "Hanwha Life Esports"): BASE + "HLE_Kanavi_2026_Split_1.png",
    ("Zeka",        "Hanwha Life Esports"): BASE + "HLE_Zeka_2026_Split_1.png",
    ("Zeus",        "Hanwha Life Esports"): BASE + "HLE_Zeus_2026_Split_1.png",
    # ── Karmine Corp ──
    ("Busio",       "Karmine Corp"):        BASE + "KC_Busio_2026_Split_1.png",
    ("Caliste",     "Karmine Corp"):        BASE + "KC_Caliste_2026_Split_1.png",
    ("Canna",       "Karmine Corp"):        BASE + "KC_Canna_2026_Split_1.png",
    ("Kyeahoo",     "Karmine Corp"):        BASE + "KC_Kyeahoo_2026_Split_1.png",
    ("Yike",        "Karmine Corp"):        BASE + "KC_Yike_2026_Split_1.png",
    # ── KT Rolster ──
    ("Aiming",      "KT Rolster"):          BASE + "KT_Aiming_2026_Split_1.png",
    ("Bdd",         "KT Rolster"):          BASE + "KT_Bdd_2026_Split_1.png",
    ("Cuzz",        "KT Rolster"):          BASE + "KT_Cuzz_2026_Split_1.png",
    ("Ghost",       "KT Rolster"):          BASE + "KT_Ghost_2026_Split_1.png",
    ("Kingen",      "KT Rolster"):          BASE + "KT_Kingen_2026_Split_1.png",
    # ── Movistar KOI ──
    ("Alvaro",      "Movistar KOI"):        BASE + "KOI_Alvaro_2026_Split_1.png",
    ("Elyoya",      "Movistar KOI"):        BASE + "KOI_Elyoya_2026_Split_1.png",
    ("Jojopyun",    "Movistar KOI"):        BASE + "KOI_Jojopyun_2026_Split_1.png",
    ("Myrwn",       "Movistar KOI"):        BASE + "KOI_Myrwn_2026_Split_1.png",
    ("Supa",        "Movistar KOI"):        BASE + "KOI_Supa_2026_Split_1.png",
    # ── Natus Vincere ──
    ("Larssen",     "Natus Vincere"):       BASE + "NAVI_Larssen_2026_Split_1.png",
    ("Maynter",     "Natus Vincere"):       BASE + "NAVI_Maynter_2026_Split_1.png",
    ("Patrik",      "Natus Vincere"):       BASE + "NAVI_Patrik_2026_Split_1.png",
    ("Poby",        "Natus Vincere"):       BASE + "NAVI_Poby_2026_Split_1.png",
    ("Sanchi",      "Natus Vincere"):       BASE + "NAVI_Sanchi_2026_Split_1.png",
    # ── Nongshim RedForce ──
    ("Kingen",      "Nongshim RedForce"):   BASE + "NS_Kingen_2026_Split_1.png",
    ("Lehends",     "Nongshim RedForce"):   BASE + "NS_Lehends_2026_Split_1.png",
    ("Scout",       "Nongshim RedForce"):   BASE + "NS_Scout_2026_Split_1.png",
    ("Sponge",      "Nongshim RedForce"):   BASE + "NS_Sponge_2026_Split_1.png",
    ("Taeyoon",     "Nongshim RedForce"):   BASE + "NS_Taeyoon_2026_Split_1.png",
    # ── Shifters ──
    ("Boukada",     "Shifters"):            BASE + "SHF_Boukada_2026_Split_1.png",
    ("nuc",         "Shifters"):            BASE + "SHF_nuc_2026_Split_1.png",
    ("Paduck",      "Shifters"):            BASE + "SHF_Paduck_2026_Split_1.png",
    ("Rooster",     "Shifters"):            BASE + "SHF_Rooster_2026_Split_1.png",
    ("Trymbi",      "Shifters"):            BASE + "SHF_Trymbi_2026_Split_1.png",
    # ── SK Gaming ──
    ("Exakick",     "SK Gaming"):           BASE + "SK_Exakick_2026_Split_1.png",
    ("Markoon",     "SK Gaming"):           BASE + "SK_Markoon_2026_Split_1.png",
    ("Mikyx",       "SK Gaming"):           BASE + "SK_Mikyx_2026_Split_1.png",
    ("Reeker",      "SK Gaming"):           BASE + "SK_Reeker_2026_Split_1.png",
    ("Wunder",      "SK Gaming"):           BASE + "SK_Wunder_2026_Split_1.png",
    # ── T1 ──
    ("Doran",       "T1"):                  BASE + "T1_Doran_2026_LCK_Cup.png",
    ("Faker",       "T1"):                  BASE + "T1_Faker_2026_LCK_Cup.png",
    ("Keria",       "T1"):                  BASE + "T1_Keria_2026_LCK_Cup.png",
    ("Oner",        "T1"):                  BASE + "T1_Oner_2026_LCK_Cup.png",
    ("Peyz",        "T1"):                  BASE + "T1_Peyz_2026_LCK_Cup.png",
    # ── Team Heretics ──
    ("Alvaro",      "Team Heretics"):       BASE + "TH_Alvaro_2026_Split_1.png",
    ("Daglas",      "Team Heretics"):       BASE + "TH_Daglas_2026_Split_1.png",
    ("Jackies",     "Team Heretics"):       BASE + "TH_Jackies_2026_Split_1.png",
    ("Odoamne",     "Team Heretics"):       BASE + "TH_Odoamne_2026_Split_1.png",
    ("Tracyn",      "Team Heretics"):       BASE + "TH_Tracyn_2026_Split_1.png",
    # ── Team Vitality ──
    ("Carzzy",      "Team Vitality"):       BASE + "VIT_Carzzy_2026_Split_1.png",
    ("Fleshy",      "Team Vitality"):       BASE + "VIT_Fleshy_2026_Split_1.png",
    ("Humanoid",    "Team Vitality"):       BASE + "VIT_Humanoid_2026_Split_1.png",
    ("Lyncas",      "Team Vitality"):       BASE + "VIT_Lyncas_2026_Split_1.png",
    ("Naak Nako",   "Team Vitality"):       BASE + "VIT_Naak_Nako_2026_Split_1.png",
}


def set_photos():
    db = SessionLocal()
    updated = 0
    not_found = []

    pros = db.query(ProPlayer).filter(ProPlayer.is_active == True).all()

    for pro in pros:
        pro.photo_url = None  # reset propre

    for pro in pros:
        url = PHOTOS.get((pro.name, pro.team))
        if url:
            pro.photo_url = url
            updated += 1
            print(f"✅ {pro.name} ({pro.team})")
        else:
            not_found.append(f"{pro.name} ({pro.team})")

    db.commit()
    db.close()

    print(f"\n✅ {updated} photos assignées")
    if not_found:
        print(f"⚠️  {len(not_found)} joueurs sans photo :")
        for p in not_found:
            print(f"   - {p}")


if __name__ == "__main__":
    set_photos()
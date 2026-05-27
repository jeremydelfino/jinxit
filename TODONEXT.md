# Récap complet — Suite système Caisses/Stickers Jungle Gap

## ✅ État actuel (DONE)

### Backend
- **Migrations DB locales** appliquées (PAS en prod) :
  - `user_cards` : `quantity INTEGER DEFAULT 1`, `equipped_slot VARCHAR(10)` (legacy, à drop), `position_x NUMERIC(5,2)`, `position_y NUMERIC(5,2)`
  - Contraintes `uq_user_cards_user_slot` et `user_cards_equipped_slot_check` **droppées**
  - `lootbox_types` : table créée (config admin, drop_rates, pool_types CSV, price_coins, is_active)
  - `lootboxes` : table créée (caisses possédées + opened_at + opened_card_id)
  - `promo_codes` : colonnes `lootbox_type_id` + `lootbox_quantity` ajoutées
  - `cards` : colonne `collection VARCHAR(100)` ajoutée
  - `transactions.transactions_type_check` étendu : ajout de `lootbox_purchase`, `card_sold`, `crate_purchase`, `promo_redeem`, `admin_add`, `coachdiff_*`

- **Modèles SQLAlchemy** :
  - `backend/models/lootbox.py` : `LootBoxType` + `LootBox`
  - `backend/models/user_card.py` : `quantity`, `position_x`, `position_y` ajoutés (le `equipped_slot` peut rester mais n'est plus utilisé)
  - `backend/models/promo.py` : `lootbox_type_id` + `lootbox_quantity` + relationship `lootbox_type`
  - `backend/models/card.py` : `collection = Column(String(100), nullable=True)`

- **Services** :
  - `backend/services/lootbox_service.py` : `pick_card_from_box()` (tirage rareté pondéré + fallback rareté si pool vide), `grant_card_to_user()` (atomique via `ON CONFLICT DO UPDATE`), constantes `RESALE_PRICES = {common:50, rare:200, epic:800, legendary:3000}`

- **Routers** :
  - `backend/routers/lootbox.py` :
    - `GET /lootbox/my-boxes` ✅
    - `GET /lootbox/types` ✅
    - `POST /lootbox/{box_id}/open` ✅
    - `POST /lootbox/buy/{box_type_id}` ✅ (avec `with_for_update`, vérif `is_active`, débit + Transaction)
    - `POST /lootbox/admin/types` ✅ (création, validation drop_rates total=100)
    - `POST /lootbox/admin/grant/{user_id}/{box_type_id}` ✅
    - `GET /lootbox/admin/types` ✅ (tous, gating `is_admin`)
    - `PATCH /lootbox/admin/types/{id}` ✅
    - `DELETE /lootbox/admin/types/{id}` ✅ (soft si caisses en circulation, hard sinon)
  - `backend/routers/cards.py` (complètement réécrit) :
    - `GET /cards/my-cards` ✅ (renvoie `quantity`, `position_x/y`, `collection`)
    - `POST /cards/{user_card_id}/sell` ✅ (auto-unequip si dernière copie, débit, Transaction)
    - `GET /cards/collection-progress` ✅ (cartes groupées par type → collection)
    - `POST /cards/equip-sticker` ✅ (positions libres, check max 3, type=sticker uniquement)
    - `POST /cards/move-sticker` ✅ (update position drag)
    - `DELETE /cards/equip-sticker/{user_card_id}` ✅
    - `GET /cards/equipped-stickers` ✅ (renvoie une **liste**, pas un dict left/center/right)
    - Helper `_equipped_stickers_for(db, user_id)` exposé pour les autres routers
  - `backend/routers/promo.py` :
    - `POST /promo/redeem` ✅ avec intégration lootbox
    - `CreatePromoSchema` étendu (lootbox_type_id + lootbox_quantity)
    - `_serialize()` retourne le champ `lootbox`

- **Bug fix critique appliqué** : `routers/promo.py` importait `models.promo_code` au lieu de `models.promo` → corrigé

### Frontend
- **Route ajoutée** dans `App.jsx` : `<Route path="/lootbox" element={<LootBox />} />`
- **Page `frontend/src/pages/LootBox/index.jsx`** créée avec 4 onglets (Collection / Stickers / Mes caisses / Boutique) :
  - Hero avec stats (coins, caisses en attente, cartes possédées, stickers possédés)
  - Tab Collection : sous-vues groupées par nom de collection (Beta, LegendsV1...) avec progress bar, slots grisés pour les non-possédées, bouton revendre sur les possédées
  - Tab Stickers : même UX mais filtrée sur `type === 'sticker'`
  - Tab Mes caisses : grille des caisses non-ouvertes, animation d'ouverture en 2 phases (shake → reveal)
  - Tab Boutique : section caisses (drop rates en barres animées) + section "achat à l'unité" (placeholder "bientôt disponible")
  - Reveal full-screen avec burst, glow par rareté, TcgCard, bouton continuer
  - `loadAll()` utilise `Promise.allSettled` (tolère les erreurs partielles)
- **Page `LootBox.css`** : design complet avec glows de fond animés, texture noise, gradient hero, tabs premium, drop rates en pills/barres, animations (shimmer, pulse, float, burst, reveal-pop), responsive complet

- **Composant `frontend/src/pages/Profile/components/BannerStickers/index.jsx`** créé :
  - Récupère les stickers équipés via `/cards/equipped-stickers`
  - Affiche les stickers en `position:absolute` sur la bannière à `(x%, y%)`
  - Drag-and-drop natif (pointer events) pour repositionner librement
  - Bouton `+ Sticker` en bas-droite de la bannière si moins de 3 équipés
  - Modal **full-screen** (via `createPortal`) au clic, avec grille des stickers possédés non-équipés
  - Bouton × sur chaque sticker au hover pour le retirer
  - Glow par rareté (drop-shadow CSS)
  - **Le composant attend une prop `bannerRef`** pour calculer les % par rapport à la bannière

- **`BannerStickers.css`** : taille 100x100px (70 sur mobile), glow par rareté, bouton add pulsant, modal portal premium

---

## 🎯 Ce qu'il reste à faire (TODO dans l'ordre)

### Étape A — Finir l'intégration BannerStickers dans Profile (PRIORITÉ 1)
**Pas encore fait.** Le composant est créé mais pas branché dans `Profile/index.jsx`. Il faut :

1. Demander à Jérémy de coller son `Profile/index.jsx` actuel (l'AI a refusé de réécrire à l'aveugle pour ne pas perdre des hooks/handlers existants)
2. Dans `Profile/index.jsx` :
   - Importer `BannerStickers` : `import BannerStickers from './components/BannerStickers'`
   - Importer `useRef` depuis React
   - Créer `const bannerRef = useRef(null)`
   - Ajouter la ref à la bannière : `<div className="profile-banner" ref={bannerRef} ...>`
   - Placer `<BannerStickers userId={profile?.id} isOwnProfile={isOwnProfile} bannerRef={bannerRef} />` **à l'intérieur** de `.profile-banner` (juste avant son `</div>` fermant)
3. Vérifier dans `Profile.css` que `.profile-banner` a bien `position: relative` (sinon les stickers en `absolute` se positionneront par rapport au mauvais conteneur)

### Étape B — Exposer les stickers d'autres users
Quand un utilisateur consulte le profil d'un autre, le composant appelle `/profile/{userId}/equipped-stickers` qui **n'existe pas encore**. Deux options :

- **Option 1 (rapide)** : créer ce endpoint dans `routers/profile.py` qui appelle `_equipped_stickers_for(db, user_id)` de `cards.py`
- **Option 2 (mieux)** : ajouter directement `equipped_stickers: [...]` dans la réponse de `/profile/{userId}` et `/profile/me`, et adapter le composant pour lire depuis là plutôt que faire un fetch séparé

Recommandation : option 1 d'abord (plus rapide à valider), puis migrer vers option 2 plus tard.

### Étape C — Admin UI (lootbox + cards)
**Pas commencé.** À faire pour ne plus avoir à tout faire en SQL/curl :

1. **Page `frontend/src/pages/AdminLootbox/index.jsx`** :
   - Liste des types de caisses (`GET /lootbox/admin/types`)
   - Formulaire création (nom, description, image_url, price_coins, pool_types CSV, drop_rates total=100, is_active)
   - Édition inline (PATCH)
   - Suppression (DELETE avec gestion soft/hard)
   - Gating `is_admin` (rediriger si pas admin)
   - Ajouter la route dans `App.jsx`

2. **Page AdminCards** (existe déjà à `frontend/src/pages/AdminCards/`) :
   - Ajouter `sticker` dans le dropdown des types
   - Ajouter le champ `collection` (input text libre)
   - S'assurer que le POST passe bien `collection` au backend
   - Côté backend : modifier `routers/admin.py` `create_card` pour accepter `collection: Optional[str] = Form(None)` et l'inclure dans l'instanciation + dans la réponse de `list_cards`

3. **Page AdminPromo** : ajouter les champs `lootbox_type_id` (dropdown des types existants) + `lootbox_quantity` (int) dans le form

### Étape D — Mise en production
Quand tout est validé en local :

1. **Backup DB prod** : `pg_dump junglegap > backup_$(date +%Y%m%d).sql`
2. **Migrations à appliquer en prod** (toutes celles faites en local) :
   ```sql
   -- user_cards
   ALTER TABLE user_cards ADD COLUMN IF NOT EXISTS quantity INTEGER NOT NULL DEFAULT 1;
   ALTER TABLE user_cards ADD COLUMN IF NOT EXISTS equipped_slot VARCHAR(10);
   ALTER TABLE user_cards ADD COLUMN IF NOT EXISTS position_x NUMERIC(5,2);
   ALTER TABLE user_cards ADD COLUMN IF NOT EXISTS position_y NUMERIC(5,2);
   ALTER TABLE user_cards DROP CONSTRAINT IF EXISTS uq_user_cards_user_slot;
   ALTER TABLE user_cards DROP CONSTRAINT IF EXISTS user_cards_equipped_slot_check;
   
   -- cards
   ALTER TABLE cards ADD COLUMN IF NOT EXISTS collection VARCHAR(100);
   
   -- transactions
   ALTER TABLE transactions DROP CONSTRAINT IF EXISTS transactions_type_check;
   ALTER TABLE transactions ADD CONSTRAINT transactions_type_check
     CHECK (type IN ('signup_bonus','daily_reward','admin_add','bet_placed','bet_won','bet_lost','bet_refunded','bet_cancelled','crate_purchase','lootbox_purchase','card_sold','coachdiff_entry','coachdiff_win','coachdiff_draw','promo_redeem'));
   
   -- lootbox_types + lootboxes : récupérer le DDL exact depuis la DB locale
   -- (pg_dump --schema-only -t lootbox_types -t lootboxes junglegap)
   
   -- promo_codes
   ALTER TABLE promo_codes ADD COLUMN IF NOT EXISTS lootbox_type_id INTEGER REFERENCES lootbox_types(id);
   ALTER TABLE promo_codes ADD COLUMN IF NOT EXISTS lootbox_quantity INTEGER DEFAULT 0;
   ```
3. **Push code** : git push main
4. **Restart systemd** : `sudo systemctl restart junglegap-backend` sur la VM
5. **Smoke tests prod** :
   - Créer un type de caisse via curl admin
   - S'auto-grant une caisse
   - Ouvrir → vérifier qu'on récupère une carte (s'assurer qu'il y a des cartes en DB prod)
   - Acheter une caisse (vérifier débit coins)
   - Vendre une carte
   - Créer un code promo lootbox + redeem
   - Aller sur `/lootbox` et vérifier les 4 onglets
   - Équiper un sticker, drag, retirer

### Étape E — Polish & extensions (optionnel après MVP)
- Notifications/toasts au lieu des `alert()` et `window.confirm()`
- Animation de "vibration légère" au moment du débit de coins
- Filtre/recherche dans la grille Collection (par nom, par rareté)
- Tri des collections (par % de complétion, alphabétique, date d'ajout)
- Sound effect optionnel à l'ouverture de caisse
- Endpoint `/lootbox/admin/cleanup-test-boxes` pour wipe rapidement l'inventaire de test
- Animation des stickers (légère flottaison) sur les profils visités
- Système d'**emote / frame / title** (déjà prévu architecturalement, juste ajouter le `type` correspondant et la logique d'équipement)
- Boutique : implémenter l'achat à l'unité de cartes (actuellement placeholder)
- Stats Hero : ajouter un compteur "Stickers équipés" (X/3)
- Stocker l'historique des ouvertures (lootbox_id → card_id) pour affichage "Drops récents persistants" entre sessions

---

## Setup Jérémy
- macOS, zsh, pyenv Python 3.10.10, projet `/Users/jdelfino/JinxIt/jinxit/` (legacy) — l'arbo réelle utilise `JinxIt/jinxit/` malgré le rebrand
- DB locale : `psql -d junglegap` (accès direct, pas besoin de sudo postgres)
- VM prod : `junglegap` (systemd `junglegap-backend`)
- Domaines : `junglegap.fr` (front Vercel) + `api.junglegap.fr` (back nginx)
- `user_id` Jérémy en local = **2**

## Préférences Jérémy
- Étudiant info, explications **claires/concises mais extrêmement bien réfléchies**
- Réécritures **complètes** des fichiers après accumulation de fixes (pas de patch)
- Modifs ligne par ligne quand scope étroit/clair
- Discuter l'approche avant de coder quand ambigu
- Code copy-pasteable dans le chat (pas en fichier joint)
- **CSS** : une règle par ligne, groupé par catégorie avec commentaires de section (ex: `/* ─── HERO ─── */`)
- Composants : `frontend/src/pages/[Name]/index.jsx` + `[Name].css` séparés
- `api` client centralisé (`import api from '../../api/client'`), **JAMAIS axios brut**
- Auth store : **default export** (`import useAuthStore from '../../store/auth'`)
- Design system : `#171717` bg, `#65BD62` vert, `#c89b3c` gold, Outfit (800-900 headings) + Inter (body)
- Préfère le drag natif HTML5 / pointer events au lieu d'ajouter une dépendance

## Décisions architecturales (à NE PAS remettre en cause)
- **Toutes les cartes dans `cards`** (pas de table séparée). Distinction via colonne `type` (champion / pro_player / meme / cosmetic / sticker / emote / frame / title à venir)
- **Système de stickers** : positions libres x/y en %, max 3 équipés (check applicatif `MAX_EQUIPPED_STICKERS = 3`), boolean `equipped` + `position_x`/`position_y` nullable
- **Anciens slots left/center/right** : `equipped_slot` legacy à droper plus tard (déjà vidé de toute contrainte)
- **Drop rates globaux par défaut** : common 60% / rare 25% / epic 12% / legendary 3% (stockés sur `lootbox_types` pour permettre des caisses spéciales)
- **Doublons stockés en `quantity`** sur `user_cards` via `ON CONFLICT DO UPDATE`
- **Revente manuelle** par l'user (50/200/800/3000 selon rareté)
- **Caisses obtenues via** : achat coins + code promo (pas de daily, pas de drop sur paris pour l'instant)
- **Collection** : champ libre `VARCHAR(100)` sur `cards` (ex: "Beta", "LegendsV1"). NULL = "Sans collection". Pas une table à part.
- **Onglet par défaut sur `/lootbox`** : Collection (progression visible d'emblée)
- **Modal stickers** : full-screen via `createPortal` (pas confiné dans la bannière)

## Première action attendue pour le nouveau chat
Jérémy doit coller son `Profile/index.jsx` actuel. L'AI doit :
1. Le réécrire complet en ajoutant `useRef`, `bannerRef`, et l'intégration `<BannerStickers>` dans `.profile-banner`
2. Vérifier que `.profile-banner` a `position: relative` dans le CSS
3. Créer l'endpoint manquant `GET /profile/{userId}/equipped-stickers` (ou modifier le composant pour lire depuis `/profile/{userId}` si l'endpoint expose déjà `equipped_stickers`)
4. Tester : ajout sticker, drag, retrait, consultation d'un autre profil
5. Ensuite enchaîner sur **Étape C (Admin UI)** puis **Étape D (prod)**

Bon courage 🚀
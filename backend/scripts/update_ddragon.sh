#!/bin/bash
# scripts/update_ddragon_version.sh
# Usage : bash scripts/update_ddragon_version.sh

set -e

PROJECT_ROOT="../../"

echo "🔍 Récupération de la dernière version DDragon..."
LATEST=$(curl -s https://ddragon.leagueoflegends.com/api/versions.json | python3 -c "import sys, json; print(json.load(sys.stdin)[0])")

if [ -z "$LATEST" ]; then
  echo "❌ Impossible de récupérer la version DDragon"
  exit 1
fi

echo "✅ Version actuelle : $LATEST"

# Trouver toutes les versions DDragon hardcodées dans le projet
echo ""
echo "🔎 Versions trouvées dans le projet :"
grep -rn --include="*.py" --include="*.jsx" --include="*.js" --include="*.ts" \
  -E "[0-9]+\.[0-9]+\.[0-9]+" "$PROJECT_ROOT" \
  | grep "ddragon" \
  | grep -oE "[0-9]+\.[0-9]+\.[0-9]+" | sort -u

echo ""
echo "🔄 Remplacement par $LATEST..."

# Remplace toutes les versions DDragon dans les fichiers source
# On cible uniquement les lignes qui contiennent "ddragon" pour éviter
# de toucher d'autres numéros de version (ex: Python, npm, etc.)
find "$PROJECT_ROOT" \( -name "*.py" -o -name "*.jsx" -o -name "*.js" -o -name "*.ts" \) \
  ! -path "*/node_modules/*" \
  ! -path "*/.git/*" \
  ! -path "*/venv/*" \
  ! -path "*/__pycache__/*" \
  -print0 | while IFS= read -r -d '' file; do
    if grep -q "ddragon" "$file" 2>/dev/null; then
      # Remplace les versions de la forme X.XX.X dans les lignes contenant ddragon
      perl -i -pe 's|(?<=ddragon\.leagueoflegends\.com/cdn/)\d+\.\d+\.\d+|'"$LATEST"'|g' "$file"
      echo "   📝 $file"
    fi
done

echo ""
echo "✅ Migration terminée → version DDragon : $LATEST"
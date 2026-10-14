# VuLink Pro V2 — Connexion QR & maintenance locale (bêta)

**Extension indépendante** installée dans \`/usr/lib/enigma2/python/Plugins/Extensions/VuLink\`, sans modification d'IPToSatPro, de ses mappings ou de son lecteur.

## Utilisation

1. Télécharge l'installateur sur ton Vu+ (root via SSH déjà actif) :
   \`\`\`sh
   wget -qO /tmp/install-vulink-v2.sh https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/vulink-pro-v2/vulink/install.sh
   sh /tmp/install-vulink-v2.sh --check
   \`\`\`
   \`--check\` vérifie les fichiers et leur empreinte Git, sans changer le Vu+.
2. Puis installe explicitement : \`sh /tmp/install-vulink-v2.sh --install\`. Redémarre **l'interface Enigma2 seulement** via OpenATV.
3. Ouvre **Plugins → VuLink Pro V2 - QR Maintenance** sur ta TV, scanne le QR avec le téléphone sur le même réseau Wi-Fi. Sinon ouvre l'adresse affichée et entre le code TV.
4. Le téléphone affiche les diagnostics et deux actions prédéfinies : **Audit syntaxe** (lecture seule) et **Sauvegarde locale** (aucun export).
5. **Toute action demandée par le téléphone nécessite la touche VERTE sur la TV** ; la touche JAUNE refuse ; ROUGE/EXIT coupe le serveur et révoque la session.
6. Télécharge le rapport JSON depuis le téléphone puis **joins-le manuellement dans ChatGPT**. Aucune connexion directe ChatGPT → Vu+, aucun SSH/FTP distant, aucun tunnel cloud à ce stade.

## Ce que comprend le rapport

- Version IPToSatPro, présence des modules et OS Python ; mémoire / stockage disponible.
- Comptages anonymisés des événements IPTV (OK/FAIL/NO_MATCH) et métriques numériques de Preview.
- Séparation temps **index** / **scoring** / **elapsed**, échantillons, médiane, p95 et maximum quand présents.
- Jamais de log brut, nom de chaîne, URL de serveur IPTV, mot de passe, code de pairage, MAC ou contenu des mappings.

## Sécurité et limites

- Serveur HTTP temporaire **sur IPv4 privée LAN uniquement**, jamais \`0.0.0.0\` ; une connexion Wi-Fi de confiance est recommandée car **HTTP local n'est pas chiffré**.
- Code aléatoire 12 caractères, session 10 minutes, code transmis dans le QR (usage local), cookies HttpOnly/SameSite, CSRF, appairage lié à l'adresse IP, maximum 8 erreurs de code/minute/IP.
- Pour une action : délai d'approbation 90 secondes, autorisation par télécommande et actions **strictement listées**. Pas de terminal, \`exec\`, script externe, reboot, téléchargement de flux IPTV ou accès générique aux fichiers.
- Les sauvegardes sont locales, sous dossier root \`0700\`, fichiers \`0600\`, plafond 24 Mio/300 fichiers, sans suivre les liens symboliques. Elles peuvent contenir des secrets IPTV **uniquement sur le décodeur** ; elles ne sont jamais servies via HTTP. Un backup déjà approuvé peut continuer après fermeture de l'écran.
- Les tests CI ne remplacent pas l'essai Vu+ Zero 4K / OpenATV réel.
- Avant une **V3 avec pilotage autonome ChatGPT**, il faudra une passerelle d'outils expressément connectée et un canal chiffré avec politique d'autorisation : ce prototype ne la simule pas.

## Retour arrière

\`\`\`sh
sh /tmp/install-vulink-v2.sh --rollback
\`\`\`

Redémarre ensuite Enigma2 via le menu OpenATV. Le rollback ne touche pas IPToSatPro.

**Statut : BÊTA TEST**, branche \`feature/vulink-pro-v2\`. Ne pas promouvoir sur \`main\` sans validation sur récepteur.

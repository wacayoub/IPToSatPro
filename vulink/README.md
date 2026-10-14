# VuLink — Connexion QR diagnostic pour Vu+ (bêta 0.1)

Projet indépendant d'IPToSatPro, sur la branche \`feature/vulink-qr-pair-v1\`.

## Fonctionnement
1. Ouvrir **Plugins → VuLink - Connexion QR diagnostic** sur le Vu+ Zero 4K.
2. La TV affiche une **adresse locale** (\`http://192.168.x.x:PORT/\`), un **code éphémère de 12 caractères**, et un QR **si \`qrcode\` (avec Pillow) ou \`qrencode\` est installé**. Rien n'est envoyé à un serveur externe.
3. Sur le téléphone, relié au **même Wi-Fi/LAN**, scanner le QR ou ouvrir l'adresse et saisir le code.
4. Télécharger \`vulink-diagnostic.json\`, puis le joindre à la conversation ChatGPT. **ChatGPT n'accède pas directement au Vu+**.
5. Fermer VuLink sur la TV : le serveur s'arrête immédiatement. Session expirée au bout de 10 minutes même si la fenêtre reste ouverte.

## Installation / vérification
Depuis SSH root sur le Vu+ :

\`\`\`sh
wget -qO /tmp/install-vulink.sh https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/vulink-qr-pair-v1/vulink/install.sh
sh /tmp/install-vulink.sh --check
sh /tmp/install-vulink.sh --install
\`\`\`

Redémarrer **uniquement l'interface Enigma2** depuis le menu OpenATV. Puis ouvrir Plugins → VuLink. En cas de problème :

\`\`\`sh
sh /tmp/install-vulink.sh --rollback
\`\`\`

## Protections
- **Lecture seule** : pas de contrôle IPTV, zap, commandes à distance, FTP, SSH ou port ouvert sur le routeur.
- Écoute temporaire sur l'**IPv4 privée du Vu+ uniquement**, jamais en \`0.0.0.0\`.
- Code aléatoire, 12 caractères (~60 bits), 10 min, 8 échecs/minute par adresse cliente.
- Pas de logs bruts, noms de chaînes, clés IPTV, URLs, credentials, MAC, numéro de série, adresses IP dans l'export.
- Pas d'envoi automatique, uniquement téléchargement par téléphone puis partage manuel.
- Le navigateur du téléphone doit être sur le même LAN ; un pare-feu ou l'isolation des clients Wi-Fi peuvent bloquer l'accès.

## État
**Bêta de diagnostic**, pas un tunnel SSH ou un plugin officiel ChatGPT. Le QR dépend actuellement des outils locaux disponibles ; sinon l'adresse et le code restent utilisables. Avant publication finale, valider le Vu+ Zero 4K réel et le rendu QR/HD-FHD.

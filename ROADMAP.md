# Feuille de route IPToSat Pro — consolidation r70

> **Décision du 9 octobre 2026 : consolidation dans une seule candidate r70-rc1.**
> Les 8 fonctionnalités initialement réparties entre r70, r71 et r72 sont
> regroupées dans `feature/r70-unified-rc` pour préparer une seule prochaine
> version. Lire [r70/STATUS.md](r70/STATUS.md) : certaines fonctions sont
> implémentées comme noyau/politique mais leur intégration matérielle reste
> à valider; aucune publication et aucune fusion sur main ne sont autorisées.
> Les titres r71/r72 ci-dessous décrivent l'ancien phasage, **non** des
> releases distinctes actuellement prévues.


**État : PLANIFIÉ — aucune fonctionnalité ci-dessous n'est annoncée comme implémentée, testée ou publiée.**  
**Référence stable pour la comparaison : r69-beta (1.0.46-r69-beta), Vu+ Zero 4K / OpenATV 8.0.1.**  
**Branche de préparation uniquement.** Ne pas modifier main, update.json, latest-version.txt, download-latest.sh, payload, IPK ou l'installateur avant validation explicite.

## Objectifs non négociables

- Préserver le chemin de zap rapide des chaînes déjà verrouillées (MANUAL LOCK / LOCKED), les succès DVB/5002/4097 et les raccourcis rapides validés.
- Ne pas bloquer le thread GUI Enigma2 : contrôles asynchrones, délais bornés, annulation des anciens travaux quand la chaîne change.
- Ne pas casser les chaînes SAT natives, le fallback SAT/IPTV, la navigation, le son, le timeshift, les relais TS, les picons ou la compatibilité OpenATV 8.0.1.
- Conserver tous les mappings existants, rôles PRIMARY / BACKUP1 / BACKUP2, préférences manuelles et configurations lors de l'installation et du retour arrière.
- Viser 1 à 2 secondes jusqu'à la **première image réelle** pour les chaînes verrouillées lorsque le matériel et le réseau le permettent; il s'agit d'un objectif mesuré, jamais d'une promesse de performance.
- Le nom commercial du flux (SD/HD/FHD/UHD) ne constitue **pas** une preuve de résolution décodée.
- Éviter tout scan exhaustif ou sonde réseau permanente au zap; la santé des sources repose d'abord sur les événements réels de lecture.

## r70 — Fiabilité et Fast Zap (P1)

### [ ] R70-01 — Real Playback Verification
- Séparer les états CONNECTED / TS_READY / VIDEO_DECODED / AUDIO_OBSERVED (si observable) / STABLE, plutôt que considérer IPTV_OK + actual=PENDING comme une preuve d'image affichée.
- Associer toute preuve à l'identité du service, au candidat et à la génération de zap actifs; ignorer les événements retardés de l'ancien décodeur.
- Récolter les timestamps click-to-first-decoded-frame et click-to-stable-playback sans attendre ces métriques pour afficher l'image.
- Ne pas bloquer une chaîne vidéo correcte si l'état audio est techniquement non observable.

### [ ] R70-02 — Black Screen Detector
- Détecter absence de décodage, image figée et absence de nouvelles frames quand l'API et le matériel fournissent des indices fiables.
- Ne pas déclarer une vraie scène sombre/noire comme panne sur la seule luminosité; éviter les faux positifs pendant les transitions, écrans statiques et temps de zapping.
- Recovery borné et annulable; ne jamais provoquer des zaps en boucle.

### [ ] R70-03 — Persistent Manual Lock
- Persister le choix explicite du candidat et du mode après redémarrage GUI et redémarrage complet.
- Priorité au verrouillage manuel sur le classement automatique; ne jamais remplacer silencieusement le candidat verrouillé.
- En cas de panne du candidat verrouillé, proposer un secours temporaire selon la politique existante, sans écraser le lock enregistré.
- Garder des sauvegardes des associations et une restauration vérifiable.

### [ ] R70-04 — Anti-Freeze Watchdog
- Surveiller états transitoires, délais de vérification, timers et tentatives stale sans réveils intensifs ni blocage de l'interface.
- Un seul processus de récupération actif par génération de zap; limites strictes sur retries/cooldowns et aucune répétition infinie SAT_TUNE_FAILED.
- Annuler le watchdog dès qu'un autre service est sélectionné; conserver le SAT natif comme autorité pour les événements tuners.

### [ ] R70-05 — Audio Auto-Recovery
- Vérifier les informations audio réellement disponibles, sans annoncer un son confirmé sur une simple présence de PID ou de piste.
- Proposer une récupération légère et bornée en cas d'absence audio confirmée, y compris pour TOD Event Sports 1–14.
- Ne jamais redémarrer une vidéo stable uniquement parce qu'une preuve audio manque; préserver pistes, langue, AC3/EAC3 et timeshift.

### [ ] R70-06 — Smart Player / récupération ciblée (complément)
- Auditer la mémoire de mode déjà introduite en r68; privilégier uniquement les réussites vérifiées pour **le même flux** (URL/identité non sensible, candidat, codec si disponible).
- Analyser les répétitions 5002 vers DVB et 4097 vers DVB et EOF; favoriser un essai utile plutôt qu'une succession de timeouts.
- Une défaillance temporaire n'efface pas immédiatement un candidat manuel; aucun downgrade silencieux de qualité.
- Corriger l'affichage du message d'installation obsolète « r62 installed » sans toucher au décodage.

**Sortie r70 :** toutes les fonctions testées sur récepteur, jamais simplement inférées de IPTV_OK; pas de régression de zap, timeshift, audio, 4K ni du MANUAL LOCK.

## r71 — Qualité, sources et candidats (P2)

### [ ] R71-01 — Source Health Monitor
- Santé par serveur + candidat, pas une interdiction générale du fournisseur après un échec isolé.
- Collecter en local : succès réel, délai première frame, EOF, échecs répétés, décrochages, délais de retour.
- Fenêtre glissante avec expiration, plafonds de taille et pondération de la fraîcheur; aucune sonde intensive en arrière-plan.
- Ne conserver aucun login, mot de passe, jeton ni URL IPTV contenant des secrets en clair dans les diagnostics exportables.

### [ ] R71-02 — Candidate History
- Historique borné par candidat : dernière lecture vérifiée, mode réussi, qualité observée, incidents, premier affichage et source.
- Corrélation par identité exacte et pays/région; pas de fusion automatique de ANTENA 3 Espagne avec ANTENA 3 Mexique.
- Consultation et remise à zéro par chaîne / source / globale, sans supprimer les locks manuels ni les bouquets.
- En cas de changement d'URL/source, invalider les observations devenues non pertinentes.

### [ ] R71-03 — Smart Mapping et Quality Engine
- Respecter les verrouillages, langue, pays, fournisseur et identité de chaîne avant la résolution annoncée.
- Séparer cible demandée, qualité annoncée, qualité décodée réellement observée et stabilité.
- Éviter la contamination 4K/FHD entre anciens et nouveaux services; le codec/HDR/FPS restent N/A tant qu'aucune preuve fiable n'existe.
- Garder visibles tous les candidats manuels, y compris SD et qualité inconnue, tout en distinguant les candidats sûrs pour l'autosélection UHD.

### [ ] R71-04 — Preview Browser réactif
- Classement asynchrone et cache incrémental, invalidé lorsqu'une source ou le mapping change.
- Conserver filtres, navigation et pluralité des fournisseurs; aucun appel réseau ni calcul de ranking coûteux sur le thread GUI.
- Mesurer les délais déjà observés (36 candidats classés en 5 à 8 secondes) et démontrer l'amélioration sans dégrader la pertinence.

**Sortie r71 :** meilleures décisions sans blacklist abusive, perte de candidats ni navigation ralentie.

## r72 — Diagnostics et mise à jour sûre (P2)

### [ ] R72-01 — Safe Online Update
- Préparer le paquet sur branche de travail / release candidate; publier seulement après tests et accord explicite.
- Vérifier paquet, version, taille, SHA-256, structure OPKG et compatibilité avant proposition d'installation; exiger confirmation utilisateur avant toute modification.
- Sauvegarder le paquet précédent, les réglages, les mappings manuels et les données nécessaires au rollback.
- Après installation, proposer un contrôle post-installation non destructif; faciliter la restauration du paquet précédent en cas d'erreur.
- Aucun rollback automatique risquant d'écraser les données; la procédure de retour doit être vérifiée sur l'appareil.
- Garder update.json, latest-version.txt et download-latest.sh sur la version validée tant que la nouvelle release n'a pas été approuvée.

### [ ] R72-02 — Performance & Health Dashboard
- Afficher état réel du lecteur (CONNECTED/DECODED/STABLE), mode, candidat, résolution mesurée, codec/FPS/HDR/audio si disponible et délai première image.
- Différencier « inconnu » de « 0 », « vérifié » de « estimé », et présenter les journaux sans secrets.
- Exposer un diagnostic court pour dépannage sans ralentir les changements de chaîne.

### [ ] R72-03 — Garde de régression et tests répétables
- Installer des tests hors appareil pour identité de service, races de zap, déduplication metadata, politiques de secours, parsing manifeste et rollback.
- Préserver les garde-fous existants de la voie LOCKED rapide et les vérifications de relais, timeshift et SAT natif.
- Produire un rapport d'acceptation par révision et par scénario.

## Matrice de validation avant release (obligatoire)

1. **Base r69** : capturer au moins 20 zaps sur chaînes verrouillées et non verrouillées, mêmes chaînes/sources et environnement réseau, avec médiane et p95 du temps **télécommande -> première image décodée**; comparer r70, r71 et r72 à cette base.
2. **Performance** : objectif 1–2 s pour LOCKED quand faisable; **pas de détérioration significative** de la médiane ou du p95 par rapport à r69. En cas de ralentissement reproductible, corriger ou retirer la fonctionnalité avant release.
3. **Médias** : vérifier DVB, 5002, 4097, TS, H.264, HEVC, SD/HD/FHD/UHD et transitions 4K vers FHD; comparer le son, y compris TOD Event Sports, AC3/EAC3 et timeshift.
4. **Fiabilité** : tester URL expirée, EOF, no video, coupures réseau, décodeur lent, NAT/relais et zap rapide répété; aucune boucle de fallback ni crash Enigma2.
5. **Mapping** : confirmer persistance et priorité du verrouillage manuel après reboot et upgrade; vérifier les homonymes régionaux et les secours PRIMARY/BACKUP.
6. **OpenATV** : SAT natif, échec tuner, picons, navigation CH+/CH-, EPG, satellites cryptés, changement bouquet, picons de liste et retour depuis chaîne verrouillée.
7. **Interface** : Preview Browser ne fige pas l'UI même avec beaucoup de candidats; pas de nouveaux recalculs coûteux au simple changement de sélection.
8. **Sécurité** : aucun secret IPTV dans logs/exports; aucune réécriture des réglages utilisateur par simple mise à jour; sauvegarde et rollback testés.
9. **Livraison** : installer la candidate sur Vu+ Zero 4K OpenATV 8.0.1, vérifier version OPKG + plugin.py + updater.py + message postinst, consigner anomalies et résultat final.

## Politique stricte de publication

- **Par défaut : HOLD / NOT RELEASED.** Toute fonctionnalité ajoutée au plan est uniquement une spécification, pas du code livré.
- Développement isolé sur branche dédiée, tests automatisés d'abord, tests réels sur le récepteur ensuite.
- Ne pas changer le pointeur de mise à jour en ligne ni annoncer r70/r71/r72 comme disponible avant validation complète.
- Pas de merge sur main, tag, release GitHub, déclenchement de déploiement ni upload d'IPK sans approbation explicite après rapport de tests.
- Si un test récepteur échoue, conserver r69 comme référence et proposer correction ou rollback, jamais un déploiement forcé.

## État initial observé (logs du 8 octobre 2026)

- R69 installée avec OPKG, plugin.py et updater.py cohérents.
- 5002 -> DVB sur Nat Geo Wild HD et Star Action après 1,9 s d'attente.
- EOF sur beIN SPORTS 1 mappée TOD Event Sports 7, puis cooldown; plusieurs SAT_TUNE_FAILED sur la chaîne « 11 » à 30°W.
- Preview ranking : environ 5,08 s pour 36 candidats après r69.
- Contre-exemples qualité/identité : MBC4 SD cible mais 1920×1080 réel; ANTENA 3 pouvant basculer vers source Mexique.
- Aucune de ces observations ne démontre à elle seule un correctif ni ne justifie de modifier automatiquement les mappings manuels.

**Décision demandée pour avancer au-delà de cette feuille de route :** valider le plan, puis autoriser séparément l'implémentation et la publication après tests sur récepteur.

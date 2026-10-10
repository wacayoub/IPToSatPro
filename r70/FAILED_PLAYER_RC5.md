# IPToSat Pro 1.0.46-r70-rc5 — failed decoder recovery (TEST ONLY)

## Pourquoi cette version

Les logs du 10 octobre sur Vu+ Zero 4K montrent :

- M+ LALIGA HD : 5002 sans image décodée après ~1.9 s ; un seul candidat, puis cooldown ~12 s à chaque nouveau zap
- M+ LALIGA 2 : TS prêt sous DVB à 1657 ms; résolution FHD confirmée plus tard (14658 ms). Le deuxième `IPTV_OK` est un contrôle tardif, pas nécessairement un deuxième démarrage
- Museum 4K : confirmé UHD sous 5002 en 2241 ms — **ne pas toucher** au mode UHD déjà efficace
- Mezzo TV : échec de deux tentatives sur la première source ; vidéo DVB confirmée sur la deuxième
- beIN SPORTS 1 : le SAT est mappé vers `TOD EVENT SPORTS 7 FHD (EXCLUS)`, **identité à vérifier manuellement**, car un flux Event 7 n'est pas une preuve de beIN SPORTS 1

La logique native r69-r70 force intentionnellement les locks manuels à leur identité exacte.
Aucun correctif ne doit attribuer automatiquement une autre chaîne de sport à une
source manuelle juste pour obtenir une image.

## Correctif intégré

1. Le **mode Auto** avec une unique méthode ServiceApp autorise maintenant
   une seconde méthode uniquement **après l'échec de la première** :
   `5002→4097` ou `4097→5002` (si disponible).
2. Aucun démarrage supplémentaire lorsqu'un player fonctionne du premier coup.
   Si `_playback_plan` contient déjà un backup (`dvb→5002`, `5002→dvb`),
   on conserve le plan exact.
3. Verrou explicite de lecteur, mode `dvb`, flux sensibles à l'audio/TOD,
   désactivation `retry_failed_stream` et mode non-Auto restent **inchangés**.
4. **Preview Auto-Test** inclut maintenant les sources non mesurées marquées
   `SOURCE` (en plus de `REVIEW`), uniquement après appui volontaire sur
   BLEU/3 et sans sauvegarde de mapping automatique.
5. Le cooldown anti-boucle reste à **12 secondes si toutes les méthodes échouent**.
   Il ne faut pas le réduire aveuglément : cela pourrait répéter un flux mort à
   chaque zap et surcharger le Vu+.
6. Les méthodes du moteur monitor.py, le relais, timeshift, SAT, r70-rc3 FTA
   et les mappings manuels restent inchangés ; seuls des adaptateurs secondaires
   sont ajoutés, avec vérification de non-régression par AST.

## Test réel attendu

1. Sauvegarder les mappings, installer **r70-rc5 TEST ONLY**.
2. Zap sur **M+ LALIGA HD** (2 passages au besoin) puis chercher :
   `IPTV_FAIL`, `RETRY_PLAYER`, `RETRY_NOW`, `IPTV_OK`,
   `RESTORE_SAT`.
3. Si `5002` échoue et si le lecteur est en **Auto** sans exception audio,
   `RETRY_PLAYER ... next_mode=4097` doit apparaître. Le succès de 4097
   dépend réellement de la source ; les tests Python ne prouvent pas l'image.
4. Dans Preview Browser choisir **TREK**, BLEU sur colonne SAT, vérifier que
   les flux `SOURCE`/`REVIEW` sont testés individuellement et qu'aucun
   mauvais candidat n'est verrouillé automatiquement.
5. Pour **beIN SPORTS 1**, inspecter le mapping exact via Preview Browser :
   `TOD EVENT SPORTS 7` ne doit pas être considéré d'office comme
   `beIN SPORTS 1`. Choisir manuellement la véritable chaîne avec image
   et audio vérifiés avant GREEN.
6. Contrôler à nouveau Mezzo, Museum 4K, timeshift et navigation Preview :
   toute régression exige retour vers r70-rc4.

## Statut de release

**HOLD / NON PUBLIÉ** : r70-rc5 n'est pas activée dans Online Update et ne
modifie pas `main`, `update.json` ni les anciens IPK. Tests GitHub CI
uniquement ; confirmation des vrais zaps requise avant publication.

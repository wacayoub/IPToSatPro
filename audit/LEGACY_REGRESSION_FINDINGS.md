# IPToSat Pro — investigation des régressions par version (aucun IPK)

## Décision

**Ne pas construire r70-rc8, ne pas activer Online Update, ne pas écraser les 290 mappings.**
L'utilisateur indique que les versions précédentes fonctionnaient beaucoup mieux.
Il faut retrouver et préserver **le premier comportement connu fonctionnel**.

## Comparaison des packages d'origine

Les archives `payload/r53.b64` à `r69-beta.b64` sont analysées par
`scripts/audit_legacy_r62_r69.py` (nom historique) et
`scripts/audit_legacy_regression_diffs.py`. Les archives r59 et r60 ne sont
pas directement comparables dans cet audit car leur format de `control` ou
leur disposition des fichiers diffère : **ne pas les déclarer validées**.

- **r53–r58 et r61–r69 :** mêmes corps AST pour `normalize_name`,
  `market_from_text`, `infer_sat_context`, `match_score_details`,
  `match_decision`, `_enrich_channel`. TREK FR sur Hot Bird est REVIEW
  (score 87), Tipik `BE:` REJECT (score 1) dans toutes ces archives.
  Ce comportement de scoring était déjà présent ; le correctif FR/BE proposé
  est une nouvelle amélioration et **pas une inversion de régression r70**.
- **r56–r57 et r61 :** modifications de méthode de recherche rapide/index ;
  les contrôles spécifiques aux catalogues existants sont encore à faire.
- **r66 :** modifie `_preview_sat_service_rows` (cache disque SAT) et
  `SatFallbackMonitor._on_start` (préchauffage d'une réplique après échec
  mémorisé). Ce n'est pas le changement principal du panneau droit.
- **r67 : régression potentielle très forte.** Dans
  `SatIPTVBridgePreview._load_selected_sat_candidates`, suppression de :
  `_rank_sat_ref_instant(raw, topn=12, per_server=4)`,
  `_preview_channel_rows(ranked)`, puis
  `self._merge_locked_candidate(key, channels)`. Remplacement par
  `cached=(sat_name, ctx, [], False)` et traitement différé
  `candidate_expand_timer.start(190 ...)`.
  Si le worker ne revient pas, est annulé ou trouve un cache négatif, le
  panneau peut afficher `NO SOURCE` alors que la ligne gauche dit `LOCKED`.
- **r67 :** ajout de `_poll_expanded_candidates` et restriction de l'ajout
  du service SAT courant à `current_crypted is True` au lieu de l'ajouter
  indépendamment de l'accès crypté.
- **r68 :** nouveau `UHD_UNKNOWN_SKIP` dans
  `SatFallbackMonitor._build_candidate_plan`. Nouvel usage de
  `decoder_confirmed_count` dans le tri des sources, et persistance de
  `last_failed_player` dans `_handle_iptv_failure`.
  Cela peut changer le rang et les reprises des candidats, sans modifier
  le score de nom. Un test de playback/qualité réel est nécessaire.
- **r69 :** conserve les changements r67/r68 du Preview et du monitor.
- **r70-rc2→rc7 :** plusieurs wrappers autour du Preview, des timers, du
  player et de la récupération des candidats. Les logs du Vu+ montrent
  `AUTO_RESCUE_START` suivi de `IPTV_OK` tardif et de
  `AUTO_RESCUE_TIMEOUT`; cette course est réelle sous rc7.

## Stratégie de réparation — retour contrôlé au fonctionnement ancien

1. **Référence témoin :** comparer r66 (dernière Preview avec candidat
   instantané + fusion du lock) à r67, sans installer à ce stade.
2. **Fonction prioritaire :** rétablir un premier petit lot de candidats
   et la source LOCKED avant tout classement différé. Ne jamais bloquer la GUI
   sur un classement complet de 72 198 entrées.
3. **Ce qui doit rester différé :** recherche profonde P/B1/B2,
   All Sources et analyse réelle de la qualité, sans cacher le premier lot.
4. **Restauration SAT :** rendre l'acceptation tardive de
   `IPTV_OK` prioritaire sur n'importe quel timer de secours.
5. **r68 quality guard :** mesurer l'effet de `UHD_UNKNOWN_SKIP` et du
   compteur `decoder_confirmed_count` pour les UHD réellement détectées,
   sans les désactiver universellement.
6. **Rejouer la même base :** TREK, Tipik, beIN 1–8, Mezzo, Museum 4K,
   chaîne libre sans signal, et tous les 290 locks existants.
7. **A/B matériel :** seulement après sauvegarde, comparer une version
   *réellement* connue comme bonne sur le même récepteur et la même base de
   chaînes/catalogues. L'utilisateur doit confirmer quelle version fonctionnait
   le mieux ; r66 est une référence de code, pas une stabilité matérielle prouvée.
8. **Conditions de publication :** plus de LOCKED/NO SOURCE,
   plus de récupération pendant `IPTV_OK`, aucune lenteur majeure sur le
   premier affichage, qualité et audio conservés, 100 zaps reproductibles.

## Vérification automatisée

`tests/test_regression_boundaries.py` vérifie directement les méthodes
extraites des IPK r65–r69, notamment la disparition du classement instantané
r67, l'arrivée de la barrière UHD r68 et le suivi d'échecs de lecteurs r68.

**Tous les correctifs restent sur la branche d'audit ; aucune release.**

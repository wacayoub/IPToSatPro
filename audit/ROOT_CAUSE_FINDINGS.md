# Audit racine IPToSat Pro — moteur de candidats r70-rc7

**Statut : STOP RELEASE / aucune nouvelle version.**
Plateforme cible : Vu+ Zero 4K, OpenATV 8.0.1.

## Sources vérifiées
- Capture réelle du Preview Browser (21:00) : SAT beIN SPORTS 6, mapping affiché `[P] TOD EVENT SPORTS 10`, panneau droit `CANDIDATES 0 BEST` et `NO SOURCE`, gauche `LOCKED`.
- Logs réels de 20:57–20:58 : `IPTV_FAIL` puis `AUTO_RESCUE_START` puis parfois `IPTV_OK` sur le *même flux*, et `AUTO_RESCUE_TIMEOUT` ~4 s plus tard.
- Code extrait du véritable IPK rc7 : `monitor.py`, `plugin.py`, `core.py`, `auto_recovery_rc7.py`.
- 100 scénarios d'identité sur le véritable `core.py` publié (beIN 1–20, décalages de numéros, variations FR/AR/PL/FHD, rejets TOD). **100/100 passent**. Cela ne valide NI le catalogue fourni NI le tuner.

## Causes racines confirmées dans le code

### CRITIQUE A — Cache Preview et source verrouillée en désaccord
`plugin.py::_sat_status` marque LOCKED lorsque la configuration manuelle contient un `channel_id`, même si celui-ci n'est plus dans le catalogue. `_load_selected_sat_candidates` recharge indépendamment des lignes candidates éventuellement vides et `complete=True`. Il ne fusionne pas toujours le verrou à l'affichage. La fusion `_merge_locked_candidate` n'est réalisée qu'après classement asynchrone dans `_poll_expanded_candidates`. Un cache négatif complet peut empêcher ce classement.

**Correction préparée sur cette branche audit :** intégration du candidat manuel lorsque son empreinte figure réellement dans le catalogue ; si absent, réactivation de la recherche sans inventer d'URL. **À tester physiquement.**

### CRITIQUE B — Une réussite vidéo tardive n'annule pas le secours déjà lancé
`monitor.py::_handle_iptv_failure` peut déclencher `_schedule_next_candidate` et donc la recherche automatique r70-rc7. Le lecteur peut signaler plus tard `IPTV_OK`, tandis que `auto_recovery_rc7.poll` poursuit son classement ou son timeout, puis appelle `_final_restore_sat` qui coupe la lecture en cours.

**Correction préparée :** annulation de la recherche si `playback_locked` est vrai, contrôle dans le poll et à l'acceptation de la vidéo. Tests automatisés positifs. **Non validée sur Vu+.**

### MAJEUR C — Timeout de classement de quatre secondes
`auto_recovery_rc7.py` utilise `fast_rank_matches_all_servers` après échec, un classement élargi bien plus lourd que la recherche instantanée. Les logs montrent deux `AUTO_RESCUE_TIMEOUT`. Cause de latence interne exacte inconnue sans trace `PREVIEW_RANK_BG`, CPU/tâches concurrentes et temps par fournisseur. On ne peut pas déclarer le moteur optimisé avant ces mesures.

**Correction NON terminée** : instrumentation source/temps et classement par étapes, sans impact sur l'ouverture rapide d'un flux fonctionnel.

### MAJEUR D — Mapping manuel ≠ correspondance certaine
Le moteur respecte un verrou manuel dont le nom IPTV peut être très différent de la chaîne SAT. beIN SPORTS 6 → TOD EVENT SPORTS 10 n'est pas une équivalence confirmée par le nom. Le moteur ne doit ni renommer ni attribuer automatiquement un événement TOD à une autre chaîne beIN. Les 100 tests de score confirment que l'algorithme rejetterait de telles différences de numéro en automatique : ce n'est PAS le score de base qui justifie ce verrou.

### MAJEUR E — SAT 14/240 ne prouve pas un lamedb cassé
La légende `CRYPTED 14 / 240 TV` est un filtre « chaînes cryptées » de Preview sur l'orbite sélectionnée. Les 240 chaînes TV et 14 chaînes déclarées cryptées ne signifient pas nécessairement que 226 services ont disparu. Vérifier l'état crypté réel et le filtre FTA indépendamment.

## Nouveaux faits démontrés par le diagnostic réel (21:11)

### E — TREK : score élevé mais décision REVIEW

- Log du récepteur : `MATCH_BG_DONE sat='TREK' stage=fuzzy rows=19 candidates=0`, `NO_MATCH best='FR TREK FHD' score=87.0 threshold=82`, puis 89 lors d'un nouveau passage.
- Reproduction *avec le core.py original* : `normalize_name('TREK') == normalize_name('FR TREK FHD') == 'trek'`. À 13°E (`orbital_position=130`), le contexte de repli infère IT/PL avec confiance MEDIUM ; un IPTV explicitement FR déclenche `review_reason='explicit IPTV market FR differs from ambiguous SAT market hint IT'`.
- `match_decision(87, details, 82)` retourne `REVIEW` malgré le score : le filtrage de sûreté prend priorité sur le seuil. Le Preview conserve 17 propositions dans ce cas, tandis que SmartMatch en accepte zéro.
- Correctif à concevoir : départager le marché réel d'origine (audio DVB/EPG/métadonnées chaîne) et le simple indice orbital, sans autoriser un flux étranger sur une incompatibilité *forte*. **Pas encore corrigé.**

### F — Tipik : le préfixe de pays `BE:` détruit la correspondance

- Log réel : `NO_MATCH best='BE: Tipik 4K' score=1.0 threshold=82`.
- Reproduction *core.py original* : `normalize_name('Tipik') == 'tipik'`, mais `normalize_name('BE: Tipik 4K') == 'be tipik'`. Le mot `BE` ne fait pas partie des marqueurs géographiques reconnus ; la confiance d'identité tombe à 71 sous le plancher de 72, avec `reject_reason='identity confidence below safe floor'`, pénalité supplémentaire -70 et score final 1.
- Correctif : traiter le préfixe **de pays réellement identifié** `BE:` (et variantes limitées) comme une étiquette, sans supprimer globalement `be` dans les marques. Recalculer la normalisation des catalogues JSONL/snapshot existants après évolution du schéma. **Pas encore corrigé.**

### G — Premier scan SAT lent, cache chaud rapide

- Mesures réelles : `PREVIEW_SAT_COST orbital=130 rows=591 elapsed=4809ms` puis 21 à 35ms à chaud, à nouveau 4868ms pour un scan froid ; `PREVIEW_RANK_BG candidate_count=17 elapsed=729ms` pour TREK.
- Source : `_preview_sat_service_rows` parcourt le catalogue DVB, consulte des données CA statiques par service dont l'état est inconnu puis met en cache les résultats. Le classement IPTV (729ms) est un coût différent de la constitution SAT (~4,8s).
- Correctif : audit d'invalidation de cache par lamedb/lamedb5, traitement différé de l'identification CA non confirmée, et mesures p50/p95 sur les mêmes bouquets avant toute nouvelle candidate. **Pas encore corrigé.**

### Diagnostic lecture seule préparé

```sh
wget -O /tmp/iptosat-explain.sh https://raw.githubusercontent.com/wacayoub/IPToSatPro/audit/r70-rc7-mapping-root-cause/scripts/receiver-explain-matches.sh
sh /tmp/iptosat-explain.sh
```

Ce script lit localement `catalog.jsonl` et `stream_health.json`, n'affiche aucun URL ni secret de fournisseur, et donne pour TREK/Tipik les décisions détaillées, les raisons de refus et le cooldown éventuel. Il ne joue aucun flux et ne touche à aucun mapping.

## Matrice d'audit

Le protocole `scripts/audit_mapping_100.py` suit exactement **100 contrôles**, sans confondre code présent, simulation réussie et tests du récepteur.

- 37 : garde-fous identifiés dans le code, pas nécessairement validés sur Vu+.
- 51 : mesures matérielles manquantes.
- 6 : correctifs préparés, non validés physiquement.
- 6 : problèmes observés dans les captures/logs et encore bloquants.

Le test `tests/test_mapping_corpus_100.py` est différent de cette matrice : il exécute **100 exemples réels de scoring**, mais pas les 100 tests matériels.

## Conditions pour autoriser une future version

1. Le SAT verrouillé affiche son candidat réellement existant, et non NO SOURCE.
2. Un flux rétabli tardivement annule toute récupération et toute restauration SAT.
3. Le classement P/B1/B2 s'achève dans un budget mesuré, même avec un gros catalogue et 100 changements de chaîne.
4. Aucune source TOD d'un autre événement n'est choisie par heuristique.
5. Tests physiques sur beIN 1–8, TREK, Mezzo, UHD, son et timeshift, comparés à r69/rc6/rc7.
6. Aucun crash Enigma2 et aucun ralentissement des mappings déjà fonctionnels.
7. Sauvegarde et retour arrière vérifiés.
8. Aucun paquet nouveau ni fusion `main` / mise à jour en ligne avant levée des anomalies critiques.

## Diagnostic du récepteur (lecture seule)

```sh
wget -O /tmp/iptosat-mapping-audit.sh https://raw.githubusercontent.com/wacayoub/IPToSatPro/audit/r70-rc7-mapping-root-cause/scripts/receiver-audit-mapping.sh
sh /tmp/iptosat-mapping-audit.sh
```

Ce script n'installe rien, ne déclenche aucun scan/ranking et n'imprime aucun URL IPTV ou mot de passe. Il est destiné à compléter les mesures réelles et éviter une version de plus qui ne règle pas la cause.

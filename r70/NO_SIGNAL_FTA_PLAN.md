# IPToSat Pro — mode SAT sans signal pour cryptées + en clair

## Implémentation r70-rc3 — 10 octobre 2026

**Candidate intégrée, non publiée : 1.0.46-r70-rc3.** Le plugin installe un réglage persistant **FTA rescue only when SAT has no signal**, qui est désactivé par défaut. L'ancien réglage *only_crypted* reste à True ; la seule exception suit le garde-fou `r70/no_signal_policy.py`.

- Le moteur de lecture crypté conserve les callbacks, plans et temps de garde existants ; identification d'accès FTA mise en cache par service SAT pour éviter les accès répétés à lamedb pendant le zap.
- Les événements `evTuneFailed` empruntent toujours le traitement différé Enigma2/PAT avant le fallback ; un tuner qui a retrouvé `LOCKED` annule le secours FTA, même si un ancien mapping manuel existe.
- Un état FTA incertain ou un tuner inconnu sans preuve explicite **ne déclenche pas** le fallback.
- Preview Browser affiche les services TV cryptés, en clair et à statut inconnu présents dans lamedb (pour le satellite sélectionné) lorsque ce mode est activé. Les filtres dédiés *Cryptées / En clair / Sans signal* restent à développer ; aucune chaîne radio ni modification de bouquets.
- Tests GitHub Actions : **41/41** (10 politique + 11 adaptateur + 12 sécurité + 8 Preview), génération de l'IPK de test et vérification des modules/version. L'image/les changements de chaînes restent non testés physiquement sur Vu+ Zero 4K.
- Pas de fusion de `main`, pas de modification de `update.json`, pas de publication Online Update. Voir la [Pull Request #2](https://github.com/wacayoub/IPToSatPro/pull/2).


**Prochaine étape proposée : r70-rc3 (PREPARATION / PAS DE RELEASE).**

Branche : `feature/r70-rc3-no-signal`, basée sur la candidate r70-rc2. Les
correctifs de Preview Browser et les temps de zap r70-rc2 restent intacts.

## Audit réel de r69/r70

- `SatFallbackMonitor._on_tune_failed` et `_deferred_tune_failed_fallback`
  traitent déjà `evTuneFailed` / `evNoResources` avec un `eTimer` différé
  (important : ne **jamais** appeler `playService` synchroniquement depuis le
  callback DVB/PAT natif d'OpenATV).
- `_evaluate` possède déjà un chemin « SAT no signal », mais
  `_encrypted_fallback_allowed_once` empêche volontairement toute FTA.
- `cfg.only_crypted` est imposé à `True` au chargement des paramètres,
  dans l'écran Settings et lors du Save : **ne pas le mettre à False globalement.**
  Ce serait un contournement dangereux de la protection FTA et pourrait ralentir
  les zaps cryptés fonctionnels.
- `cfg.instant_mapped=True` court-circuite les vérifications SAT à 45 ms pour
  les locks existants. Dans le nouveau mode, cette optimisation doit être
  suspendue **uniquement** pour les chaînes FTA effectivement identifiées ;
  la voie cryptée déjà validée garde son raccourci.
- Le Preview Browser possède un roster SAT crypté et des chemins distincts
  Manual Mapping/All Sources : il faut ajouter les chaînes en clair dans le
  navigateur **lorsque le mode de secours FTA est activé**, sans modifier
  `lamedb`, les bouquets Enigma2 ou l'ordre des chaînes.

## Règles définitives du nouveau mode

| Type SAT | Frontend/vidéo | Action |
|---|---|---|
| Cryptée | Pas de signal | Logique existante, mapper vers IPTV |
| En clair (FTA) | `LOCKED` + vidéo SAT | Toujours SAT |
| En clair (FTA) | `FAILED` / `LOST_LOCK` + pas de vidéo après grâce | IPTV si option explicite |
| En clair (FTA) | `TUNING` / `ACQUIRING` | Attendre, ne pas basculer |
| En clair (FTA) | `?` + `evTuneFailed` prouvé + pas de vidéo après délai | Secours possible |
| En clair (FTA) | `?` sans événement natif | Ne pas considérer automatiquement absent |
| En clair (FTA) | Écran noir mais tuner `LOCKED` | Conserver SAT; ne pas confondre absence de signal et contenu noir |
| Cryptée `LOCKED` mais décryptage absent | — | Maintenir comportement crypté existant |
| Ref changé pendant le timer | — | Annuler; ne jamais basculer une autre chaîne |

En l'absence de candidat IPTV validé : laisser la référence SAT en place et
afficher « Aucun secours IPTV » ; ne pas choisir une homonyme d'une région
différente et ne pas tourner en boucle.

## UI planifiée

- Settings > Fallback SAT : `Cryptées uniquement` (comportement historique) /
  `Cryptées + FTA sans signal` (nouveau, option explicite, désactivée par défaut).
- Preview Browser : `Toutes TV SAT`, `Cryptées`, `En clair`, `Sans signal`
  (le statut *sans signal* ne doit être affiché que s'il a réellement été mesuré,
  pas inféré d'une simple résolution/EPG inconnue).
- Deux colonnes SAT et IPTV, PRIMARY/B1/B2, All Sources, pages 8/9, mappings
  manuels et tri provider/region conservés.
- Marquer le *type de preuve* (tuner FAILED, evTuneFailed, PTS absent) dans un
  journal diagnostique sans noms de comptes, URL ni secrets IPTV.

## Préparation effectuée

- `r70/no_signal_policy.py` : moteur de décision pur, conservateur, **non
  activé dans le paquet actuellement disponible** ; ne change pas le zap.
- `tests/test_no_signal_policy.py` : tests pour service FTA réellement sans
  signal, tuner sain, phase transitoire, vidéo présente, crypto inconnue,
  expiration de contexte et conservation du Fast Zap crypté.

## Critères avant intégration et IPK

1. Ajouter une option Enigma2 persistante et un écran Settings sans retirer
   `only_crypted=True` pour le mode historique.
2. Brancher le seul garde-fou no-signal FTA dans le chemin *différé* existant,
   en préservant `_native_pat_guard_remaining_ms` et les timers.
3. Réduire *uniquement* le fast path des FTA dans ce mode pour donner au tuner
   le temps de valider LOCKED vs FAILED.
4. Étendre le roster Preview à toutes les chaînes TV SAT (FTA + cryptées), sans
   toucher au moteur de lecture, aux favoris/bouquets, ni aux chaînes radio.
5. Mesurer 20+ zaps sur Vu+ Zero 4K, FTA avec et sans signal, cryptées, FHD/4K,
   timeshift, PAT, verrouillage manuel et absence de boucle lors d'une panne IPTV.
6. Comparer temps médian et p95 cryptés à r70-rc2 ; arrêter le déploiement à
   toute régression du chemin validé.
7. Ne pas fusionner dans `main` ni publier d'Online Update avant essais réels.

**État actuel : candidate r70-rc3 construite et testée hors récepteur ; fonction activable dans Settings après installation, sous réserve de validation matérielle.**

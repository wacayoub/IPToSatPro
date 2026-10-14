# IPToSatPro — R76.9, dossier de passage en version finale
**Audit : 14 octobre 2026 — branche de finalisation sans installation récepteur.**

## Décision
**CANDIDAT FINAL LOGICIEL, NON ENCORE VERSION FINALE CERTIFIÉE.**
La dernière version officiellement publiée via main/update.json reste
`1.0.46-r70-final`. Le candidat R76.9 est
`1.0.46-r76.9-preview-manual-parity-beta`, reconstruit et épinglé en SHA256.
Il n'est pas autorisé de le présenter comme validé sur le Vu+ Zero 4K.

CI R76.9 précédent réussi (14/10/2026):
https://github.com/wacayoub/IPToSatPro/actions/runs/38549976457

Paquet candidat (ancien chemin conservé pour éviter tout redéploiement):
- Base: feature/r769-preview-manual-parity
- Manifest: staging/r76-metrix-preview.update.json
- 458724 octets, SHA256:
  `2fcba58d3a7c56accadcae7c31a19ea84d0ba539b9ea5caab558b6e1cfb13bd8`
- Contrôle du candidat: `python3 scripts/release_r769_gate.py`.
- Le mode `--require-hardware-proof` échoue volontairement sans validation réelle.
- Aucun changement de main/update.json, des mappings, du moteur lecteur ou
  du décodeur n'a été effectué dans cette branche de finalisation.

## Ce qui est consolidé au niveau code/tests
- Preview Browser et Manual Mapping : méthode commune de classement,
  candidat normal 48/16, approfondi 192/64, affichage du score,
  statut BEST/ALT/REJECT et préfixe IPTV original (AR:/FR:/DE:).
- Priorité des feeds régionaux MENA/AR et vérification du fournisseur
  SAT, sans assimiler un candidat au programme réellement en lecture.
- Contexte SAT : ne jamais réutiliser les métadonnées d'une autre référence
  pour justifier un meilleur candidat.
- 11 thèmes choisis depuis Settings; présentation HD/FHD et boutons de
  télécommande existants, layout en deux colonnes conservé.
- Protection du code lecteur, du monitoring, des mappings manuels et
  des paramètres. Sauvegarde avant installation et retour arrière possible.
- Artefact bêta de préproduction reconstruit de manière déterministe.

## Bloquants pour appeler la version « Final »
1. **Aucune preuve de lecture matérielle**: VuLink V3 a accepté la publication de
   commandes dans GitHub mais les deux précédentes demandes de diagnostic du
   14 octobre sont restées sans réponse confirmée. Auth GitHub != agent Vu+ actif.
2. **Performance réelle non prouvée**: cible utilisateur de 1–2 s au changement
   de chaîne; logs antérieurs de ranking 0.9–3.8 s et chaînes sans signal parfois
   7 s. Aucune mesure récente ne permet de déclarer ces incidents clos.
3. **Audio/vidéo non validés**: TOD 1–14, beIN AAC/AC3, UHD/4K,
   écran noir et reprise après zapping nécessitent un test sur récepteur.
4. **TOD King dynamique** est sur une branche séparée et expérimentale,
   non fusionnée au candidat R76.9, pour éviter une régression lecteur.
5. **Chaînes contextuelles**: vérifier le classement en production pour
   Discovery AR face à UK/DE/FR, Disney avec préfixe IPTV, Filmbox One
   inversé, OSN/ABSat, beIN, ainsi que le cas SAT sans signal.

## Matrice de réception requise pour publication stable
| Axe | Vérification matérielle | Critère de validation |
|---|---|---|
| Démarrage | Ouverture plugin, MENU, Settings et choix 11 thèmes | aucun plantage ni freeze |
| Preview | 20 chaînes SAT, comparer Manual Mapping et Preview | meilleurs candidats cohérents, préfixes d'origine |
| AutoLock | 20 cas avec candidats forts + corrections manuelles | verrouillage cohérent sans remplacer une correction |
| Régions | Discovery AR, beIN/OSN, Disney FR, chaînes ABSAT | pas de priorité DE/UK/PL/IT injustifiée |
| Zapping | 20 SAT cryptées, 20 sans signal, retour au canal | mesurer médiane, p95, et écran noir, viser 1–2 s |
| Audio | TOD Events 1–14, beIN, AC3/AAC | audio réel, aucune perte à la reprise |
| Qualité | SD/HD/FHD/4K, relance du même canal | image stable sans saccades |
| Continuité | timeshift, reboot, rafraîchissement catalogue | mappings et verrouillages persistants |
| Sauvegarde | Avant/après installation puis rollback | hashes mappings identiques, code restauré |

La **réussite des seuls tests Python/CI ne remplace pas ces preuves**.

## Installation uniquement si un essai volontaire est décidé
Le script `download-r76-beta.sh` se lance sans argument en **mode check**:
il vérifie le manifest et l'IPK sans installer; `--install` est une
action distincte avec backup, `--rollback` restaure le code sauvegardé.
À ne pas lancer automatiquement via GitHub/VuLink. Le fallback R70
stable reste accessible depuis main.

## Publication stable — préconditions
- Tous les tests CI logiciels sont verts, y compris release_r769_gate.py.
- Un rapport matériel daté démontre vidéo/audio/zapping et absence de
  régression sur Vu+ Zero 4K / OpenATV 8.0.1.
- L'identité du package vérifié est fixée par son SHA256; aucun « final »
  ne doit être publié en réutilisant un artefact modifié.
- Promotion de la version et du manifeste vers main seulement **après**
  validation effective, avec rollback de la précédente version conservé.

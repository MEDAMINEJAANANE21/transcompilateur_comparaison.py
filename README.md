# Documentation : Script de comparaison des transcompilateurs C#

## Vue d'ensemble

Ce script Python compare les sorties C# de l'**ancien transcompilateur** et du **nouveau transcompilateur**, puis génère un rapport exploitable sous trois formats.

Le script parcourt deux dossiers, aligne les fichiers `.cs` portant le même chemin relatif, détecte les fichiers ajoutés, supprimés ou modifiés, et produit :

- un **CSV détaillé** (pour Excel/tableur)
- un **JSON structuré** (pour intégration dans un outil)
- un **rapport Markdown** avec résumé et extraits de diff

***

## Ce que le script compare

Le script ne se limite pas à un simple diff ligne par ligne. Il effectue une analyse à plusieurs niveaux :

### Entités de code

Il extrait les **classes**, **méthodes** et **propriétés** dans chaque fichier `.cs`, puis signale :

- les entités **ajoutées** (présentes dans le nouveau, absentes dans l'ancien)
- les entités **supprimées** (présentes dans l'ancien, absentes dans le nouveau)
- les entités avec une **signature modifiée** (même nom mais type de retour, paramètres ou modificateurs différents)

### Indicateurs de logique

Pour chaque fichier, le script compte les occurrences des mots-clés suivants et remonte les différences :

| Mot-clé | Signification |
|---|---|
| `if` | Branchements conditionnels |
| `for` / `foreach` / `while` | Boucles |
| `switch` | Commutateurs |
| `try` / `catch` | Gestion des erreurs |
| `throw` | Levées d'exceptions |
| `async` / `await` | Programmation asynchrone |
| `return` | Points de retour |

### Motifs de code détectés

Le script détecte aussi la présence ou l'absence de **motifs caractéristiques** et remonte toute transition :

| Motif | Description |
|---|---|
| `try/catch` | Blocs de gestion d'erreurs |
| `throw` | Levée d'exceptions |
| `LINQ` | Requêtes (Select, Where, OrderBy…) |
| `async/await` | Code asynchrone |
| `reflection` | Introspection dynamique |
| `interop` | DllImport, Marshal, COM |
| `ui-events` | Gestionnaires d'événements UI (Click, Load…) |
| `casts` | Conversions de types (`as`, `is`, cast explicite) |
| `null-handling` | Opérateurs `?.`, `??`, `null` |

***

## Comment l'utiliser

### Prérequis

- Python 3.9 ou supérieur
- Aucune dépendance externe (bibliothèques standard uniquement)

### Structure des dossiers attendue

Place les sorties de l'**ancien transcompilateur** dans un dossier et celles du **nouveau** dans un autre, en conservant les **mêmes chemins relatifs** entre les deux :

```
ancien_output/
  Module1.cs
  Forms/Form1.cs
  Controls/UserControl1.cs

nouveau_output/
  Module1.cs
  Forms/Form1.cs
  Controls/UserControl1.cs
```

### Commande

```bash
python compare_transpilers.py --old ancien_output --new nouveau_output --out output/rapport_diff
```

### Paramètres

| Paramètre | Description | Exemple |
|---|---|---|
| `--old` | Dossier avec les sorties de l'ancien transcompilateur | `ancien_output` |
| `--new` | Dossier avec les sorties du nouveau transcompilateur | `nouveau_output` |
| `--out` | Préfixe des fichiers de sortie (sans extension) | `output/rapport_diff` |

### Fichiers générés

```
output/rapport_diff.csv
output/rapport_diff.json
output/rapport_diff.md
```

***

## Format des résultats

### CSV (`rapport_diff.csv`)

Contient une ligne par différence détectée, avec les colonnes suivantes :

| Colonne | Description |
|---|---|
| `file` | Chemin relatif du fichier `.cs` |
| `entity_type` | Type d'entité (`class`, `method`, `property`, `logic`, `file`) |
| `change_type` | Nature du changement (`added`, `removed`, `modified-signature`, `metrics-change`, `text-changed`) |
| `entity` | Identifiant de l'entité (`Classe::Methode(params)`) |
| `old_line` | Numéro de ligne dans l'ancien fichier |
| `new_line` | Numéro de ligne dans le nouveau fichier |
| `old_signature` | Ancienne signature de l'entité |
| `new_signature` | Nouvelle signature de l'entité |
| `notes` | Commentaire automatique (ex. : changements de métriques logiques) |

Ce format est directement exploitable dans **Excel**, **LibreOffice Calc** ou tout outil de tableur pour trier et filtrer les différences par fichier, type ou niveau de risque.

### JSON (`rapport_diff.json`)

Contient trois sections :

- `summary` : un objet par fichier avec son statut (`unchanged`, `changed`, `added`, `removed`) et son nombre de différences
- `differences` : la liste complète des différences, dans le même format que le CSV
- `diff_samples` : des extraits du diff unifié (format `git diff`) pour les fichiers modifiés (limité aux 80 premières lignes par fichier)

### Markdown (`rapport_diff.md`)

Contient :

- un tableau de synthèse (fichiers inchangés, modifiés, ajoutés, supprimés)
- un tableau récapitulatif par fichier
- des extraits de diff pour les 20 premiers fichiers modifiés

***

## Exemple d'interprétation

Voici comment lire une ligne typique du CSV :

```
file                    : Forms/Form1.cs
entity_type             : method
change_type             : removed
entity                  : Form1::Command1_Click()
old_line                : 42
new_line                :
old_signature           : private void Command1_Click(object sender, EventArgs e)
new_signature           :
notes                   :
```

**Interprétation** : la méthode `Command1_Click` existait dans l'ancien transcompilateur (ligne 42 du fichier généré) mais est absente dans le nouveau. Cela peut indiquer que le nouveau transcompilateur nomme différemment les gestionnaires d'événements, ou qu'il génère une structure événementielle différente.

***

## Limites

Ce script effectue une **comparaison structurelle légère** basée sur des expressions régulières. Il est efficace pour :

- détecter les changements de signatures de méthodes/classes/propriétés
- repérer les ajouts et suppressions d'entités
- identifier des changements de motifs logiques visibles dans le code source

Il ne remplace pas une analyse sémantique complète basée sur Roslyn (compilateur C#) ou un vrai AST, et ne garantit pas l'équivalence fonctionnelle entre les deux sorties. Pour aller plus loin, une version utilisant `tree-sitter-c-sharp` ou l'API Roslyn permettrait une analyse encore plus fine.

***

## Roadmap : Version 2 envisagée

La prochaine version pourrait ajouter :

- comparaison des **instructions `using`** (imports)
- comparaison des **appels de méthodes** à l'intérieur des corps de méthodes
- calcul d'un **score de similarité par fichier** (0–100%)
- détection des renommages (méthode renommée mais logique identique)
- export HTML interactif du rapport

# Agent de home staging gratuit pour Claude

Agent de **home staging virtuel** qui marche dans Claude Code et Claude Desktop :
il analyse vos photos de pièces, propose un plan de staging, puis **génère les photos meublées / désencombrées**.

- **Gratuit** : le rendu d'image passe par [Pollinations.ai](https://enter.pollinations.ai), un service open source qui donne des crédits gratuits (modèle d'édition d'image FLUX Kontext).
- **Rien à installer** : serveur MCP en Python 3 pur (aucune dépendance pip).
- **En français** : styles, types de pièce et conseils.

## Contenu

| Fichier | Rôle |
|---|---|
| `home-staging-mcp/server.py` | Serveur MCP : outils `stage_room`, `declutter_room`, `list_styles` |
| `.mcp.json` | Déclare le serveur pour Claude Code (chargé automatiquement dans ce dossier) |
| `.claude/agents/home-stager.md` | Sous-agent « home stager » : diagnostic → plan → rendus → conseils |
| `.claude/skills/home-staging/SKILL.md` | Skill qui se déclenche dès que vous parlez de home staging |

## Installation (5 minutes)

1. **Clé gratuite Pollinations** : créez un compte sur <https://enter.pollinations.ai>, puis générez une clé secrète (`sk_...`).
2. **Exportez-la** dans votre terminal (ou votre `~/.bashrc` / `~/.zshrc`) :
   ```bash
   export POLLINATIONS_API_KEY="sk_votre_cle"
   ```
3. **Claude Code** : clonez ce dépôt, ouvrez-y `claude` et acceptez le serveur MCP `home-staging` quand on vous le propose. Vérifiez avec `/mcp`.

### Claude Desktop (optionnel)

Dans *Réglages → Développeur → Modifier la config* (`claude_desktop_config.json`) :

```json
{
  "mcpServers": {
    "home-staging": {
      "command": "python3",
      "args": ["/chemin/absolu/vers/3DS/home-staging-mcp/server.py"],
      "env": {
        "POLLINATIONS_API_KEY": "sk_votre_cle",
        "HOME_STAGING_OUTPUT_DIR": "/chemin/absolu/vers/mes-rendus"
      }
    }
  }
}
```
Redémarrez Claude Desktop : les outils `stage_room`, `declutter_room` et `list_styles` apparaissent.
(Sous Windows, remplacez `python3` par `python` ou `py`.)

## Utilisation

Dans Claude Code :

```
Fais le home staging des photos du dossier ./photos-appart : appartement haussmannien à vendre, cible jeunes cadres.
```
```
Meuble ./salon-vide.jpg en style scandinave avec un grand canapé d'angle face à la fenêtre.
```
```
Vide ./chambre.jpg puis meuble-la en japandi.
```

Les rendus sont enregistrés dans `staging-output/`.

### Styles disponibles
`scandinave`, `moderne`, `industriel`, `boheme`, `haussmannien`, `japandi`, `classique`, `mediterraneen`, `luxe`, `neutre-vente`. Vous pouvez aussi décrire un style librement.

### Types de pièce
`salon`, `chambre`, `cuisine`, `salle-a-manger`, `bureau`, `salle-de-bain`, `chambre-enfant`, `entree`, `terrasse`, `studio`.

## Réglages (variables d'environnement)

| Variable | Défaut | Rôle |
|---|---|---|
| `POLLINATIONS_API_KEY` | — | Clé gratuite `sk_...` |
| `HOME_STAGING_MODEL` | `black-forest-labs/flux.1-kontext-pro` | Modèle d'édition. Alternatives : `openai/gpt-image-1-mini`, `google/gemini-2.5-flash-image`, `bytedance/seedream-4.0` |
| `HOME_STAGING_OUTPUT_DIR` | `./staging-output` | Dossier des rendus |
| `HOME_STAGING_TIMEOUT` | `180` | Délai max d'un rendu (secondes) |
| `POLLINATIONS_BASE_URL` | `https://gen.pollinations.ai` | URL de l'API |

## Dépannage

- **401/403** : clé absente ou invalide → vérifiez `POLLINATIONS_API_KEY` (clé secrète `sk_`, pas `pk_`).
- **402** : crédits gratuits épuisés pour le moment → réessayez plus tard ou changez de modèle.
- **429/503** : trop de requêtes → patientez quelques secondes.
- **Architecture modifiée sur le rendu** : demandez à Claude de relancer avec un autre `seed` ou des instructions plus précises.

## Rappel légal

En France, une photo d'annonce aménagée virtuellement doit être signalée (ex. « photo non contractuelle – aménagement virtuel »). Le staging virtuel ne doit pas cacher de défauts du bien.

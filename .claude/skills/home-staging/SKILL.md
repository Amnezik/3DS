---
name: home-staging
description: Home staging virtuel de photos de pièces (meubler une pièce vide, changer de style déco, désencombrer, valoriser une annonce immobilière). Utiliser dès que l'utilisateur parle de home staging, staging virtuel, meubler/décorer une photo, ou mettre en valeur un bien à vendre ou louer.
---

# Home staging virtuel

Délègue le travail à l'agent `home-stager` (outil Agent, `subagent_type: home-stager`) en lui passant les chemins/URLs des photos et les préférences de l'utilisateur (style, cible, budget, pièces).

Si l'utilisateur veut juste un rendu rapide, appelle directement les outils MCP :
- `mcp__home-staging__list_styles` — styles et types de pièce disponibles
- `mcp__home-staging__declutter_room` — vider une pièce encombrée
- `mcp__home-staging__stage_room` — meubler/décorer (`image`, `style`, `room_type`, `instructions` en anglais)

Les rendus sont enregistrés dans `staging-output/`. Le service d'images est Pollinations.ai (gratuit, clé gratuite sur https://enter.pollinations.ai à mettre dans `POLLINATIONS_API_KEY`).

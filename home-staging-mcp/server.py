#!/usr/bin/env python3
"""
Home Staging MCP server — gratuit, sans dépendance (stdlib Python uniquement).

Expose à Claude des outils de home staging virtuel :
  - stage_room      : meuble / redécore une photo de pièce (vide ou encombrée)
  - declutter_room  : vide une pièce encombrée (désencombrement virtuel)
  - list_styles     : liste les styles de décoration disponibles

Le rendu d'image passe par l'API Pollinations.ai (modèles d'édition d'image
type FLUX Kontext). Une clé gratuite s'obtient sur https://enter.pollinations.ai
et se passe via la variable d'environnement POLLINATIONS_API_KEY.

Protocole : MCP (JSON-RPC 2.0, une ligne JSON par message sur stdin/stdout).
"""

import base64
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

SERVER_NAME = "home-staging"
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2025-06-18"

API_BASE = os.environ.get("POLLINATIONS_BASE_URL", "https://gen.pollinations.ai").rstrip("/")
API_KEY = os.environ.get("POLLINATIONS_API_KEY", "").strip()
DEFAULT_MODEL = os.environ.get("HOME_STAGING_MODEL", "black-forest-labs/flux.1-kontext-pro")
OUTPUT_DIR = Path(os.environ.get("HOME_STAGING_OUTPUT_DIR", "./staging-output")).expanduser()
TIMEOUT = int(os.environ.get("HOME_STAGING_TIMEOUT", "180"))

STYLES = {
    "scandinave": "Scandinavian style: light oak wood, white and soft grey palette, cozy wool textiles, minimal clean furniture, green plants",
    "moderne": "contemporary modern style: clean lines, neutral palette with black accents, sleek sofa, designer lighting, abstract art",
    "industriel": "industrial loft style: black metal, reclaimed wood, cognac leather sofa, Edison bulbs, concrete-friendly tones",
    "boheme": "bohemian style: rattan and wicker, jute rugs, terracotta and warm earth tones, macrame, many plants, layered textiles",
    "haussmannien": "elegant Parisian Haussmann style: classic moldings respected, velvet armchairs, brass details, marble side tables, chic neutral palette",
    "japandi": "Japandi style: low wooden furniture, beige and muted tones, natural linen, ceramics, calm and uncluttered",
    "classique": "timeless classic style: comfortable upholstered furniture, warm neutral tones, wooden furniture, framed art, table lamps",
    "mediterraneen": "Mediterranean style: white and sand tones, blue accents, natural wood, linen, terracotta pots, olive tree",
    "luxe": "high-end luxury style: velvet and marble, gold accents, statement chandelier, designer furniture, refined neutral palette",
    "neutre-vente": "neutral real-estate staging for sale: broadly appealing neutral furniture, light tones, uncluttered, bright and welcoming",
}

ROOM_TYPES = {
    "salon": "living room",
    "chambre": "bedroom",
    "cuisine": "kitchen",
    "salle-a-manger": "dining room",
    "bureau": "home office",
    "salle-de-bain": "bathroom",
    "chambre-enfant": "kid's bedroom",
    "entree": "entryway",
    "terrasse": "terrace / balcony",
    "studio": "studio apartment (living + sleeping area)",
}

PRESERVE = (
    "Keep the exact same room architecture, camera angle, perspective, walls, windows, doors, "
    "floor, ceiling and lighting direction. Do not move or remove walls, windows or doors. "
    "Photorealistic real-estate photography, natural daylight, realistic scale and shadows, high detail."
)


def log(*args):
    print("[home-staging]", *args, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- #
# Construction des prompts
# --------------------------------------------------------------------------- #
def build_stage_prompt(style, room_type, extra):
    style_desc = STYLES.get(style, style or STYLES["neutre-vente"])
    room_desc = ROOM_TYPES.get(room_type, room_type or "room")
    parts = [
        f"Virtually stage this {room_desc}: furnish and decorate it in a {style_desc}.",
        "Remove any clutter, boxes, debris or personal items first.",
    ]
    if extra:
        parts.append(f"Additional instructions: {extra}.")
    parts.append(PRESERVE)
    return " ".join(parts)


def build_declutter_prompt(extra):
    parts = [
        "Remove all furniture, objects, clutter, boxes and personal items from this room "
        "so that it appears completely empty and clean, ready to be staged.",
    ]
    if extra:
        parts.append(f"Additional instructions: {extra}.")
    parts.append(PRESERVE)
    return " ".join(parts)


# --------------------------------------------------------------------------- #
# Appel API Pollinations
# --------------------------------------------------------------------------- #
def _headers(extra=None):
    h = {"User-Agent": f"{SERVER_NAME}-mcp/{SERVER_VERSION}", "Accept": "application/json, image/*"}
    if API_KEY:
        h["Authorization"] = f"Bearer {API_KEY}"
    if extra:
        h.update(extra)
    return h


def _load_image(image):
    """Retourne (bytes, filename, mime) pour un chemin local, ou None si c'est une URL."""
    if image.startswith(("http://", "https://")):
        return None
    if image.startswith("data:"):
        header, b64 = image.split(",", 1)
        mime = header[5:].split(";")[0] or "image/png"
        return base64.b64decode(b64), "input" + (mimetypes.guess_extension(mime) or ".png"), mime
    path = Path(image).expanduser()
    if not path.is_file():
        raise ValueError(f"Image introuvable : {path}")
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return path.read_bytes(), path.name, mime


def _multipart(fields, files):
    boundary = "----homestaging" + uuid.uuid4().hex
    body = bytearray()
    for name, value in fields.items():
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
    for name, (filename, data, mime) in files.items():
        body += (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\n"
            f"Content-Type: {mime}\r\n\r\n"
        ).encode()
        body += data + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def _http(req):
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read(), resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        detail = e.read()[:600].decode("utf-8", "replace")
        hint = ""
        if e.code in (401, 403):
            hint = " → Clé API manquante ou invalide. Créez une clé gratuite (sk_...) sur https://enter.pollinations.ai et définissez POLLINATIONS_API_KEY."
        elif e.code == 402:
            hint = " → Crédits gratuits épuisés pour l'instant ; réessayez plus tard ou changez de modèle."
        elif e.code in (429, 503):
            hint = f" → Limite de débit atteinte, réessayez dans {e.headers.get('Retry-After', 'quelques')} secondes."
        raise RuntimeError(f"Erreur API Pollinations HTTP {e.code}: {detail}{hint}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"Impossible de joindre {API_BASE} : {e.reason}") from None


def _extract_image(raw, ctype):
    """Gère les réponses brutes (image/*) ou JSON façon OpenAI ({data:[{b64_json|url}]})."""
    if ctype.startswith("image/"):
        return raw, ctype
    try:
        payload = json.loads(raw)
    except ValueError:
        raise RuntimeError(f"Réponse inattendue ({ctype}): {raw[:300]!r}") from None
    items = payload.get("data") or []
    if not items:
        raise RuntimeError(f"Aucune image dans la réponse : {json.dumps(payload)[:400]}")
    item = items[0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"]), "image/png"
    if item.get("url"):
        url = item["url"]
        if url.startswith("data:"):
            data, _, mime = _load_image(url)
            return data, mime
        raw2, ctype2 = _http(urllib.request.Request(url, headers=_headers()))
        return raw2, ctype2 or "image/png"
    raise RuntimeError(f"Format de réponse non reconnu : {json.dumps(item)[:400]}")


def edit_image(image, prompt, model=None, seed=None):
    model = model or DEFAULT_MODEL
    local = _load_image(image)
    if local:
        data, filename, mime = local
        fields = {"prompt": prompt, "model": model, "n": "1"}
        if seed is not None:
            fields["seed"] = str(seed)
        body, ctype = _multipart(fields, {"image": (filename, data, mime)})
        req = urllib.request.Request(
            f"{API_BASE}/v1/images/edits", data=body, method="POST",
            headers=_headers({"Content-Type": ctype}),
        )
    else:
        params = {"model": model, "image": image}
        if seed is not None:
            params["seed"] = str(seed)
        url = f"{API_BASE}/image/{urllib.parse.quote(prompt, safe='')}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers=_headers())
    log(f"appel {req.get_method()} {req.full_url[:120]}… modèle={model}")
    raw, ctype = _http(req)
    return _extract_image(raw, ctype)


def save_image(data, mime, source, suffix, output_path=None):
    ext = mimetypes.guess_extension(mime.split(";")[0].strip()) or ".png"
    if ext == ".jpe":
        ext = ".jpg"
    if output_path:
        out = Path(output_path).expanduser()
    else:
        stem = Path(urllib.parse.urlparse(source).path).stem if source.startswith("http") else Path(source).stem
        stem = (stem or "piece")[:40]
        out = OUTPUT_DIR / f"{stem}-{suffix}-{time.strftime('%Y%m%d-%H%M%S')}{ext}"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    return out.resolve()


# --------------------------------------------------------------------------- #
# Outils MCP
# --------------------------------------------------------------------------- #
IMAGE_PARAM = {
    "type": "string",
    "description": "Chemin local (jpg/png/webp) ou URL publique de la photo de la pièce.",
}
COMMON_PARAMS = {
    "output_path": {"type": "string", "description": "Chemin du fichier résultat (optionnel)."},
    "model": {"type": "string", "description": f"Modèle d'édition Pollinations (défaut : {DEFAULT_MODEL})."},
    "seed": {"type": "integer", "description": "Graine pour varier/reproduire le rendu (optionnel)."},
    "return_image": {"type": "boolean", "description": "Renvoyer l'image à Claude pour qu'il la voie (défaut : true)."},
}

TOOLS = [
    {
        "name": "stage_room",
        "description": (
            "Home staging virtuel : meuble et décore une photo de pièce (vide ou à rafraîchir) "
            "dans un style donné, en conservant l'architecture. Enregistre le rendu sur disque."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "image": IMAGE_PARAM,
                "style": {
                    "type": "string",
                    "description": "Style de décoration : " + ", ".join(STYLES) + " (ou description libre).",
                    "default": "neutre-vente",
                },
                "room_type": {
                    "type": "string",
                    "description": "Type de pièce : " + ", ".join(ROOM_TYPES) + " (ou description libre).",
                    "default": "salon",
                },
                "instructions": {
                    "type": "string",
                    "description": "Consignes supplémentaires en anglais de préférence (ex : 'add a large L-shaped sofa facing the window').",
                },
                "prompt_override": {
                    "type": "string",
                    "description": "Prompt complet à utiliser à la place du prompt généré (expert).",
                },
                **COMMON_PARAMS,
            },
            "required": ["image"],
        },
    },
    {
        "name": "declutter_room",
        "description": "Désencombrement virtuel : retire meubles et objets pour obtenir une pièce vide et propre.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image": IMAGE_PARAM,
                "instructions": {"type": "string", "description": "Consignes supplémentaires (ex : 'keep the kitchen cabinets')."},
                **COMMON_PARAMS,
            },
            "required": ["image"],
        },
    },
    {
        "name": "list_styles",
        "description": "Liste les styles de décoration et types de pièces disponibles.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _image_result(data, mime, out, prompt, return_image):
    content = [{
        "type": "text",
        "text": f"Rendu enregistré : {out}\nPrompt utilisé : {prompt}",
    }]
    if return_image:
        content.append({"type": "image", "data": base64.b64encode(data).decode(), "mimeType": mime.split(";")[0]})
    return {"content": content}


def call_tool(name, args):
    if name == "list_styles":
        lines = ["Styles :"] + [f"- {k} : {v}" for k, v in STYLES.items()]
        lines += ["", "Types de pièce :"] + [f"- {k} ({v})" for k, v in ROOM_TYPES.items()]
        if not API_KEY:
            lines += ["", "⚠ POLLINATIONS_API_KEY n'est pas définie : l'API peut refuser les requêtes. "
                          "Clé gratuite sur https://enter.pollinations.ai"]
        return {"content": [{"type": "text", "text": "\n".join(lines)}]}

    image = args.get("image")
    if not image:
        raise ValueError("Paramètre 'image' requis.")
    if name == "stage_room":
        prompt = args.get("prompt_override") or build_stage_prompt(
            args.get("style", "neutre-vente"), args.get("room_type", "salon"), args.get("instructions"))
        suffix = f"staged-{args.get('style', 'neutre-vente')}".replace(" ", "_")[:40]
    elif name == "declutter_room":
        prompt = build_declutter_prompt(args.get("instructions"))
        suffix = "vide"
    else:
        raise ValueError(f"Outil inconnu : {name}")

    data, mime = edit_image(image, prompt, args.get("model"), args.get("seed"))
    out = save_image(data, mime, image, suffix, args.get("output_path"))
    return _image_result(data, mime, out, prompt, args.get("return_image", True))


# --------------------------------------------------------------------------- #
# Boucle JSON-RPC (MCP stdio)
# --------------------------------------------------------------------------- #
def send(msg):
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def handle(msg):
    method, mid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if mid is None:  # notification
        return
    try:
        if method == "initialize":
            result = {
                "protocolVersion": params.get("protocolVersion", PROTOCOL_VERSION),
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": (
                    "Outils de home staging virtuel. Utilisez list_styles pour voir les styles, "
                    "declutter_room pour vider une pièce, stage_room pour la meubler."
                ),
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            try:
                result = call_tool(params.get("name"), params.get("arguments") or {})
            except Exception as e:  # erreur métier -> visible par Claude
                log("erreur outil:", e)
                result = {"content": [{"type": "text", "text": f"Erreur : {e}"}], "isError": True}
        else:
            send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Méthode inconnue : {method}"}})
            return
        send({"jsonrpc": "2.0", "id": mid, "result": result})
    except Exception as e:
        send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": str(e)}})


def main():
    log(f"démarré (API={API_BASE}, modèle={DEFAULT_MODEL}, clé={'oui' if API_KEY else 'non'})")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON invalide"}})
            continue
        for m in msg if isinstance(msg, list) else [msg]:
            handle(m)


if __name__ == "__main__":
    main()

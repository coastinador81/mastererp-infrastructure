import json
import os
import urllib.error
import urllib.request

NAMES = {
    "gemini": "Gemini",
    "anthropic": "Anthropic",
    "openai": "OpenAI",
}
def choose(provider, effort, prompt):
    if provider in NAMES:
        return provider, "El usuario eligió esta empresa."
    text = prompt.lower()
    if effort == "high" or any(word in text for word in ("analiz", "estrateg", "contrato", "compar", "razon", "plan")):
        return "anthropic", "La petición pide análisis o el esfuerzo es alto."
    if any(word in text for word in ("imagen", "foto", "catálogo", "catalogo", "producto", "ficha", "visual")):
        return "gemini", "La petición trata de producto, catálogo o imagen."
    return "openai", "Es una petición general."


def needs_erp(prompt):
    text = prompt.lower()
    return any(word in text for word in ("erp", "pedido", "correo", "gmail", "factura", "inventario", "catálogo", "catalogo"))


def _post(url, payload, headers):
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def call_provider(provider, effort, prompt):
    if provider == "openai":
        key = os.environ.get("OPENAI_API_KEY", "")
        if not key:
            return None
        model = "gpt-4.1" if effort == "high" else "gpt-4.1-mini"
        data = _post(
            "https://api.openai.com/v1/chat/completions",
            {"model": model, "messages": [{"role": "user", "content": prompt}]},
            {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        return data["choices"][0]["message"]["content"]
    if provider == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            return None
        model = "claude-sonnet-4-5" if effort == "high" else "claude-haiku-4-5"
        data = _post(
            "https://api.anthropic.com/v1/messages",
            {"model": model, "max_tokens": 800, "messages": [{"role": "user", "content": prompt}]},
            {"x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
        )
        return "".join(block.get("text", "") for block in data.get("content", []))
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return None
    model = "gemini-2.5-pro" if effort == "high" else "gemini-2.5-flash"
    data = _post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
        {"contents": [{"parts": [{"text": prompt}]}]},
        {"Content-Type": "application/json"},
    )
    parts = data["candidates"][0]["content"]["parts"]
    return "".join(part.get("text", "") for part in parts)


def answer(event):
    method = ((event.get("requestContext") or {}).get("http") or {}).get("method", "POST")
    if method == "OPTIONS":
        return respond(204, {})
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return respond(400, {"error": "El cuerpo no es JSON."})
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        return respond(400, {"error": "Escribe una petición."})
    if len(prompt) > 3000:
        return respond(400, {"error": "La petición supera el límite de 3000 caracteres."})
    provider, reason = choose(str(body.get("provider") or "auto"), str(body.get("effort") or "medium"), prompt)
    effort = str(body.get("effort") or "medium")
    erp = needs_erp(prompt)
    try:
        text = call_provider(provider, effort, prompt)
    except (urllib.error.URLError, KeyError, TimeoutError, json.JSONDecodeError) as error:
        return respond(200, {
            "provider": provider,
            "providerName": NAMES[provider],
            "reason": reason,
            "erp": erp,
            "reply": f"Elegí {NAMES[provider]}. La consulta no se completó: {error}.",
        })
    if not text:
        extra = " También usaré el punto con UonifyERP para los datos del negocio." if erp else ""
        text = (
            f"Elegí {NAMES[provider]}. {reason}{extra} "
            f"La credencial de {NAMES[provider]} todavía no está cargada, así que el modelo no respondió."
        )
    elif erp:
        text = f"{text}\n\nPara los datos del negocio uso el punto con UonifyERP."
    return respond(200, {
        "provider": provider,
        "providerName": NAMES[provider],
        "reason": reason,
        "erp": erp,
        "reply": text,
    })


def respond(status, payload):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload, ensure_ascii=False),
    }


def lambda_handler(event, context):
    return answer(event)

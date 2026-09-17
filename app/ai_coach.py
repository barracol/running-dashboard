from __future__ import annotations

from datetime import date, timedelta
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import get_settings
from .schemas import CoachFeedback, CoachFeedbackRequest, CoachPlan, CoachPlanRequest


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


class CoachError(RuntimeError):
    pass


def configured() -> bool:
    settings = get_settings()
    return bool(settings.ai_gateway_url or settings.openai_api_key)


def _response_schema() -> dict:
    sports = [
        "running", "trail_running", "walking", "hiking", "cycling", "mountain_biking",
        "swimming", "rowing", "kayaking", "skiing", "cross_country_skiing", "skating",
        "workout", "yoga", "football", "tennis", "other",
    ]
    workout = {
        "type": "object",
        "additionalProperties": False,
        "required": ["planned_date", "activity_type", "title", "target_distance_m", "target_duration_s", "intensity", "notes", "rationale"],
        "properties": {
            "planned_date": {"type": "string"},
            "activity_type": {"type": "string", "enum": sports},
            "title": {"type": "string"},
            "target_distance_m": {"type": ["integer", "null"]},
            "target_duration_s": {"type": ["integer", "null"]},
            "intensity": {"type": "string", "enum": ["recovery", "easy", "moderate", "hard", "long"]},
            "notes": {"type": "string"},
            "rationale": {"type": "string"},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["week_start", "analysis_summary", "load_guidance", "cautions", "workouts"],
        "properties": {
            "week_start": {"type": "string"},
            "analysis_summary": {"type": "string"},
            "load_guidance": {"type": "string"},
            "cautions": {"type": "array", "items": {"type": "string"}},
            "workouts": {"type": "array", "items": workout},
        },
    }


def _prompt(request: CoachPlanRequest, context: dict) -> str:
    end = request.week_start + timedelta(days=6)
    available = ", ".join(request.available_days) if request.available_days else "qualsiasi giorno"
    return f"""Sei un assistente di pianificazione sportiva prudente. Crea una proposta, non una prescrizione medica.

Obiettivo dell'utente: {request.goal}
Istruzioni aggiuntive: {request.instructions or 'nessuna'}
Settimana richiesta: {request.week_start.isoformat()} / {end.isoformat()}
Numero esatto di allenamenti: {request.sessions}
Di cui allenamenti di nuoto: {request.swimming_sessions}
Di cui allenamenti di ciclismo: {request.cycling_sessions}
Giorni disponibili: {available}

Regole:
- usa soltanto date comprese nella settimana richiesta e al massimo una sessione per giorno;
- se sono indicati giorni disponibili, usa esclusivamente quelli;
- pianifica carichi progressivi e lascia recupero adeguato dopo lavori intensi o lunghi;
- considera gare confermate e allenamenti già programmati;
- non diagnosticare condizioni mediche e non inventare dati mancanti;
- se i dati suggeriscono dolore, malattia, affaticamento anomalo o un aumento rischioso, inserisci una cautela e proponi prudenza;
- durata e distanza devono essere realistiche rispetto allo storico, ma possono essere null quando non applicabili;
- scrivi in italiano, con note operative abbastanza precise da poter eseguire la seduta;
- restituisci esattamente {request.sessions} elementi in workouts.
- restituisci esattamente {request.swimming_sessions} elementi con activity_type "swimming";
- restituisci esattamente {request.cycling_sessions} elementi con activity_type "cycling";
- le altre sessioni devono essere discipline diverse da nuoto e ciclismo;

Dati disponibili, minimizzati e già estratti dal database:
{json.dumps(context, ensure_ascii=False, separators=(',', ':'))}
"""


def generate_plan(request: CoachPlanRequest, context: dict) -> CoachPlan:
    settings = get_settings()
    if not settings.ai_gateway_url and not settings.openai_api_key:
        raise CoachError("Coach AI non configurato: manca OPENAI_API_KEY sul server")

    prompt = _prompt(request, context)
    if settings.ai_gateway_url:
        payload = {"input": prompt, "schema_name": "running_week_plan", "schema": _response_schema()}
        endpoint = settings.ai_gateway_url
        headers = {"X-Internal-Token": settings.ai_gateway_token}
    else:
        payload = {
            "model": settings.openai_model, "store": False, "input": prompt,
            "reasoning": {"effort": "medium"},
            "text": {"verbosity": "medium", "format": {
                "type": "json_schema", "name": "running_week_plan", "strict": True, "schema": _response_schema(),
            }},
        }
        endpoint = OPENAI_RESPONSES_URL
        headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    http_request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            **headers,
        },
        method="POST",
    )
    try:
        with urlopen(http_request, timeout=60) as response:
            body = json.loads(response.read())
    except HTTPError as exc:
        try:
            error_body = json.loads(exc.read())
            detail = error_body.get("detail") or error_body.get("error", {}).get("message", "")
        except Exception:
            detail = ""
        raise CoachError(f"Coach AI: {detail or f'errore HTTP {exc.code}'}") from exc
    except (URLError, TimeoutError) as exc:
        raise CoachError("Gateway AI non raggiungibile; controlla la connessione del Raspberry") from exc

    output_text = body.get("output_text")
    if not output_text:
        for item in body.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        output_text = content.get("text")
                        break
    if not output_text:
        raise CoachError("Il Coach AI non ha restituito un piano utilizzabile")
    try:
        plan = CoachPlan.model_validate_json(output_text)
    except Exception as exc:
        raise CoachError("Il piano ricevuto non supera i controlli di validità") from exc
    swimming_count = sum(item.activity_type == "swimming" for item in plan.workouts)
    cycling_count = sum(item.activity_type == "cycling" for item in plan.workouts)
    if plan.week_start != request.week_start or len(plan.workouts) != request.sessions:
        raise CoachError("Il piano ricevuto non rispetta settimana o numero di sessioni richiesti")
    if swimming_count != request.swimming_sessions:
        raise CoachError("Il piano ricevuto non rispetta il numero di sessioni di nuoto richiesto")
    if cycling_count != request.cycling_sessions:
        raise CoachError("Il piano ricevuto non rispetta il numero di sessioni di ciclismo richiesto")
    return plan


def generate_feedback(request: CoachFeedbackRequest, context: dict) -> CoachFeedback:
    settings = get_settings()
    if not settings.ai_gateway_url and not settings.openai_api_key:
        raise CoachError("Coach AI non configurato: manca OPENAI_API_KEY sul server")
    schema = {
        "type": "object", "additionalProperties": False,
        "required": ["answer", "highlights", "cautions"],
        "properties": {
            "answer": {"type": "string"},
            "highlights": {"type": "array", "items": {"type": "string"}},
            "cautions": {"type": "array", "items": {"type": "string"}},
        },
    }
    prompt = f"""Sei un coach sportivo prudente che risponde in italiano a una domanda libera.
Usa esclusivamente i dati forniti. Distingui chiaramente fatti, interpretazioni e dati mancanti.
Puoi commentare continuità, carico, passo, frequenza cardiaca, recupero, peso, gare e scarpe quando pertinenti.
Non formulare diagnosi mediche. Se emergono dolore, malessere o segnali anomali, invita alla prudenza e a rivolgersi a un professionista.
Non creare un piano settimanale salvo richiesta esplicita: rispondi prima di tutto alla domanda.

Domanda: {request.question}

Dati disponibili:
{json.dumps(context, ensure_ascii=False, separators=(',', ':'))}
"""
    if settings.ai_gateway_url:
        payload = {"input": prompt, "schema_name": "running_open_feedback", "schema": schema}
        endpoint = settings.ai_gateway_url
        headers = {"X-Internal-Token": settings.ai_gateway_token}
    else:
        payload = {"model": settings.openai_model, "store": False, "input": prompt,
                   "reasoning": {"effort": "medium"},
                   "text": {"verbosity": "medium", "format": {"type": "json_schema", "name": "running_open_feedback", "strict": True, "schema": schema}}}
        endpoint = OPENAI_RESPONSES_URL
        headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    http_request = Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        with urlopen(http_request, timeout=60) as response:
            body = json.loads(response.read())
    except HTTPError as exc:
        try:
            error_body = json.loads(exc.read()); detail = error_body.get("detail") or error_body.get("error", {}).get("message", "")
        except Exception:
            detail = ""
        raise CoachError(f"Coach AI: {detail or f'errore HTTP {exc.code}'}") from exc
    except (URLError, TimeoutError) as exc:
        raise CoachError("Gateway AI non raggiungibile; controlla la connessione del Raspberry") from exc
    output_text = body.get("output_text")
    if not output_text:
        for item in body.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text": output_text = content.get("text"); break
    if not output_text:
        raise CoachError("Il Coach AI non ha restituito una risposta utilizzabile")
    try:
        return CoachFeedback.model_validate_json(output_text)
    except Exception as exc:
        raise CoachError("La risposta ricevuta non supera i controlli di validità") from exc

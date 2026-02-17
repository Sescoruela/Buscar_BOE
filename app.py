import os
import json
import datetime as dt
import streamlit as st
import requests

st.set_page_config(page_title="Búsqueda + BOE (Gemini)", page_icon="🔎", layout="centered")

# ---------------- Sidebar: API KEY ----------------
st.sidebar.title("⚙️ Configuración")

api_key = st.sidebar.text_input(
    "Google API Key (Gemini)",
    type="password",
    help="Se usa solo en esta sesión (no se guarda en disco)."
)

model_name = st.sidebar.text_input("Modelo", value="gemini-2.5-flash")

if st.sidebar.button("🧹 Borrar chat"):
    st.session_state.clear()
    st.rerun()

st.title("🔎 Chat: Búsqueda + BOE")
st.caption("El agente puede buscar en web (DuckDuckGo) y consultar el BOE (sumario y legislación consolidada).")

if not api_key:
    st.info("Introduce tu API key en la barra lateral para empezar.")
    st.stop()

# Recomendado por la integración: key en variable de entorno
os.environ["GOOGLE_API_KEY"] = api_key

# ---------------- LangChain imports ----------------
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_community.tools import DuckDuckGoSearchResults
from langgraph.prebuilt import create_react_agent

# ---------------- Helpers ----------------
BOE_BASE = "https://boe.es/datosabiertos/api"
TODAY_YYYYMMDD = dt.date.today().strftime("%Y%m%d")


def _get_json(url: str, params: dict | None = None) -> dict:
    """GET JSON with BOE-style Accept header + basic error handling."""
    try:
        r = requests.get(
            url,
            params=params,
            headers={"Accept": "application/json"},
            timeout=20,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"_error": f"{type(e).__name__}: {e}", "_url": url, "_params": params or {}}


def _find_list_of_dicts_with_key(obj, key: str):
    """Find first list[dict] in a nested json that contains 'key'."""
    if isinstance(obj, dict):
        for v in obj.values():
            found = _find_list_of_dicts_with_key(v, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        # If it's a list of dicts and any dict has the key, return it
        if obj and all(isinstance(x, dict) for x in obj) and any(key in x for x in obj):
            return obj
        for item in obj:
            found = _find_list_of_dicts_with_key(item, key)
            if found is not None:
                return found
    return None


def _pretty_truncate(obj, max_chars=4000) -> str:
    s = json.dumps(obj, ensure_ascii=False, indent=2)
    return s if len(s) <= max_chars else s[:max_chars] + "\n... (truncado)"


def _format_normas(normas: list[dict], limit: int = 8) -> str:
    lines = []
    for n in normas[:limit]:
        ident = n.get("identificador") or n.get("id") or n.get("identificador_norma")
        titulo = n.get("titulo") or n.get("title") or "(sin título)"
        fecha = n.get("fecha_actualizacion") or n.get("fecha_disposicion") or n.get("fecha_publicacion") or ""
        api_url = f"{BOE_BASE}/legislacion-consolidada/id/{ident}" if ident else ""
        lines.append(f"- **{titulo}**  \n  id: `{ident}` {('· ' + str(fecha)) if fecha else ''}  \n  api: {api_url}")
    return "\n".join(lines) if lines else "No se encontraron normas en la respuesta."


def _extract_sumario_entries(sumario_json: dict, limit: int = 12) -> list[dict]:
    """
    Intenta extraer entradas de documentos del sumario buscando nodos que contengan:
    - 'titulo'
    - y alguna clave 'url*' (pdf/xml/html)
    """
    out = []

    def rec(x):
        nonlocal out
        if len(out) >= limit:
            return
        if isinstance(x, dict):
            keys_lower = {k.lower(): k for k in x.keys()}
            has_url = any(k.startswith("url") for k in keys_lower.keys())
            if has_url and ("titulo" in keys_lower or "title" in keys_lower or "nombre" in keys_lower):
                titulo = x.get(keys_lower.get("titulo")) or x.get(keys_lower.get("title")) or x.get(keys_lower.get("nombre"))
                urls = {}
                for kl, orig in keys_lower.items():
                    if kl.startswith("url") and isinstance(x.get(orig), str):
                        urls[kl] = x.get(orig)
                out.append({"titulo": titulo or "(sin título)", "urls": urls})
            for v in x.values():
                rec(v)
        elif isinstance(x, list):
            for i in x:
                rec(i)

    rec(sumario_json)
    return out


# ---------------- Tools ----------------
search = DuckDuckGoSearchResults()

@tool
def boe_sumario(fecha: str) -> str:
    """Devuelve el sumario del BOE para una fecha (formato AAAAMMDD). Ej: 20240101"""
    url = f"{BOE_BASE}/boe/sumario/{fecha}"
    data = _get_json(url)
    if "_error" in data:
        return _pretty_truncate(data)

    entries = _extract_sumario_entries(data, limit=12)
    if not entries:
        # fallback: devuelve JSON truncado para que el LLM lo lea
        return _pretty_truncate(data)

    lines = [f"Sumario BOE {fecha} (top {len(entries)} entradas):"]
    for e in entries:
        lines.append(f"- **{e['titulo']}**")
        for k, v in (e.get("urls") or {}).items():
            lines.append(f"  - {k}: {v}")
    return "\n".join(lines)


@tool
def boe_legislacion_buscar(texto: str, from_date: str = "", to_date: str = "", limit: int = 8) -> str:
    """
    Busca normativa en 'Legislación consolidada' del BOE.
    - texto: búsqueda libre (se aplica sobre el campo 'texto' y suele funcionar para contenido general)
    - from_date / to_date: filtro por última actualización (AAAAMMDD), opcional
    - limit: máximo resultados (<=50 recomendado)
    """
    url = f"{BOE_BASE}/legislacion-consolidada"

    # Query en formato JSON (según documentación oficial)
    # Usamos texto:"..." para soportar espacios.
    q = {
        "query": {
            "query_string": {"query": f'texto:"{texto}"'},
            "range": {}
        },
        "sort": []
    }

    params = {
        "limit": int(limit),
        "query": json.dumps(q, ensure_ascii=False),
    }
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date

    data = _get_json(url, params=params)
    if "_error" in data:
        return _pretty_truncate(data)

    # Intento robusto: buscar una lista de dicts que contenga 'identificador'
    normas = _find_list_of_dicts_with_key(data, "identificador") or []
    if normas:
        return _format_normas(normas, limit=int(limit))

    # fallback: JSON truncado
    return _pretty_truncate(data)


tools = [search, boe_sumario, boe_legislacion_buscar]

# ---------------- LLM + Agent ----------------
llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)

system_text = (
    "Eres un asistente útil. Tienes herramientas:\n"
    "1) DuckDuckGoSearchResults: para búsqueda web general.\n"
    "2) boe_sumario(fecha AAAAMMDD): para obtener el sumario diario del BOE.\n"
    "3) boe_legislacion_buscar(texto, from_date, to_date, limit): para buscar normativa en legislación consolidada del BOE.\n\n"
    f"Si el usuario pide 'lo de hoy' y no da fecha, usa por defecto {TODAY_YYYYMMDD}.\n"
    "Primero usa herramientas si te faltan datos, y luego responde con una conclusión clara."
)

# Crear agente con langgraph
agent_executor = create_react_agent(llm, tools)

# ---------------- Simple memory in session_state ----------------
if "history" not in st.session_state:
    st.session_state.history = []

# Render history
for msg in st.session_state.history:
    if isinstance(msg, HumanMessage):
        with st.chat_message("user"):
            st.markdown(msg.content)
    elif isinstance(msg, AIMessage):
        with st.chat_message("assistant"):
            st.markdown(msg.content)

# Input
user_text = st.chat_input("Pregunta (ej: 'Resumen BOE de hoy' o 'Busca normativa sobre alquiler turístico')")

if user_text:
    history_before = st.session_state.history.copy()

    with st.chat_message("user"):
        st.markdown(user_text)

    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            try:
                # Preparar mensajes con system prompt e historial
                messages = [SystemMessage(content=system_text)] + history_before + [HumanMessage(content=user_text)]
                
                # Invocar agente
                result = agent_executor.invoke({"messages": messages})
                
                # Extraer respuesta del agente
                answer = ""
                if "messages" in result:
                    # Buscar el último mensaje del asistente
                    for msg in reversed(result["messages"]):
                        if isinstance(msg, AIMessage):
                            # Extraer contenido del mensaje
                            if isinstance(msg.content, str):
                                answer = msg.content
                                break
                            elif isinstance(msg.content, list):
                                # Si es una lista, buscar elementos de tipo 'text'
                                for item in msg.content:
                                    if isinstance(item, dict) and item.get('type') == 'text':
                                        answer = item.get('text', '')
                                        break
                                if answer:
                                    break
                
                if not answer:
                    answer = "No pude generar una respuesta."
                    
            except Exception as e:
                answer = f"⚠️ Error ejecutando el agente: {type(e).__name__}: {e}"

            st.markdown(answer)

    st.session_state.history = history_before + [
        HumanMessage(content=user_text),
        AIMessage(content=answer),
    ]

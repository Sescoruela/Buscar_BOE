import os
import json
import datetime as dt
import streamlit as st
import requests
from ddgs import DDGS

st.set_page_config(page_title="Chat BOE (Gemini)", page_icon="🔎", layout="wide")

# ---------------- Sidebar: Configuración ----------------
st.sidebar.title("⚙️ Configuración")

api_key = st.sidebar.text_input(
    "Google API Key (Gemini)",
    type="password",
    help="Se usa solo en esta sesión (no se guarda en disco)."
)

model_name = st.sidebar.text_input("Modelo", value="gemini-2.0-flash")

# ---------------- Filtros de Búsqueda ----------------
st.sidebar.subheader("🔍 Opciones de Búsqueda")

tipo_busqueda = st.sidebar.selectbox(
    "Tipo de búsqueda",
    ["💬 Pregunta libre", "📰 Sumario BOE", "📜 Legislación", "🌐 Búsqueda Web"],
    index=0
)

# Opciones adicionales según el tipo de búsqueda
if tipo_busqueda in ["📰 Sumario BOE", "📜 Legislación"]:
    fecha_busqueda = st.sidebar.date_input(
        "Fecha",
        value=dt.date.today(),
        max_value=dt.date.today()
    )
    fecha_str = fecha_busqueda.strftime("%Y%m%d")

if tipo_busqueda == "📜 Legislación":
    st.sidebar.subheader("🏷️ Filtros de Legislación")
    tema_legislacion = st.sidebar.multiselect(
        "Áreas temáticas",
        ["Fiscal", "Laboral", "Civil", "Penal", "Administrativo", "Mercantil", "Constitucional"],
        help="Selecciona áreas de interés"
    )
    
    limite_resultados = st.sidebar.slider("Máximo resultados", 5, 50, 10)

if st.sidebar.button("🧹 Borrar chat"):
    st.session_state.clear()
    st.rerun()

# ---------------- Main Content ----------------
col1, col2 = st.columns([2, 1])

with col1:
    st.title("🔎 Chat: Búsqueda + BOE")

with col2:
    st.info(f"**Modo:** {tipo_busqueda}")

st.caption("Consulta el BOE, busca legislación o haz preguntas con ayuda de IA.")

if not api_key:
    st.warning("⚠️ Introduce tu API key en la barra lateral para empezar.")
    st.stop()

# Recomendado por la integración: key en variable de entorno
os.environ["GOOGLE_API_KEY"] = api_key

# ---------------- LangChain imports ----------------
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# ---------------- Helpers ----------------
BOE_BASE = "https://boe.es/datosabiertos/api"
TODAY_YYYYMMDD = dt.date.today().strftime("%Y%m%d")


def buscar_web(query: str, max_results: int = 5) -> list:
    """Busca en DuckDuckGo"""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            return results
    except Exception as e:
        return [{"error": f"Error en búsqueda: {str(e)}"}]


def obtener_sumario_boe(fecha: str) -> dict:
    """Obtiene el sumario del BOE para una fecha específica"""
    url = f"{BOE_BASE}/boe/sumario/{fecha}"
    try:
        r = requests.get(url, headers={"Accept": "application/json"}, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def buscar_legislacion(texto: str, from_date: str = "", to_date: str = "", limit: int = 10) -> dict:
    """Busca en legislación consolidada del BOE"""
    url = f"{BOE_BASE}/legislacion-consolidada"
    
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
    
    try:
        r = requests.get(url, params=params, headers={"Accept": "application/json"}, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def extraer_documentos_sumario(sumario_json: dict, limit: int = 15) -> list:
    """Extrae documentos del sumario del BOE"""
    documentos = []
    
    def buscar_recursivo(obj):
        if isinstance(obj, dict):
            if "titulo" in obj and any(k.startswith("url") for k in obj.keys()):
                doc = {
                    "titulo": obj.get("titulo", "Sin título"),
                    "seccion": obj.get("seccion", ""),
                    "departamento": obj.get("departamento", ""),
                    "url_pdf": obj.get("urlPdf", ""),
                    "url_html": obj.get("urlHtml", ""),
                }
                documentos.append(doc)
            
            for valor in obj.values():
                buscar_recursivo(valor)
        elif isinstance(obj, list):
            for item in obj:
                buscar_recursivo(item)
    
    buscar_recursivo(sumario_json)
    return documentos[:limit]


def extraer_normas(data: dict, limit: int = 10) -> list:
    """Extrae normas de la respuesta de legislación"""
    normas = []
    
    def buscar_recursivo(obj):
        if isinstance(obj, dict):
            if "identificador" in obj and "titulo" in obj:
                normas.append(obj)
            for v in obj.values():
                buscar_recursivo(v)
        elif isinstance(obj, list):
            for item in obj:
                buscar_recursivo(item)
    
    buscar_recursivo(data)
    return normas[:limit]


def generar_respuesta_con_contexto(pregunta: str, contexto: str, modelo: ChatGoogleGenerativeAI) -> str:
    """Genera una respuesta usando Gemini con contexto"""
    system_prompt = f"""Eres un asistente experto en legislación española y el BOE.
    
Contexto disponible:
{contexto}

Instrucciones:
- Responde de forma clara y concisa
- Usa el contexto proporcionado
- Si el contexto no es suficiente, dilo claramente
- Proporciona enlaces cuando estén disponibles
- Usa formato Markdown para mejor legibilidad
"""
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=pregunta)
    ]
    
    try:
        response = modelo.invoke(messages)
        
        # Extraer contenido
        if isinstance(response.content, str):
            return response.content
        elif isinstance(response.content, list):
            for item in response.content:
                if isinstance(item, dict) and item.get('type') == 'text':
                    return item.get('text', '')
        
        return "No pude generar una respuesta."
    except Exception as e:
        return f"⚠️ Error: {type(e).__name__}: {e}"

# ---------------- Simple memory in session_state ----------------


# ---------------- LLM ----------------
llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)

# ---------------- Historial de Conversación ----------------
if "history" not in st.session_state:
    st.session_state.history = []

# Renderizar historial
for msg in st.session_state.history:
    if isinstance(msg, dict):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# ---------------- Input del Usuario ----------------
placeholder_text = {
    "💬 Pregunta libre": "Ej: '¿Qué normativa existe sobre alquiler turístico?'",
    "📰 Sumario BOE": f"Ej: 'Resume el BOE del {dt.date.today().strftime('%d/%m/%Y')}'",
    "📜 Legislación": "Ej: 'Busca normativa sobre protección de datos'",
    "🌐 Búsqueda Web": "Ej: 'Últimas noticias sobre fiscalidad en España'"
}

user_text = st.chat_input(placeholder_text.get(tipo_busqueda, "Escribe tu pregunta..."))

if user_text:
    # Agregar mensaje del usuario al historial
    with st.chat_message("user"):
        st.markdown(user_text)
    
    st.session_state.history.append({"role": "user", "content": user_text})
    
    # Procesar según el tipo de búsqueda
    with st.chat_message("assistant"):
        with st.spinner("Procesando..."):
            contexto = ""
            respuesta = ""
            
            try:
                if tipo_busqueda == "📰 Sumario BOE":
                    # Obtener sumario del BOE
                    sumario = obtener_sumario_boe(fecha_str)
                    
                    if "error" in sumario:
                        respuesta = f"❌ Error al obtener el sumario: {sumario['error']}"
                    else:
                        documentos = extraer_documentos_sumario(sumario)
                        
                        if documentos:
                            contexto = f"Sumario del BOE del {fecha_busqueda.strftime('%d/%m/%Y')}:\n\n"
                            for i, doc in enumerate(documentos, 1):
                                contexto += f"{i}. **{doc['titulo']}**\n"
                                if doc['seccion']:
                                    contexto += f"   Sección: {doc['seccion']}\n"
                                if doc['departamento']:
                                    contexto += f"   Departamento: {doc['departamento']}\n"
                                if doc['url_pdf']:
                                    contexto += f"   [📄 PDF]({doc['url_pdf']})\n"
                                contexto += "\n"
                            
                            respuesta = generar_respuesta_con_contexto(user_text, contexto, llm)
                        else:
                            respuesta = f"No se encontraron documentos en el sumario del {fecha_busqueda.strftime('%d/%m/%Y')}"
                
                elif tipo_busqueda == "📜 Legislación":
                    # Buscar en legislación
                    # Combinar búsqueda con temas seleccionados
                    query_text = user_text
                    if tema_legislacion:
                        query_text += " " + " ".join(tema_legislacion)
                    
                    resultado = buscar_legislacion(query_text, limit=limite_resultados)
                    
                    if "error" in resultado:
                        respuesta = f"❌ Error al buscar legislación: {resultado['error']}"
                    else:
                        normas = extraer_normas(resultado, limit=limite_resultados)
                        
                        if normas:
                            contexto = f"Resultados de legislación para '{user_text}':\n\n"
                            for i, norma in enumerate(normas, 1):
                                ident = norma.get("identificador", "")
                                titulo = norma.get("titulo", "Sin título")
                                fecha = norma.get("fecha_actualizacion", norma.get("fecha_disposicion", ""))
                                
                                contexto += f"{i}. **{titulo}**\n"
                                contexto += f"   ID: {ident}\n"
                                if fecha:
                                    contexto += f"   Fecha: {fecha}\n"
                                contexto += f"   [🔗 Ver en BOE](https://boe.es/buscar/doc.php?id={ident})\n\n"
                            
                            respuesta = generar_respuesta_con_contexto(user_text, contexto, llm)
                        else:
                            respuesta = "No se encontraron normas que coincidan con la búsqueda."
                
                elif tipo_busqueda == "🌐 Búsqueda Web":
                    # Búsqueda en web
                    resultados = buscar_web(user_text, max_results=5)
                    
                    if resultados and "error" not in resultados[0]:
                        contexto = f"Resultados de búsqueda web para '{user_text}':\n\n"
                        for i, res in enumerate(resultados, 1):
                            titulo = res.get("title", "Sin título")
                            snippet = res.get("body", "")
                            url = res.get("href", "")
                            
                            contexto += f"{i}. **{titulo}**\n"
                            if snippet:
                                contexto += f"   {snippet}\n"
                            if url:
                                contexto += f"   [🔗 Enlace]({url})\n\n"
                        
                        respuesta = generar_respuesta_con_contexto(user_text, contexto, llm)
                    else:
                        respuesta = "No se encontraron resultados en la búsqueda web."
                
                else:  # Pregunta libre
                    # Pregunta directa al modelo sin contexto específico
                    system_prompt = """Eres un asistente experto en legislación española y el BOE (Boletín Oficial del Estado).
                    
Puedes ayudar con:
- Información sobre legislación española
- Interpretación de normativa
- Orientación sobre trámites administrativos
- Explicaciones sobre leyes y regulaciones

Responde de forma clara, concisa y profesional. Si no tienes información suficiente, reconócelo."""
                    
                    messages = [
                        SystemMessage(content=system_prompt),
                        HumanMessage(content=user_text)
                    ]
                    
                    response = llm.invoke(messages)
                    
                    if isinstance(response.content, str):
                        respuesta = response.content
                    elif isinstance(response.content, list):
                        for item in response.content:
                            if isinstance(item, dict) and item.get('type') == 'text':
                                respuesta = item.get('text', '')
                                break
                
                if not respuesta:
                    respuesta = "No pude generar una respuesta."
                    
            except Exception as e:
                respuesta = f"⚠️ Error: {type(e).__name__}: {str(e)}"
            
            st.markdown(respuesta)
    
    # Agregar respuesta al historial
    st.session_state.history.append({"role": "assistant", "content": respuesta})

# ---------------- Footer ----------------
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    st.caption(f"📅 Hoy: {dt.date.today().strftime('%d/%m/%Y')}")

with col2:
    st.caption(f"💬 Mensajes: {len(st.session_state.history)}")

with col3:
    st.caption(f"🔍 Modo: {tipo_busqueda}")

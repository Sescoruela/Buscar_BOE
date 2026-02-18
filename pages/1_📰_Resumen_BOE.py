"""
Página de Streamlit para el Resumen Diario del BOE
"""

import streamlit as st
import datetime as dt
import os
from boe_digest import (
    generar_digest_completo,
    TEMAS_BOE
)

st.set_page_config(
    page_title="MOD-BOE: Resumen Diario",
    page_icon="📰",
    layout="wide"
)

st.title("📰 MOD-BOE: Resumen Inteligente del BOE")
st.markdown("""
Este módulo genera un resumen diario del BOE con:
- ✅ Ingesta automática del BOE
- 🏷️ Filtros por temas (economía, empleo, sanidad, etc.)
- 🤖 Informe ejecutivo generado por IA
- 📧 Envío por email (digest diario)
- 🔗 Enlaces directos a los documentos
""")

# Sidebar: Configuración
st.sidebar.header("⚙️ Configuración")

# API Key para IA
st.sidebar.subheader("🤖 IA para Informe Ejecutivo")
api_key = st.sidebar.text_input(
    "Google API Key (Gemini)",
    type="password",
    help="Necesaria para generar el informe ejecutivo con IA"
)

if api_key:
    os.environ["GOOGLE_API_KEY"] = api_key
    st.sidebar.success("✅ API Key configurada")

# Opciones de informe IA
generar_informe_ia = st.sidebar.checkbox(
    "Generar informe ejecutivo con IA",
    value=True if api_key else False,
    disabled=not api_key,
    help="Genera un informe profesional resumiendo los documentos más relevantes"
)

if generar_informe_ia and not api_key:
    st.sidebar.warning("⚠️ Necesitas una API Key para generar el informe con IA")

# Selección de fecha
fecha_default = dt.date.today()
fecha_seleccionada = st.sidebar.date_input(
    "Fecha del BOE",
    value=fecha_default,
    max_value=dt.date.today()
)
fecha_str = fecha_seleccionada.strftime("%Y%m%d")

# Selección de temas
st.sidebar.subheader("🏷️ Filtrar por temas")
st.sidebar.caption("Selecciona los temas de tu interés (vacío = todos)")

temas_seleccionados = []
for tema in TEMAS_BOE.keys():
    tema_display = tema.replace("_", " ").title()
    if st.sidebar.checkbox(tema_display, value=False, key=f"tema_{tema}"):
        temas_seleccionados.append(tema)

# Configuración de email
st.sidebar.subheader("📧 Envío por Email")
enviar_email = st.sidebar.checkbox("Enviar por email", value=False)

email_config = {}
if enviar_email:
    destinatario = st.sidebar.text_input("Email destinatario", placeholder="tu@email.com")
    
    with st.sidebar.expander("⚙️ Configuración SMTP"):
        remitente = st.text_input("Email remitente", placeholder="tu@gmail.com")
        password = st.text_input("Contraseña de aplicación", type="password", help="Para Gmail, usa una contraseña de aplicación")
        smtp_server = st.text_input("Servidor SMTP", value="smtp.gmail.com")
        smtp_port = st.number_input("Puerto SMTP", value=587, min_value=1, max_value=65535)
        
        email_config = {
            "remitente": remitente,
            "password": password,
            "smtp_server": smtp_server,
            "smtp_port": smtp_port
        }
        
        st.caption("⚠️ Para Gmail: [Crea una contraseña de aplicación](https://myaccount.google.com/apppasswords)")

# Botón para generar resumen
if st.button("🚀 Generar Resumen", type="primary", use_container_width=True):
    with st.spinner("Generando resumen del BOE..."):
        try:
            # Generar digest
            resultado = generar_digest_completo(
                fecha=fecha_str,
                temas_filtro=temas_seleccionados if temas_seleccionados else None,
                enviar_por_email=enviar_email,
                destinatario=destinatario if enviar_email else None,
                config_email=email_config if enviar_email else None
            )
            
            if "error" in resultado:
                st.error(f"❌ Error: {resultado['error']}")
            else:
                # Mostrar estadísticas
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📄 Total Documentos", resultado["total_documentos"])
                with col2:
                    st.metric("🏷️ Categorías", len(resultado["clasificacion"]))
                with col3:
                    if enviar_email and "email" in resultado:
                        if "error" in resultado["email"]:
                            st.metric("📧 Email", "❌ Error")
                        else:
                            st.metric("📧 Email", "✅ Enviado")
                
                # Generar Informe Ejecutivo con IA
                if generar_informe_ia and api_key:
                    st.markdown("---")
                    st.subheader("📋 Informe Ejecutivo")
                    
                    with st.spinner("Generando informe ejecutivo con IA..."):
                        try:
                            from langchain_google_genai import ChatGoogleGenerativeAI
                            from langchain_core.messages import SystemMessage, HumanMessage
                            
                            # Preparar contexto para la IA
                            contexto_docs = []
                            for tema, docs in resultado.get("documentos_por_tema", {}).items():
                                if docs:
                                    contexto_docs.append(f"\n### {tema.replace('_', ' ').upper()}")
                                    for doc in docs[:5]:  # Top 5 por tema
                                        titulo = doc.get("titulo", "Sin título")
                                        seccion = doc.get("seccion", "")
                                        contexto_docs.append(f"- {titulo}")
                                        if seccion:
                                            contexto_docs.append(f"  ({seccion})")
                            
                            contexto_texto = "\n".join(contexto_docs)
                            
                            # Prompt para el informe ejecutivo
                            system_prompt = """Eres un analista experto del BOE (Boletín Oficial del Estado) especializado en generar informes ejecutivos profesionales.

Tu tarea es crear un INFORME EJECUTIVO que:
1. Sea conciso pero completo (máximo 800 palabras)
2. Esté estructurado profesionalmente para presentar a clientes o directivos
3. Destaque los documentos más relevantes y su impacto
4. Use un lenguaje claro y profesional
5. Identifique tendencias o áreas de especial atención

Estructura del informe:
- **RESUMEN EJECUTIVO**: Síntesis en 2-3 párrafos de los aspectos más relevantes
- **ÁREAS CLAVE**: Por cada tema, destaca los documentos más importantes y su impacto potencial
- **CONCLUSIONES Y RECOMENDACIONES**: Análisis de implicaciones y áreas a monitorear

Usa formato Markdown con negritas, listas y secciones claras."""

                            fecha_legible = fecha_seleccionada.strftime("%d de %B de %Y")
                            
                            user_prompt = f"""Genera un informe ejecutivo profesional del BOE del {fecha_legible}.

DATOS DISPONIBLES:
- Total de documentos: {resultado['total_documentos']}
- Categorías analizadas: {', '.join([t.replace('_', ' ') for t in resultado['clasificacion'].keys()])}

DOCUMENTOS POR CATEGORÍA:
{contexto_texto}

Genera el informe ejecutivo siguiendo la estructura solicitada."""

                            llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.3)
                            
                            messages = [
                                SystemMessage(content=system_prompt),
                                HumanMessage(content=user_prompt)
                            ]
                            
                            response = llm.invoke(messages)
                            
                            # Extraer contenido
                            informe = ""
                            if isinstance(response.content, str):
                                informe = response.content
                            elif isinstance(response.content, list):
                                for item in response.content:
                                    if isinstance(item, dict) and item.get('type') == 'text':
                                        informe = item.get('text', '')
                                        break
                            
                            if informe:
                                st.markdown(informe)
                                
                                # Botón para descargar informe
                                col_a, col_b = st.columns(2)
                                with col_a:
                                    st.download_button(
                                        label="📄 Descargar Informe (Markdown)",
                                        data=informe,
                                        file_name=f"informe_ejecutivo_boe_{fecha_str}.md",
                                        mime="text/markdown"
                                    )
                                
                                # Guardar informe en resultado
                                resultado["informe_ejecutivo"] = informe
                            else:
                                st.warning("No se pudo generar el informe ejecutivo")
                                
                        except Exception as e:
                            st.error(f"❌ Error al generar informe con IA: {type(e).__name__}: {str(e)}")
                
                st.markdown("---")
                # Mostrar resumen por categorías
                st.subheader("📊 Resumen por Categorías")
                categorias_df = []
                for tema, cantidad in resultado["clasificacion"].items():
                    categorias_df.append({
                        "Tema": tema.replace("_", " ").title(),
                        "Documentos": cantidad
                    })
                st.dataframe(categorias_df, use_container_width=True, hide_index=True)
                
                # Mostrar HTML generado
                st.subheader("📰 Vista Previa del Resumen")
                st.components.v1.html(resultado["html"], height=800, scrolling=True)
                
                # Botón para descargar HTML
                st.download_button(
                    label="⬇️ Descargar HTML",
                    data=resultado["html"],
                    file_name=f"resumen_boe_{fecha_str}.html",
                    mime="text/html"
                )
                
                # Mostrar resultado del envío de email
                if enviar_email and "email" in resultado:
                    if "error" in resultado["email"]:
                        st.error(f"❌ Error al enviar email: {resultado['email']['error']}")
                    else:
                        st.success(f"✅ {resultado['email']['mensaje']}")
        
        except Exception as e:
            st.error(f"❌ Error inesperado: {type(e).__name__}: {e}")

# Información adicional
with st.expander("ℹ️ Información sobre los temas"):
    st.markdown("""
    ### Categorías disponibles:
    
    - **Economía**: Impuestos, fiscalidad, comercio, empresas
    - **Empleo**: Laboral, trabajo, salarios, contratos
    - **Educación**: Universidad, formación, docencia
    - **Sanidad**: Salud, hospitales, medicamentos
    - **Justicia**: Penal, tribunales, sentencias
    - **Medio Ambiente**: Ecología, clima, sostenibilidad
    - **Vivienda**: Alquileres, hipotecas, inmobiliario
    - **Transporte**: Tráfico, circulación, vehículos
    - **Administración**: Funcionarios, oposiciones, nombramientos
    
    Los documentos se clasifican automáticamente usando palabras clave.
    """)

with st.expander("🔧 Cómo configurar el envío automático"):
    st.markdown("""
    ### Configuración para envío automático diario:
    
    Para recibir el resumen diariamente por email, puedes:
    
    1. **Opción A: Usar GitHub Actions**
       - Crear un workflow que ejecute el script diariamente
       - Configurar las credenciales SMTP como secrets
    
    2. **Opción B: Usar un servidor propio**
       - Configurar un cron job
       - Ejecutar `boe_digest.py` automáticamente
    
    3. **Opción C: Usar Streamlit Cloud + scheduler externo**
       - Configurar un servicio como Zapier o Make
       - Llamar a la API de tu app de Streamlit
    
    ### Para Gmail:
    1. Activa la verificación en 2 pasos
    2. Ve a [Contraseñas de aplicación](https://myaccount.google.com/apppasswords)
    3. Genera una contraseña para "Correo"
    4. Usa esa contraseña en lugar de tu contraseña normal
    """)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #6b7280;'>
    <p>📊 Datos del BOE obtenidos desde la <a href='https://boe.es/datosabiertos/' target='_blank'>API de Datos Abiertos del BOE</a></p>
</div>
""", unsafe_allow_html=True)

"""
Home / Índice de la aplicación BOE
"""

import streamlit as st

st.set_page_config(
    page_title="BOE Tools",
    page_icon="📚",
    layout="wide"
)

st.title("📚 BOE Tools: Suite de Herramientas para el BOE")

st.markdown("""
Bienvenido a la suite completa de herramientas para trabajar con el Boletín Oficial del Estado.

## 🚀 Funcionalidades Disponibles

### 🔎 Chat: Búsqueda + BOE
Asistente inteligente con IA que puede:
- Buscar en internet
- Consultar el sumario diario del BOE
- Buscar en legislación consolidada
- Responder preguntas con contexto

**👉 Ve a la página "Chat BOE" en el menú lateral**

### 📰 MOD-BOE: Resumen Diario Inteligente
Sistema automatizado de análisis del BOE:
- ✅ Ingesta diaria automática
- 🏷️ Clasificación por temas (economía, empleo, sanidad, etc.)
- 📊 Resumen visual con estadísticas
- 🔗 Enlaces directos a documentos PDF/HTML
- 📧 Envío por email (digest diario)

**👉 Ve a la página "Resumen BOE" en el menú lateral**

---

## 📖 Guía Rápida

### Para usar el Chat:
1. Ve a la página "Chat BOE"
2. Introduce tu API Key de Google (Gemini)
3. Pregunta lo que necesites sobre el BOE

### Para generar un resumen:
1. Ve a la página "Resumen BOE"
2. Selecciona la fecha y los temas de interés
3. Opcionalmente configura el envío por email
4. Genera el resumen

---
""", unsafe_allow_html=True)

# Estadísticas rápidas (opcional)
col1, col2, col3 = st.columns(3)

with col1:
    st.info("**🔎 Chat Inteligente**\nBúsqueda con IA")

with col2:
    st.success("**📰 Resumen Diario**\nDigest automatizado")

with col3:
    st.warning("**🔗 API Oficial**\nDatos del BOE")

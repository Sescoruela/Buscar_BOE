"""
MOD-BOE: Módulo de Resumen Diario del BOE
Ingesta diaria del BOE + filtros por temas + resumen con enlaces
"""

import os
import json
import datetime as dt
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Optional

BOE_BASE = "https://boe.es/datosabiertos/api"


# Temas/categorías para filtrado
TEMAS_BOE = {
    "economía": ["impuesto", "fiscal", "tribut", "económ", "financ", "banco", "comercio", "empresa"],
    "empleo": ["laboral", "trabajo", "empleo", "salarial", "pension", "seguridad social", "contrato"],
    "educación": ["educación", "educativo", "universidad", "escolar", "formación", "docente"],
    "sanidad": ["salud", "sanit", "médic", "hospital", "farmac", "medicamento", "epidem"],
    "justicia": ["penal", "procesal", "judicial", "tribunal", "sentencia", "delito", "código"],
    "medio_ambiente": ["ambient", "ecolog", "clima", "sostenib", "residuo", "contamin", "energ"],
    "vivienda": ["vivienda", "alquiler", "inmobiliar", "hipoteca", "arrendamiento", "edificación"],
    "transporte": ["transport", "tráfico", "circulación", "vehículo", "carretera", "ferrocarril"],
    "administración": ["administr", "público", "funcionario", "oposición", "concurso", "nombramiento"],
}


def obtener_sumario_boe(fecha: str) -> Dict:
    """
    Obtiene el sumario del BOE para una fecha específica (formato YYYYMMDD)
    """
    url = f"{BOE_BASE}/boe/sumario/{fecha}"
    try:
        response = requests.get(
            url,
            headers={"Accept": "application/json"},
            timeout=20
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def extraer_documentos(sumario_json: Dict) -> List[Dict]:
    """
    Extrae documentos del sumario del BOE de forma recursiva
    """
    documentos = []
    
    def buscar_recursivo(obj):
        if isinstance(obj, dict):
            # Detectar si es un documento válido
            if "titulo" in obj and any(k.startswith("url") for k in obj.keys()):
                doc = {
                    "titulo": obj.get("titulo", "Sin título"),
                    "seccion": obj.get("seccion", ""),
                    "departamento": obj.get("departamento", ""),
                    "rango": obj.get("rango", ""),
                    "url_pdf": obj.get("urlPdf", ""),
                    "url_html": obj.get("urlHtml", ""),
                    "url_xml": obj.get("urlXml", ""),
                }
                documentos.append(doc)
            
            # Continuar búsqueda recursiva
            for valor in obj.values():
                buscar_recursivo(valor)
                
        elif isinstance(obj, list):
            for item in obj:
                buscar_recursivo(item)
    
    buscar_recursivo(sumario_json)
    return documentos


def clasificar_por_tema(documentos: List[Dict], temas_filtro: Optional[List[str]] = None) -> Dict[str, List[Dict]]:
    """
    Clasifica documentos por temas definidos
    """
    clasificacion = {tema: [] for tema in TEMAS_BOE.keys()}
    clasificacion["otros"] = []
    
    # Si se especifican temas, filtrar solo esos
    if temas_filtro:
        temas_activos = {k: v for k, v in TEMAS_BOE.items() if k in temas_filtro}
    else:
        temas_activos = TEMAS_BOE
    
    for doc in documentos:
        texto_busqueda = f"{doc['titulo']} {doc['seccion']} {doc['departamento']}".lower()
        clasificado = False
        
        for tema, keywords in temas_activos.items():
            if any(keyword in texto_busqueda for keyword in keywords):
                clasificacion[tema].append(doc)
                clasificado = True
                break
        
        if not clasificado:
            clasificacion["otros"].append(doc)
    
    # Eliminar categorías vacías
    return {k: v for k, v in clasificacion.items() if v}


def generar_resumen_html(fecha: str, clasificacion: Dict[str, List[Dict]]) -> str:
    """
    Genera un resumen HTML del BOE con enlaces
    """
    fecha_obj = dt.datetime.strptime(fecha, "%Y%m%d")
    fecha_legible = fecha_obj.strftime("%d de %B de %Y")
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            .header {{
                background-color: #1e3a8a;
                color: white;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 20px;
            }}
            .tema {{
                background-color: white;
                padding: 15px;
                margin-bottom: 15px;
                border-radius: 8px;
                border-left: 4px solid #1e3a8a;
            }}
            .tema h2 {{
                color: #1e3a8a;
                margin-top: 0;
                text-transform: capitalize;
            }}
            .documento {{
                margin-bottom: 15px;
                padding: 10px;
                background-color: #f9fafb;
                border-radius: 4px;
            }}
            .documento h3 {{
                margin: 0 0 8px 0;
                font-size: 16px;
                color: #1f2937;
            }}
            .metadatos {{
                color: #6b7280;
                font-size: 12px;
                margin-bottom: 8px;
            }}
            .enlaces a {{
                display: inline-block;
                margin-right: 10px;
                padding: 4px 12px;
                background-color: #3b82f6;
                color: white;
                text-decoration: none;
                border-radius: 4px;
                font-size: 12px;
            }}
            .enlaces a:hover {{
                background-color: #2563eb;
            }}
            .contador {{
                font-size: 14px;
                color: #6b7280;
                margin-bottom: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📰 Resumen BOE - {fecha_legible}</h1>
            <p>Resumen inteligente del Boletín Oficial del Estado</p>
        </div>
    """
    
    total_docs = sum(len(docs) for docs in clasificacion.values())
    html += f'<p class="contador"><strong>Total de documentos:</strong> {total_docs}</p>'
    
    for tema, documentos in clasificacion.items():
        if not documentos:
            continue
            
        tema_display = tema.replace("_", " ").title()
        html += f"""
        <div class="tema">
            <h2>🏷️ {tema_display} ({len(documentos)} documentos)</h2>
        """
        
        for doc in documentos[:10]:  # Limitar a 10 por tema
            html += f"""
            <div class="documento">
                <h3>{doc['titulo']}</h3>
            """
            
            if doc.get('seccion') or doc.get('departamento'):
                html += f"""
                <div class="metadatos">
                    {f"<strong>Sección:</strong> {doc['seccion']}" if doc.get('seccion') else ""}
                    {" | " if doc.get('seccion') and doc.get('departamento') else ""}
                    {f"<strong>Dpto:</strong> {doc['departamento']}" if doc.get('departamento') else ""}
                </div>
                """
            
            html += '<div class="enlaces">'
            if doc.get('url_pdf'):
                html += f'<a href="{doc["url_pdf"]}" target="_blank">📄 PDF</a>'
            if doc.get('url_html'):
                html += f'<a href="{doc["url_html"]}" target="_blank">🌐 HTML</a>'
            html += '</div></div>'
        
        if len(documentos) > 10:
            html += f'<p class="metadatos">... y {len(documentos) - 10} documentos más en esta categoría</p>'
        
        html += '</div>'
    
    html += """
        <div style="text-align: center; color: #6b7280; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
            <p>Generado automáticamente desde la API de Datos Abiertos del BOE</p>
        </div>
    </body>
    </html>
    """
    
    return html


def enviar_email_digest(
    destinatario: str,
    asunto: str,
    contenido_html: str,
    smtp_server: str = "smtp.gmail.com",
    smtp_port: int = 587,
    remitente: str = None,
    password: str = None
) -> Dict[str, str]:
    """
    Envía el digest por email
    """
    if not remitente or not password:
        return {"error": "Se requiere configurar remitente y password"}
    
    try:
        mensaje = MIMEMultipart("alternative")
        mensaje["Subject"] = asunto
        mensaje["From"] = remitente
        mensaje["To"] = destinatario
        
        parte_html = MIMEText(contenido_html, "html")
        mensaje.attach(parte_html)
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(remitente, password)
            server.send_message(mensaje)
        
        return {"status": "success", "mensaje": f"Email enviado a {destinatario}"}
        
    except Exception as e:
        return {"error": f"Error al enviar email: {type(e).__name__}: {e}"}


def generar_digest_completo(
    fecha: str,
    temas_filtro: Optional[List[str]] = None,
    enviar_por_email: bool = False,
    destinatario: str = None,
    config_email: Dict = None
) -> Dict:
    """
    Función principal que genera el digest completo
    """
    # 1. Obtener sumario
    sumario = obtener_sumario_boe(fecha)
    if "error" in sumario:
        return sumario
    
    # 2. Extraer documentos
    documentos = extraer_documentos(sumario)
    
    # 3. Clasificar por temas
    clasificacion = clasificar_por_tema(documentos, temas_filtro)
    
    # 4. Generar HTML
    html_resumen = generar_resumen_html(fecha, clasificacion)
    
    resultado = {
        "fecha": fecha,
        "total_documentos": len(documentos),
        "clasificacion": {k: len(v) for k, v in clasificacion.items()},
        "documentos_por_tema": clasificacion,  # Agregar documentos completos
        "html": html_resumen
    }
    
    # 5. Enviar por email si se solicita
    if enviar_por_email and destinatario and config_email:
        fecha_obj = dt.datetime.strptime(fecha, "%Y%m%d")
        asunto = f"📰 Resumen BOE - {fecha_obj.strftime('%d/%m/%Y')}"
        
        resultado_email = enviar_email_digest(
            destinatario=destinatario,
            asunto=asunto,
            contenido_html=html_resumen,
            **config_email
        )
        resultado["email"] = resultado_email
    
    return resultado


if __name__ == "__main__":
    # Ejemplo de uso
    hoy = dt.date.today().strftime("%Y%m%d")
    resultado = generar_digest_completo(
        fecha=hoy,
        temas_filtro=["economía", "empleo", "vivienda"]
    )
    print(json.dumps(resultado["clasificacion"], indent=2, ensure_ascii=False))

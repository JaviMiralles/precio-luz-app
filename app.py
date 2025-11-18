import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from matplotlib.lines import Line2D
import matplotlib.font_manager as fm
import io
import urllib.request
from fontTools.ttLib import TTFont
from datetime import datetime, timedelta

# Intentamos importar cairosvg, si falla, desactivamos el modo logo SVG
try:
    import cairosvg
    SVG_AVAILABLE = True
except OSError:
    SVG_AVAILABLE = False
except ImportError:
    SVG_AVAILABLE = False

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Generador de Precios de la Luz", layout="wide")

# --- CONFIGURACIÓN ---
URL_LOGO = "https://noticiastrabajo.huffingtonpost.es/assets/logo-header-ntoD9DGMqO_Z1D8ye2.svg"
URL_FONT_TITULAR = "https://noticiastrabajo.huffingtonpost.es/fonts/tiempos-headline-semibold.woff2"
URL_FONT_TEXTO = "https://noticiastrabajo.huffingtonpost.es/fonts/tiempos-text-regular-v2.woff2"
URL_FONT_BOLD = "https://noticiastrabajo.huffingtonpost.es/fonts/tiempos-text-bold-v2.woff2"
COLOR_BORDE_AZUL = "#6195b7"

@st.cache_resource
def preparar_fuente(url, nombre):
    carpeta = "fonts"
    if not os.path.exists(carpeta): os.makedirs(carpeta)
    ruta_woff2 = os.path.join(carpeta, f"{nombre}.woff2")
    ruta_ttf = os.path.join(carpeta, f"{nombre}.ttf")
    if os.path.exists(ruta_ttf): return fm.FontProperties(fname=ruta_ttf)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(ruta_woff2, 'wb') as out: out.write(response.read())
        font = TTFont(ruta_woff2)
        font.flavor = None
        font.save(ruta_ttf)
        return fm.FontProperties(fname=ruta_ttf)
    except: return None

def cargar_estilos():
    return (preparar_fuente(URL_FONT_TITULAR, "TiemposHeadline"),
            preparar_fuente(URL_FONT_TEXTO, "TiemposText"),
            preparar_fuente(URL_FONT_BOLD, "TiemposTextBold"))

# --- LÓGICA DEL GRÁFICO ---
def generar_grafico(df, tipo_dato, fecha_dato):
    f_titular, f_texto, f_bold = cargar_estilos()
    p_tit = {'fontproperties': f_titular} if f_titular else {'fontweight': 'bold'}
    p_txt = {'fontproperties': f_texto} if f_texto else {}
    p_bld = {'fontproperties': f_bold} if f_bold else {'fontweight': 'bold'}

    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    
    if tipo_dato == "OMIE":
        fecha_obj = datetime.now() + timedelta(days=1)
    else:
        fecha_obj = fecha_dato + timedelta(days=1)
    
    texto_fecha = f"{fecha_obj.day} de {meses[fecha_obj.month - 1]} de {fecha_obj.year}"
    titulo_completo = f'Precio de la luz, {texto_fecha}'
    if tipo_dato == "PVPC":
        titulo_completo += " (PVPC)"

    precios = df['precio'].values
    horas = [f"{h:02d}:00 a {h+1:02d}:00" for h in range(len(precios))]
    if len(precios) > 24:
         precios = precios[:24]
         horas = horas[:24]

    df_p = pd.DataFrame({'h': horas, 'p': precios})
    df_p['rank'] = df_p['p'].rank(method='first')
    df_p['c'] = df_p['rank'].apply(lambda r: '#228000' if r<=8 else ('#f39c12' if r<=16 else '#f81203'))

    fig, ax = plt.subplots(figsize=(7.94, 8.19), dpi=100)
    plt.subplots_adjust(top=0.80, bottom=0.12, left=0.22, right=0.98)

    fig.text(0.5, 0.90, titulo_completo, ha='center', va='center', fontsize=20, color='black', **p_tit)
    fig.text(0.22, 0.82, "Precio (EUR/MWh)", ha='left', va='bottom', fontsize=10, color='#444', **p_txt)

    barras = ax.barh(df_p['h'], df_p['p'], color=df_p['c'], height=0.8)
    ax.invert_yaxis()
    ax.margins(y=0.01)
    ax.set_xlim(0, max(precios) * 1.35)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.grid(axis='y', linestyle=':', alpha=0.5, color='gray')
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)
    
    ax.tick_params(axis='y', length=0, labelsize=10, pad=8)
    for l in ax.get_yticklabels(): 
        if f_texto: l.set_fontproperties(f_texto)
        l.set_fontsize(10)
    ax.set_xticks([])

    for b in barras:
        ax.text(b.get_width() + 1, b.get_y() + b.get_height()/2, 
                f'{b.get_width():.2f}€/MWh', va='center', fontsize=10, color='black', **p_bld)

    y_linea = 0.08
    linea = Line2D([0.05, 0.95], [y_linea, y_linea], transform=fig.transFigure, color=COLOR_BORDE_AZUL, linewidth=3)
    fig.add_artist(linea)
    
    fuente_texto = "Fuente: OMIE" if tipo_dato == "OMIE" else "Fuente: ESIOS (REE)"
    fig.text(0.05, y_linea - 0.025, fuente_texto, ha="left", va="top", fontsize=10, color='gray', **p_txt)

    # LOGICA SEGURA PARA EL LOGO
    logo_insertado = False
    if SVG_AVAILABLE:
        try:
            png = cairosvg.svg2png(url=URL_LOGO)
            img = plt.imread(io.BytesIO(png), format='png')
            ab = AnnotationBbox(OffsetImage(img, zoom=0.30), (0.915, y_linea - 0.04), 
                                frameon=False, xycoords='figure fraction', box_alignment=(1, 0.5))
            ax.add_artist(ab)
            logo_insertado = True
        except Exception:
            logo_insertado = False
    
    if not logo_insertado:
        # Fallback de texto si falla el SVG
        fig.text(0.95, y_linea - 0.025, "NoticiasTrabajo", ha="right", va="top", fontsize=14, color='gray', **p_tit)

    return fig

import os # Asegurar importacion os

# --- INTERFAZ ---
st.title("⚡ Generador de Precios de la Luz")
st.write("Sube tu archivo y obtén el gráfico automáticamente.")

if not SVG_AVAILABLE:
    st.warning("⚠️ Aviso: El sistema de gráficos vectoriales no está disponible en este servidor. Se usará texto en lugar del logo.")

uploaded_file = st.file_uploader("Sube tu archivo Excel (OMIE) o CSV (PVPC)", type=['xls', 'csv', 'xlsx'])

if uploaded_file is not None:
    try:
        filename = uploaded_file.name.lower()
        df_final = None
        tipo_dato = ""
        fecha_ref = datetime.now()

        if filename.endswith('.csv'):
            df = pd.read_csv(uploaded_file, sep=';')
            df.columns = df.columns.str.lower()
            if 'geoname' in df.columns: df = df[df['geoname'] == 'Península']
            if 'datetime' in df.columns and 'value' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'], utc=True).dt.tz_convert('Europe/Madrid')
                df = df.sort_values('datetime')
                df_final = pd.DataFrame({'precio': df['value'].values})
                tipo_dato = "PVPC"
                fecha_ref = df['datetime'].iloc[0]
            else:
                st.error("El CSV no tiene las columnas esperadas (datetime, value).")

        else:
            try: df = pd.read_csv(uploaded_file, skiprows=3, encoding='latin-1', sep=';')
            except: 
                uploaded_file.seek(0)
                df = pd.read_excel(uploaded_file)
            
            col0 = df.columns[0]
            if df[col0].astype(str).str.contains("Precio marginal", na=False, case=False).any():
                fila = df[df[col0].astype(str).str.contains("Precio marginal", na=False, case=False)]
                vals = fila.iloc[0, 1:25].astype(str).str.replace(',', '.', regex=False).values.astype(float)
                df_final = pd.DataFrame({'precio': vals})
                tipo_dato = "OMIE"
            else:
                st.error("No se encontró la fila de 'Precio marginal' en el Excel.")

        if df_final is not None:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.subheader("Gráfico")
                fig = generar_grafico(df_final, tipo_dato, fecha_ref)
                st.pyplot(fig)
                
                buf = io.BytesIO()
                fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
                st.download_button("⬇️ Descargar Imagen", data=buf, file_name="precio_luz.png", mime="image/png")

            with col2:
                st.subheader("Datos (Copiar y Pegar)")
                txt = ""
                for i, p in enumerate(df_final['precio']):
                    ini = f"{i:02d}:00"
                    fin = f"{i+1:02d}:00" if i < 23 else "24:00"
                    # Convertir a float antes de formatear para evitar errores
                    precio_float = float(p)
                    p_fmt = f"{precio_float:.2f}".replace('.', ',')
                    txt += f"{ini} a {fin}: {p_fmt} euros/MWh\n"
                st.text_area("Listado:", value=txt, height=600)

    except Exception as e:
        st.error(f"Ocurrió un error: {e}")
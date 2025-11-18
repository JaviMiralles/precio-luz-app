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
import warnings

# Ignorar advertencias
warnings.filterwarnings("ignore")

# --- CONFIGURACIÓN ---
try:
    import cairosvg
    SVG_AVAILABLE = True
except (OSError, ImportError):
    SVG_AVAILABLE = False

st.set_page_config(page_title="Generador Precios Luz", layout="wide")

# --- RECURSOS ---
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
        with urllib.request.urlopen(req) as response, open(ruta_woff2, 'wb') as out:
            out.write(response.read())
        font = TTFont(ruta_woff2)
        font.flavor = None
        font.save(ruta_ttf)
        return fm.FontProperties(fname=ruta_ttf)
    except: return None

def cargar_estilos():
    return (preparar_fuente(URL_FONT_TITULAR, "TiemposHeadline"),
            preparar_fuente(URL_FONT_TEXTO, "TiemposText"),
            preparar_fuente(URL_FONT_BOLD, "TiemposTextBold"))

import os

# --- PROCESAMIENTO ---
def procesar_archivo(uploaded_file):
    filename = uploaded_file.name.lower()
    df_res = None
    tipo = ""
    fecha_ref = None
    
    try:
        # CASO 1: CSV (PVPC / Red Eléctrica)
        if filename.endswith('.csv'):
            df = pd.read_csv(uploaded_file, sep=';')
            df.columns = df.columns.str.lower()
            
            if 'geoname' in df.columns: 
                df = df[df['geoname'] == 'Península']
            
            if 'datetime' in df.columns and 'value' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'], utc=True).dt.tz_convert('Europe/Madrid')
                df = df.sort_values('datetime')
                
                precios = df['value'].values
                fecha_ref = df['datetime'].iloc[0]
                
                horas = [f"{h:02d}:00 a {h+1:02d}:00" for h in range(len(precios))]
                if len(precios) > 24:
                    precios = precios[:24]
                    horas = horas[:24]
                
                df_res = pd.DataFrame({'h': horas, 'p': precios})
                tipo = "PVPC"
            else:
                return None, "El CSV no tiene columnas 'datetime' y 'value'", None

        # CASO 2: EXCEL (OMIE)
        else:
            try: df = pd.read_csv(uploaded_file, skiprows=3, encoding='latin-1', sep=';')
            except: 
                uploaded_file.seek(0)
                df = pd.read_excel(uploaded_file)
            
            col0 = df.columns[0]
            mask = df[col0].astype(str).str.contains("Precio marginal", na=False, case=False)
            
            if mask.any():
                fila = df[mask]
                vals = fila.iloc[0, 1:25].astype(str).str.replace(',', '.', regex=False).values.astype(float)
                
                horas = [f"{h:02d}:00 a {h+1:02d}:00" for h in range(24)]
                df_res = pd.DataFrame({'h': horas, 'p': vals})
                
                tipo = "OMIE"
                fecha_ref = datetime.now()
            else:
                return None, "No se encontró 'Precio marginal' en el Excel", None

        return df_res, tipo, fecha_ref

    except Exception as e:
        return None, f"Error leyendo archivo: {e}", None

# --- GENERAR GRÁFICO ---
def crear_grafico(df_p, tipo, fecha_base):
    f_tit, f_txt, f_bld = cargar_estilos()
    p_tit = {'fontproperties': f_tit} if f_tit else {'fontweight': 'bold'}
    p_txt = {'fontproperties': f_txt} if f_txt else {}
    p_bld = {'fontproperties': f_bld} if f_bld else {'fontweight': 'bold'}

    if tipo == "OMIE":
        fecha_obj = datetime.now() + timedelta(days=1)
    else:
        fecha_obj = fecha_base 
        
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    
    # Fecha formateada para el Título
    txt_fecha_titulo = f"{fecha_obj.day} de {meses[fecha_obj.month - 1]} de {fecha_obj.year}"

    # Fecha formateada para el Archivo (ej: precio-luz-horas-19-noviembre-2025)
    nombre_mes = meses[fecha_obj.month - 1]
    nombre_archivo_base = f"precio-luz-horas-{fecha_obj.day}-{nombre_mes}-{fecha_obj.year}"
    if tipo == "PVPC":
        nombre_archivo_base += "-pvpc"

    titulo_principal = f"Precio de la luz, {txt_fecha_titulo}"
    texto_footer = "Fuente: OMIE"
    
    if tipo == "PVPC":
        titulo_principal += " (PVPC)"
        texto_footer = "Fuente: Red Eléctrica de España"

    df_p['rank'] = df_p['p'].rank(method='first')
    df_p['c'] = df_p['rank'].apply(lambda r: '#228000' if r<=8 else ('#f39c12' if r<=16 else '#f81203'))

    fig, ax = plt.subplots(figsize=(7.94, 8.19), dpi=100)
    plt.subplots_adjust(top=0.80, bottom=0.12, left=0.22, right=0.98)

    fig.text(0.5, 0.90, titulo_principal, ha='center', va='center', fontsize=20, color='black', **p_tit)
    fig.text(0.22, 0.82, "Precio (EUR/MWh)", ha='left', va='bottom', fontsize=10, color='#444', **p_txt)

    barras = ax.barh(df_p['h'], df_p['p'], color=df_p['c'], height=0.8)
    ax.invert_yaxis()
    ax.margins(y=0.01)
    
    if len(df_p) > 0:
        ax.set_xlim(0, df_p['p'].max() * 1.35)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.grid(axis='y', linestyle=':', alpha=0.5, color='gray')
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)
    
    ax.tick_params(axis='y', length=0, labelsize=10, pad=8)
    ax.set_xticks([])
    
    for l in ax.get_yticklabels():
        if f_txt: l.set_fontproperties(f_txt)
        l.set_fontsize(10)

    for b in barras:
        ax.text(b.get_width() + 1, b.get_y() + b.get_height()/2, 
                f'{b.get_width():.2f}€/MWh', va='center', fontsize=10, color='black', **p_bld)

    y_linea = 0.08
    linea = Line2D([0.05, 0.95], [y_linea, y_linea], transform=fig.transFigure, color=COLOR_BORDE_AZUL, linewidth=3)
    fig.add_artist(linea)
    
    fig.text(0.05, y_linea - 0.025, texto_footer, ha="left", va="top", fontsize=10, color='gray', **p_txt)

    logo_puesto = False
    if SVG_AVAILABLE:
        try:
            png = cairosvg.svg2png(url=URL_LOGO)
            img = plt.imread(io.BytesIO(png), format='png')
            ab = AnnotationBbox(OffsetImage(img, zoom=0.30), (0.915, y_linea - 0.04), 
                                frameon=False, xycoords='figure fraction', box_alignment=(1, 0.5))
            ax.add_artist(ab)
            logo_puesto = True
        except: pass
    
    if not logo_puesto:
        fig.text(0.95, y_linea - 0.025, "NoticiasTrabajo", ha="right", va="top", fontsize=14, color='gray', **p_tit)

    return fig, nombre_archivo_base

# --- APP STREAMLIT ---
st.title("⚡ Generador de Precios de la Luz")
st.markdown("""
Sube tu archivo y la herramienta detectará el formato automáticamente:
* **Excel (.xls/xlsx):** Datos de **OMIE**.
* **CSV (.csv):** Datos de **PVPC**.
""")

archivo = st.file_uploader("Arrastra tu archivo aquí", type=['xls', 'xlsx', 'csv'])

if archivo:
    with st.spinner("Procesando archivo..."):
        df, tipo, fecha = procesar_archivo(archivo)
        
        if df is not None:
            st.success(f"✅ Archivo detectado: **{tipo}**")
            
            col1, col2 = st.columns([1.5, 1])
            
            with col1:
                st.subheader("Vista Previa")
                # Ahora la función devuelve la figura Y el nombre del archivo base
                fig, nombre_base = crear_grafico(df, tipo, fecha)
                st.pyplot(fig)
                
                # --- BOTONES DE DESCARGA (Nombres dinámicos) ---
                
                buf_png = io.BytesIO()
                fig.savefig(buf_png, format='png', dpi=100, bbox_inches='tight')
                
                buf_jpg = io.BytesIO()
                fig.savefig(buf_jpg, format='jpg', dpi=100, bbox_inches='tight', facecolor='white')

                btn_col1, btn_col2 = st.columns(2)
                
                with btn_col1:
                    st.download_button(
                        label="⬇️ Descargar PNG",
                        data=buf_png,
                        file_name=f"{nombre_base}.png",  # <--- NOMBRE DINÁMICO
                        mime="image/png",
                        use_container_width=True
                    )
                
                with btn_col2:
                    st.download_button(
                        label="⬇️ Descargar JPG",
                        data=buf_jpg,
                        file_name=f"{nombre_base}.jpg",  # <--- NOMBRE DINÁMICO
                        mime="image/jpeg",
                        use_container_width=True
                    )

            with col2:
                st.subheader("Código HTML (Lista)")
                st.caption("Copia este código y pégalo en tu editor:")
                
                html_out = "<ul>\n"
                for idx, row in df.iterrows():
                    p_fmt = f"{row['p']:.2f}".replace('.', ',')
                    html_out += f"  <li>{row['h']}: {p_fmt} euros/MWh</li>\n"
                html_out += "</ul>"
                
                st.code(html_out, language="html")
        
        else:
            st.error(f"Error: {tipo}")
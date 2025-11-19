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

# --- LÓGICA DE TEXTOS (COPY) ---
def obtener_momento_dia(hora):
    """Devuelve el momento del día para el texto natural."""
    if 0 <= hora < 7: return "de madrugada"
    if 7 <= hora < 12: return "por la mañana"
    if 12 <= hora < 16: return "a mediodía"
    if 16 <= hora < 21: return "por la tarde"
    return "por la noche"

def generar_texto_rrss(df, tipo, fecha_base):
    # Determinar fecha efectiva
    if tipo == "OMIE":
        fecha_obj = datetime.now() + timedelta(days=1)
    else:
        fecha_obj = fecha_base

    dias_semana = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    
    dia_sem = dias_semana[fecha_obj.weekday()]
    fecha_texto = f"{dia_sem}, {fecha_obj.day} de {meses[fecha_obj.month - 1]} de {fecha_obj.year}"
    
    nombre_mercado = "Mercado Mayorista" if tipo == "OMIE" else "mercado regulado (PVPC)"

    # Datos Min y Max
    row_min = df.loc[df['p'].idxmin()]
    row_max = df.loc[df['p'].idxmax()]
    
    # Extraer hora inicio numérica para el contexto
    hora_min_num = int(row_min['h'].split(':')[0])
    hora_max_num = int(row_max['h'].split(':')[0])
    
    momento_min = obtener_momento_dia(hora_min_num)
    momento_max = obtener_momento_dia(hora_max_num)

    # Formatear precios
    p_min_fmt = f"{row_min['p']:.2f}".replace('.', ',')
    p_max_fmt = f"{row_max['p']:.2f}".replace('.', ',')

    copy = f"""💡 Consulta ya el precio de la luz para este {fecha_texto}, en el {nombre_mercado}.

✅ Las horas más baratas se concentrarán {momento_min}, con el tramo de {row_min['h']} horas marcando el precio más bajo del día: {p_min_fmt} €/MWh.

❌ Las más caras llegarán {momento_max}, especialmente de {row_max['h']} horas, cuando el importe alcanzará los {p_max_fmt} €/MWh.

📊 Si quieres conocer el precio de la luz hora a hora, consulta el siguiente enlace:"""

    return copy

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
    txt_fecha = f"{fecha_obj.day} de {meses[fecha_obj.month - 1]} de {fecha_obj.year}"
    nombre_mes = meses[fecha_obj.month - 1]
    nombre_archivo_base = f"precio-luz-horas-{fecha_obj.day}-{nombre_mes}-{fecha_obj.year}"
    if tipo == "PVPC":
        nombre_archivo_base += "-pvpc"

    titulo_principal = f"Precio de la luz, {txt_fecha}"
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
st.markdown("Calculadora automática de gráficos, listados y comparativas para OMIE y PVPC.")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("1. Subir Archivo")
    uploaded_file = st.file_uploader("Excel (OMIE) o CSV (PVPC)", type=['xls', 'xlsx', 'csv'])
    
    st.divider()
    st.header("2. Comparativa")
    precio_ayer = st.number_input("Precio medio AYER (€/MWh):", min_value=0.0, value=0.0, step=0.01, format="%.2f")
    precio_anio_pasado = st.number_input("Precio medio AÑO PASADO (€/MWh):", min_value=0.0, value=0.0, step=0.01, format="%.2f")

# --- LÓGICA PRINCIPAL ---
if uploaded_file:
    with st.spinner("Procesando..."):
        df, tipo, fecha = procesar_archivo(uploaded_file)
        
        if df is not None:
            st.success(f"✅ Datos de **{tipo}** cargados.")
            
            # --- ESTADÍSTICAS ---
            precio_medio_hoy = df['p'].mean()
            
            # Generar el COPY para RRSS
            copy_rrss = generar_texto_rrss(df, tipo, fecha)

            # --- SECCIÓN DE MÉTRICAS ---
            st.markdown("### 📊 Resumen y Comparativa")
            col_met1, col_met2, col_met3 = st.columns(3)
            col_met1.metric(label="Precio Medio HOY", value=f"{precio_medio_hoy:.2f} €")
            
            if precio_ayer > 0:
                diff_ayer = precio_medio_hoy - precio_ayer
                perc_ayer = (diff_ayer / precio_ayer) * 100
                col_met2.metric("Vs. Ayer", f"{diff_ayer:.2f} €", f"{perc_ayer:.2f} %", delta_color="inverse")
            else: col_met2.info("Falta precio ayer")

            if precio_anio_pasado > 0:
                diff_anio = precio_medio_hoy - precio_anio_pasado
                perc_anio = (diff_anio / precio_anio_pasado) * 100
                col_met3.metric("Vs. Año Pasado", f"{diff_anio:.2f} €", f"{perc_anio:.2f} %", delta_color="inverse")
            else: col_met3.info("Falta precio año pasado")

            st.divider()

            # --- COLUMNAS DE CONTENIDO ---
            col1, col2 = st.columns([1.4, 1])
            
            # COLUMNA 1: GRÁFICO
            with col1:
                st.subheader("1. Gráfico")
                fig, nombre_base = crear_grafico(df, tipo, fecha)
                st.pyplot(fig)
                
                buf_png = io.BytesIO()
                fig.savefig(buf_png, format='png', dpi=100, bbox_inches='tight')
                buf_jpg = io.BytesIO()
                fig.savefig(buf_jpg, format='jpg', dpi=100, bbox_inches='tight', facecolor='white')

                b1, b2 = st.columns(2)
                b1.download_button("⬇️ PNG", buf_png, f"{nombre_base}.png", "image/png", use_container_width=True)
                b2.download_button("⬇️ JPG", buf_jpg, f"{nombre_base}.jpg", "image/jpeg", use_container_width=True)

            # COLUMNA 2: TEXTOS
            with col2:
                # Pestañas para organizar la información
                tab1, tab2 = st.tabs(["📋 Listado HTML", "📱 Copy RRSS"])
                
                with tab1:
                    st.caption("Para pegar en el editor (modo código):")
                    html_out = "<ul>\n"
                    for idx, row in df.iterrows():
                        p_fmt = f"{row['p']:.2f}".replace('.', ',')
                        html_out += f"  <li>{row['h']}: {p_fmt} euros/MWh</li>\n"
                    html_out += "</ul>"
                    st.code(html_out, language="html")

                with tab2:
                    st.caption("Para publicar en redes sociales:")
                    st.text_area("Texto RRSS:", value=copy_rrss, height=350)
        
        else:
            st.error(f"Error: {tipo}")
else:
    st.info("👈 Utiliza el menú de la izquierda para empezar.")
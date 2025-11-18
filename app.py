import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from matplotlib.lines import Line2D
import matplotlib.font_manager as fm
import io
import urllib.request
from fontTools.ttLib import TTFont
import cairosvg
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Generador de Precios de la Luz", layout="wide")

# --- ESTILOS Y FUENTES ---
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

    # Procesar fecha para título
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    
    # Si es OMIE (Excel), sumamos un día porque el dato es para mañana
    # Si es PVPC (CSV), usamos la fecha real del dato + 1 día (predicción)
    if tipo_dato == "OMIE":
        fecha_obj = datetime.now() + timedelta(days=1)
    else:
        fecha_obj = fecha_dato + timedelta(days=1)
    
    texto_fecha = f"{fecha_obj.day} de {meses[fecha_obj.month - 1]} de {fecha_obj.year}"
    titulo_completo = f'Precio de la luz, {texto_fecha}'
    if tipo_dato == "PVPC":
        titulo_completo += " (PVPC)"

    # Procesar Datos
    precios = df['precio'].values
    horas = [f"{h:02d}:00 a {h+1:02d}:00" for h in range(len(precios))]
    if len(precios) > 24:
         precios = precios[:24]
         horas = horas[:24]

    df_p = pd.DataFrame({'h': horas, 'p': precios})
    df_p['rank'] = df_p['p'].rank(method='first')
    df_p['c'] = df_p['rank'].apply(lambda r: '#228000' if r<=8 else ('#f39c12' if r<=16 else '#f81203'))

    # Figura
    fig, ax = plt.subplots(figsize=(7.94, 8.19), dpi=100)
    plt.subplots_adjust(top=0.80, bottom=0.12, left=0.22, right=0.98)

    # Cabecera
    fig.text(0.5, 0.90, titulo_completo, ha='center', va='center', fontsize=20, color='black', **p_tit)
    fig.text(0.22, 0.82, "Precio (EUR/MWh)", ha='left', va='bottom', fontsize=10, color='#444', **p_txt)

    # Barras
    barras = ax.barh(df_p['h'], df_p['p'], color=df_p['c'], height=0.8)
    ax.invert_yaxis()
    ax.margins(y=0.01)
    ax.set_xlim(0, max(precios) * 1.35)

    # Estilos
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

    # Footer
    y_linea = 0.08
    linea = Line2D([0.05, 0.95], [y_linea, y_linea], transform=fig.transFigure, color=COLOR_BORDE_AZUL, linewidth=3)
    fig.add_artist(linea)
    
    fuente_texto = "Fuente: OMIE" if tipo_dato == "OMIE" else "Fuente: ESIOS (REE)"
    fig.text(0.05, y_linea - 0.025, fuente_texto, ha="left", va="top", fontsize=10, color='gray', **p_txt)

    try:
        png = cairosvg.svg2png(url=URL_LOGO)
        img = plt.imread(io.BytesIO(png), format='png')
        ab = AnnotationBbox(OffsetImage(img, zoom=0.30), (0.915, y_linea - 0.04), 
                            frameon=False, xycoords='figure fraction', box_alignment=(1, 0.5))
        ax.add_artist(ab)
    except: pass

    return fig

# --- INTERFAZ DE USUARIO ---
st.title("⚡ Generador de Gráficos de la Luz")
st.write("Sube el archivo de OMIE (Excel) o PVPC (CSV) y obtén el gráfico y la lista de precios al instante.")

uploaded_file = st.file_uploader("Sube tu archivo aquí", type=['xls', 'csv'])

if uploaded_file is not None:
    tipo_dato = None
    df_final = None
    fecha_referencia = None

    try:
        # DETECCIÓN AUTOMÁTICA DE FORMATO
        filename = uploaded_file.name.lower()
        
        if filename.endswith('.csv'):
            # Asumimos PVPC
            df = pd.read_csv(uploaded_file, sep=';')
            df.columns = df.columns.str.lower()
            if 'geoname' in df.columns: df = df[df['geoname'] == 'Península']
            df['datetime'] = pd.to_datetime(df['datetime'], utc=True).dt.tz_convert('Europe/Madrid')
            df = df.sort_values('datetime')
            
            df_final = pd.DataFrame({'precio': df['value'].values})
            tipo_dato = "PVPC"
            fecha_referencia = df['datetime'].iloc[0]

        else:
            # Asumimos OMIE (Excel/XLS pero a veces es texto)
            try: df = pd.read_csv(uploaded_file, skiprows=3, encoding='latin-1', sep=';')
            except: 
                uploaded_file.seek(0)
                df = pd.read_excel(uploaded_file)
            
            col0 = df.columns[0]
            fila = df[df[col0].astype(str).str.contains("Precio marginal", na=False, case=False)]
            precios = fila.iloc[0, 1:25].astype(str).str.replace(',', '.', regex=False).values.astype(float)
            
            df_final = pd.DataFrame({'precio': precios})
            tipo_dato = "OMIE"
            fecha_referencia = datetime.now() # OMIE no trae fecha limpia en la fila, asumimos hoy para mañana

        # MOSTRAR RESULTADOS
        if df_final is not None:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.subheader(f"Gráfico ({tipo_dato})")
                fig = generar_grafico(df_final, tipo_dato, fecha_referencia)
                st.pyplot(fig)
                
                # Botón descargar imagen
                img_buffer = io.BytesIO()
                fig.savefig(img_buffer, format='png', dpi=100, bbox_inches='tight')
                st.download_button("⬇️ Descargar Imagen", data=img_buffer, file_name="precio_luz.png", mime="image/png")

            with col2:
                st.subheader("Listado de Precios")
                texto_lista = ""
                for i, p in enumerate(df_final['precio']):
                    h_inicio = f"{i:02d}:00"
                    h_fin = f"{i+1:02d}:00" if i < 23 else "24:00"
                    precio_fmt = f"{p:.2f}".replace('.', ',')
                    texto_lista += f"{h_inicio} a {h_fin}: {precio_fmt} euros/MWh\n"
                
                st.text_area("Copia y pega esto:", value=texto_lista, height=600)

    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")
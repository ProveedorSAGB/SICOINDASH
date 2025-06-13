import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import unicodedata
import gspread

#================================================== CONFIGURACIÓN INICIAL DE LA PÁGINA ======================================================================================
st.set_page_config(page_title="Sistema Control Interno", layout="wide", page_icon="📊")


###########################################################
###########################################################
###########################################################
# DESCARGA Y CONSOLIDACIÓN DE INFORMACIÓN PARA LA APP
###########################################################
###########################################################
###########################################################



#==================================== CARGA DE DATOS DESDE GOOGLE SHEETS CON CACHEO ============================================
@st.cache_resource(ttl="5m", show_spinner="Descargando datos actualizados desde Sheets...")
def descargar_y_cargar_datos():
    # Conecta usando las credenciales de la sección correspondiente se cambia ttl de 1h a 5m
    gc = gspread.service_account_from_dict(st.secrets['gcp_service_account'])

    # Abre el libro de Sheets llamado "SICOIN_BASE"
    sh = gc.open("SICOIN_BASE")

    # Selecciona las hojas correspondientes
    worksheet1 = sh.worksheet("PTAR")    # Hoja para PTAR
    worksheet2 = sh.worksheet("ACTRI")   # Hoja para ACTRI
    worksheet3 = sh.worksheet("PTCI")    # Hoja para PTCI
    worksheet4 = sh.worksheet("AMTRI")   # Hoja para AMTRI
    worksheet5 = sh.worksheet("NOMBRES")   # Hoja para AMTRI

    # Obtén todos los registros y conviértelos a DataFrames
    return {
        "PTAR": pd.DataFrame(worksheet1.get_all_records()),
        "ACTRI": pd.DataFrame(worksheet2.get_all_records()),
        "PTCI": pd.DataFrame(worksheet3.get_all_records()),
        "AMTRI": pd.DataFrame(worksheet4.get_all_records()),
        "NOMBRES": pd.DataFrame(worksheet5.get_all_records())
    }

#============================================ FUNCIÓN PARA LIMPIEZA DE DATOS ============================================================
@st.cache_data(show_spinner=False)
def limpiar_datos(df):
    df.columns = df.columns.str.strip()                                          # Normaliza nombres de las columnas
    if 'Año' in df.columns:
        df = df[df['Año'] != 'Año']                                                # Elimina filas duplicadas con encabezados
        df['Año'] = pd.to_numeric(df['Año'], errors='coerce')                      # Normaliza 'Año' y lo convierte a número
    if 'Institución' in df.columns:
        df['Institución'] = df['Institución'].astype(str).str.strip()              # Normaliza 'Institución'
    if 'Sector' in df.columns:
        df['Sector'] = df['Sector'].astype(str).str.strip()                        # Normaliza 'Sector'
    return df

#================================================== CARGA PRINCIPAL DE LOS DATOS EN LA APP ============================================================
try:
    # Paso 1: Descarga y carga de datos (solo en primer uso)
    datos_crudos = descargar_y_cargar_datos()  # Se leen los registros desde Sheets

    # Paso 2: Limpieza de datos
    datos_limpios = {nombre: limpiar_datos(df) for nombre, df in datos_crudos.items()}

    # Asignación a variables
    df1 = datos_limpios["PTAR"]
    df2 = datos_limpios["ACTRI"]
    df3 = datos_limpios["PTCI"]
    df4 = datos_limpios["AMTRI"]
    df5 = datos_limpios["NOMBRES"]

except Exception as e:
    st.error(f"Error crítico: {str(e)}")
    st.stop()
#======================================= FIN DE LA DESCARGA Y CONSOLIDACIÓN DE INFORMACIÓN PARA LA APP ======================================================================================



###########################################################
###########################################################
###########################################################
# CABECERA DE LA APP Y CONFIGURACIÓN DE FILTROS PRINCIPALES
###########################################################
###########################################################
###########################################################


#============================================ CABECERA ESTÁTICA CON LOS TÍTULOS PRINCIPALES ======================================================================================
st.markdown("""
<div style='background-color:#621132; padding:30px; border-radius:8px; margin-bottom:20px;'>
  <h1 style='text-align:center; color:white; margin:0; font-size:28px;'>SISTEMA DE CONTROL INTERNO INSTITUCIONAL 2025</h1>
  <h3 style='text-align:center; color:white; margin:0; margin-top:10px; font-size:20px;'>RIESGOS Y AVANCE DE LAS ACCIONES DE CONTROL</h3>
</div>
""", unsafe_allow_html=True)


#====================================== LISTAS DE FILTROS PARTE 1 - PRE CÁLCULO PARA OPTIMIZAR RENDIMIENTO ==============================================
@st.cache_data(show_spinner=False)
def precompute_filter_lists(df):
    # Lista de instituciones y sectores
    inst_list = sorted(df['Institución'].dropna().unique().tolist())
    sector_list = sorted(df['Sector'].dropna().unique().tolist())

    # Precomputar años disponibles por institución
    years_by_institucion = {}
    for inst in inst_list:
        years = sorted(df[df['Institución'] == inst]['Año'].dropna().unique().tolist())
        years_by_institucion[inst] = years

    # Precomputar años disponibles por sector
    years_by_sector = {}
    for sec in sector_list:
        years = sorted(df[df['Sector'] == sec]['Año'].dropna().unique().tolist())
        years_by_sector[sec] = years

    return inst_list, sector_list, years_by_institucion, years_by_sector

#===================================== LISTAS DE FILTROS PARTE 2 - OBTENCIÓN DE LISTA DE FILTROS PRECOMPUTADAS ==============================================
inst_list, sector_list, years_by_inst, years_by_sector = precompute_filter_lists(df1)  # Obtener listas de filtros precomputadas (se calcula una única vez por sesión)

# Callback para reiniciar sector a "Todas" al cambiar la institución
def reset_sector():
    st.session_state['sector'] = "Todas"

col1, col2, col3 = st.columns(3)  # Guardar filtros
with col1:
    institucion = st.selectbox("Seleccione la Institución", inst_list, key="institucion", on_change=reset_sector)
with col2:
    sector = st.selectbox("Seleccione el Sector", ["Todas"] + sector_list, key="sector")
with col3:
    # Se seleccionan los años basados en la opción de sector o institución
    if sector != "Todas":
        available_years = years_by_sector.get(sector, [])
    else:
        available_years = years_by_inst.get(institucion, [])
    year = st.selectbox("Seleccione el Año", available_years)

#======================================= FIN DE LA CABECERA DE LA APP Y CONFIGURACIÓN DE FILTROS PRINCIPALES =========================================================
#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------



###########################################################
###########################################################
###########################################################
# 1. PESTAÑA PTAR
###########################################################
###########################################################
###########################################################



#====================================== PREPARACIÓN DE DATOS ANTES DE MOSTRAR RESULTADOS EN LA PESTAÑA PTAR =====================================================================
#------------------------------------------------------------------------------------------------------------------------------------------------------------------


#================================== SE OBTIENE UNA LISTA CON LOS NOMBRES DE LAS VARIABLES PARA EL REPORTE PTAR =====================================================
risk_cols = ['Sustantivo','Administrativo','Financiero','Presupuestal','Servicios', 'Seguridad','Obra_Pública','Recursos_Humanos','Imagen','TICs','Salud', 'Otro','Corrupción','Legal']
cuadrante_cols = ['I','II','III','IV']
estrategia_cols = ['Evitar','Reducir','Asumir','Transferir','Compartir']
estados = ['Sin_Avances', 'En_Proceso', 'Concluidas', 'Cumplimiento']
trimestres = ['1', '2', '3', '4']


#================================== FUNCIÓN PARA OBTENER INSTITUCION, SECTOR Y SIGLAS FILTRADOS (Header) ==============================================
#=================================== OBTIENE TAMBIÉN EL DATASET PARA LAS TABLAS SEGUN SEA EL CASO (data) ==============================================
#========================= OBTIENE TAMBIEN LOS INDICADORES PRINCIPALES DE ACCIONES DE CONTROL Y RIESGOS (Stats) ==============================================
#==================================== OBTIENE TAMBIEN LAS TABLAS: RIESGOS, CUADRANTE Y ESTRATEGIA ==============================================

def generate_dashboard(institucion, year, sector):
  #----- Parte 1 de la función: Calcula data para reportes -----#
    if sector != "Todas":                                       # -------------------- # Caso 1: Sector != "Todas"
        filtered = df1[(df1['Sector'] == sector) & (df1['Año'] == year)]               # Filtra PTAR o df1 por Sector y Año y lo guarda en filtered
        instituciones_list = "<ul style='margin:0; padding-left:20px;'>" + "".join(
          f"<li>{inst}</li>" for inst in filtered['Institución'].unique()) + "</ul>"   # Crea lista desordenada de HTML con las instituciones del sector seleccionado y los imprime
        header = f"""
        <div style='background-color:#f8f9fa; padding:15px; border-radius:10px; margin-bottom:20px; box-shadow:0 2px 4px rgba(0,0,0,0.1);'>
          <h3 style='color:#621132; margin:0; font-size:14px;'>
            Sector: {sector}<br>
            Instituciones: {instituciones_list}
          </h3>
        </div>
        """
                                                                                # COMENTARIO: VARIABLE CUMPLIMIENTO - Se guarda en data, el cumplimeinto promedio por trimestre del sector seleccionado para posterior uso
        data = filtered.sum(numeric_only=True).to_dict()                                # Obtiene los acumulados de filtered (dfi filtrada) y los guarda en data (acumulados por que es un sector) #serie a diccionario para posterior uso en reportes
        for t in trimestres:                                                            # En el Caso 1, el Cumplimiento por Sector se obtendrá en promedio- aqui recorre la lista de trimestres
            key = f"{t}Cumplimiento"                                                    # Se interpola la cadena del trimestre con % y se guarda en key
            if key in filtered.columns:                                                 # Revisa si existe Key (nCumplimiento) como columna en filtered (que es df1 filtrado por Sector y Año)
                avg_value = pd.to_numeric(filtered[key], errors='coerce').fillna(0).mean()  # Filtra key en filtered, convierte a número, cambia NaN por 0 y obtiene el promedio - finalmente guarda el dataframe
                data[key] = round(avg_value, 2)                                             # Guarda los promedios de Cumplimiento en data, con dos decimales

    else:                                                     # ------------------------ # Caso 2: sector = "Todas"    (Filtro por Institucipon y Año)
        filtered = df1[(df1['Institución'] == institucion) & (df1['Año'] == year)]       # En este caso se usa iloc[0] por que filtered nadamas tiene un registro (ya que se filtro por institución)
        header = f"""
        <div style='background-color:#f8f9fa; padding:15px; border-radius:10px; margin-bottom:20px; box-shadow:0 2px 4px rgba(0,0,0,0.1);'>
          <h3 style='color:#621132; margin:0; font-size:14px;'>
            Institución: {institucion}<br>
            Sector: {filtered['Sector'].iloc[0]}<br>
            Siglas: {filtered['Siglas'].iloc[0]}
          </h3>
        </div>
        """
        data = filtered.iloc[0].to_dict()     # Se obtiene un diccionario con los datos filtrados por Institucion y Año para los posteriores reportes

  #---- Parte 2 de la función: Se limpia el data obtenido - se cambian NaN por 0 -----#
    for key in data:
        if pd.isna(data[key]):
            data[key] = 0
        elif isinstance(data[key], (int, float)) and not str(key).endswith("Cumplimiento"):
            data[key] = int(round(data[key]))

  #---- Parte 3 de la función: Obtenido data, se obtienen los indicadores principales de la pestaña PTAR - Total de AC_Total y Riesgos ----#
    stats = f"""
    <div style='background-color:#f8f9fa; padding:20px; border-radius:10px; margin-bottom:20px; box-shadow:0 2px 4px rgba(0,0,0,0.1);'>
      <h2 style='text-align:center; color:#2e86c1; margin:0;'>
        Total de Acciones de Control: <span style='color:#621132;'>{data['AC_Total']}</span><br>
        Total de Riesgos: <span style='color:#621132;'>{data['Riesgos_Totales']}</span>
      </h2>
    </div>
    """

  #---- Parte 4 de la función: Obtención de tablas principales ----#

                             # ------------------------ Tabla de Clasificación de Riesgos ------------------------- #
    risk_html = """
    <div style='overflow-x:auto; margin-bottom:20px;'>
      <table style='width:100%; border-collapse:collapse;'>
        <tr style='background-color:#621132; color:white;'>
    """
    for col in risk_cols:
        risk_html += f"<th style='padding:12px; text-align:center; border:1px solid #ddd;'>{col}</th>"    # Titulos de la tabla
    risk_html += "</tr><tr>"
    for col in risk_cols:                                                                                 # Valores de la tabla
        risk_html += f"<td style='padding:12px; text-align:center; border:1px solid #ddd; font-weight:500;'>{data[col]}</td>"
    risk_html += "</tr></table></div>"

                             # ------------------------------- Tabla de Cuadrante ---------------------------------- #
    cuadrante_html = """
    <div style='overflow-x:auto; margin-bottom:20px;'>
      <table style='width:100%; border-collapse:collapse;'>
        <tr style='background-color:#621132; color:white;'>
    """
    colors = ['#dc3545', '#ffc107', '#28a745', '#007bff']                                                                              # Guarda los colores de cada riesgo
    for col, color in zip(cuadrante_cols, colors):
        cuadrante_html += f"<th style='background-color:{color}; padding:12px; text-align:center; border:1px solid #ddd;'>{col}</th>"
    cuadrante_html += "</tr><tr>"
    for col in cuadrante_cols:
        cuadrante_html += f"<td style='padding:12px; text-align:center; border:1px solid #ddd; font-weight:500;'>{data[col]}</td>"
    cuadrante_html += "</tr></table></div>"

                             # ------------------------------- Tabla de Estrategia ---------------------------------- #
    estrategia_html = """
    <div style='overflow-x:auto; margin-bottom:20px;'>
      <table style='width:100%; border-collapse:collapse;'>
        <tr style='background-color:#621132; color:white;'>
    """
    for col in estrategia_cols:
        estrategia_html += f"<th style='padding:12px; text-align:center; border:1px solid #ddd;'>{col}</th>"
    estrategia_html += "</tr><tr>"
    for col in estrategia_cols:
        estrategia_html += f"<td style='padding:12px; text-align:center; border:1px solid #ddd; font-weight:500;'>{data[col]}</td>"
    estrategia_html += "</tr></table></div>"

  #---- Parte 5 de la función (Final): Retorna resultados ----#
    return header, stats, risk_html, cuadrante_html, estrategia_html, data
#============================================================== FIN DE LA FUNCIÓN =======================================================================



#============================================== DESEMPAQUETADO DE VALORES QUE DEVUELVE LA FUNCIÓN ==============================================
header, stats, risk_html, cuadrante_html, estrategia_html, data = generate_dashboard(institucion, year, sector)


#================================== MOSTRAR INSTITUCIONES, SIGLAS Y  SECTOR FILTRADOS (Header) ==============================================
st.markdown(header, unsafe_allow_html=True)                                                     #Se muestran fuera de las pestañas pues son datos globales
#--------------------------------------------------------------------------------------------------------------------------------------------------

#================================================== CREACIÓN DE PESTAÑAS PTAR, PTCI Y REPORTES =========================================================
tabs = st.tabs(["PTAR", "PTCI", "REPORTES"])


#===================================================== MOSTRAR RESULTADOS EN LA PESTAÑA PTAR ==============================================
#===================================================== MOSTRAR RESULTADOS EN LA PESTAÑA PTAR ==============================================
#===================================================== MOSTRAR RESULTADOS EN LA PESTAÑA PTAR ==============================================

#---- Pestaña PTAR
with tabs[0]:

  #---- Parte 1 del with: Se muestran los Indicadores Principales (Stats) ----#
    st.markdown(stats, unsafe_allow_html=True)


#============================================= SE ABRE LA SECCIÓN 1 - "Clasificación de Riesgos" ==============================================
#--------------------------------------------------------------------------------------------------------------------------------------------------
    st.markdown("""
      <div style='background-color:#621132; color:white; padding:10px; border-radius:5px; margin-bottom:20px; text-align:center;'>
        Clasificación de Riesgos
      </div>
    """, unsafe_allow_html=True)
                                        # ------ Se muestra la Tabla de Clasificación de Riesgos ----#
    st.markdown(risk_html, unsafe_allow_html=True)
    col1, col2 = st.columns(2)

                                #-------------- Se muestra la Tabla de Cuadrante (En columna 1) ------------#
    with col1:
        st.markdown("""
          <div style='background-color:#621132; color:white; padding:10px; border-radius:5px; margin-bottom:20px; text-align:center;'>
            Cuadrante
          </div>
        """, unsafe_allow_html=True)
        st.markdown(cuadrante_html, unsafe_allow_html=True)

                                #-------------- Se muestra la Tabla de Estrategia (En columna 2) ------------#
    with col2:
        st.markdown("""
          <div style='background-color:#621132; color:white; padding:10px; border-radius:5px; margin-bottom:20px; text-align:center;'>
            Estrategia
          </div>
        """, unsafe_allow_html=True)
        st.markdown(estrategia_html, unsafe_allow_html=True)



#====================================== SE ABRE LA SECCIÓN 2 - "Seguimiento de las Acciones de Control" ==============================================
#--------------------------------------------------------------------------------------------------------------------------------------------------
    st.markdown("""
      <div style='background-color:#621132; color:white; padding:10px; border-radius:5px; margin-bottom:20px; text-align:center;'>
        Seguimiento de las Acciones de Control
      </div>
    """, unsafe_allow_html=True)

                       #-------------- Parte 1: Se crea y muestra la Tabla para el estado de las Acciones de Control ------------#
    # (Se agregan "%" en Cumplimiento)
    st.markdown("""
      <div style='overflow-x:auto; margin-top:20px; margin-bottom:20px;'>
        <table style='width:100%; border-collapse:collapse;'>
          <tr style='background-color:#621132; color:white; text-align:center;'>
            <th>Estatdo de las Acciones de Control</th>
            <th>Primero</th>
            <th>Segundo</th>
            <th>Tercero</th>
            <th>Cuarto</th>
          </tr>
          <tr>
            <th style='background-color:#621132; color:white;'>Sin Avances</th>
            <td style='text-align:center; border:1px solid #ddd;'>{0}</td>
            <td style='text-align:center; border:1px solid #ddd;'>{1}</td>
            <td style='text-align:center; border:1px solid #ddd;'>{2}</td>
            <td style='text-align:center; border:1px solid #ddd;'>{3}</td>
          </tr>
          <tr>
            <th style='background-color:#621132; color:white;'>En Proceso</th>
            <td style='text-align:center; border:1px solid #ddd;'>{4}</td>
            <td style='text-align:center; border:1px solid #ddd;'>{5}</td>
            <td style='text-align:center; border:1px solid #ddd;'>{6}</td>
            <td style='text-align:center; border:1px solid #ddd;'>{7}</td>
          </tr>
          <tr>
            <th style='background-color:#621132; color:white;'>Concluidas</th>
            <td style='text-align:center; border:1px solid #ddd;'>{8}</td>
            <td style='text-align:center; border:1px solid #ddd;'>{9}</td>
            <td style='text-align:center; border:1px solid #ddd;'>{10}</td>
            <td style='text-align:center; border:1px solid #ddd;'>{11}</td>
          </tr>
          <tr>
            <th style='background-color:#621132; color:white;'>% de Cumplimiento</th>
            <td style='text-align:center; border:1px solid #ddd;'>{12}%</td>
            <td style='text-align:center; border:1px solid #ddd;'>{13}%</td>
            <td style='text-align:center; border:1px solid #ddd;'>{14}%</td>
            <td style='text-align:center; border:1px solid #ddd;'>{15}%</td>
          </tr>
        </table>
      </div>
    """.format(
      data.get("1Sin_Avances",0), data.get("2Sin_Avances",0), data.get("3Sin_Avances",0), data.get("4Sin_Avances",0),
      data.get("1En_Proceso",0), data.get("2En_Proceso",0), data.get("3En_Proceso",0), data.get("4En_Proceso",0),
      data.get("1Concluidas",0), data.get("2Concluidas",0), data.get("3Concluidas",0), data.get("4Concluidas",0),
      data.get("1Cumplimiento",0), data.get("2Cumplimiento",0), data.get("3Cumplimiento",0), data.get("4Cumplimiento",0)
    ), unsafe_allow_html=True)

                           #-------------- Parte 2: Se crea el gráfico de barras para el estado de las AC ------------#
           #----------------- Para ello primero crea lista de diccionarios que contenga los datos para el gráfico -----------------#

    plot_data = []
    for t in trimestres:
        for estado in estados:
            plot_data.append({'Trimestre': f' {t}', 'Estado': estado, 'Cantidad': data.get(f"{t}{estado}", 0)})

                #-------------- Convierte a dataframe la información obtenida y crea la gráfica (fig)  ------------------------#
    fig = px.bar(pd.DataFrame(plot_data), x='Trimestre', y='Cantidad', color='Estado',
                 barmode='group', height=400,
                 color_discrete_map={'Sin_Avances': '#dc3545', 'En_Proceso': '#ffc107',
                                     'Concluidas': '#28a745', 'Cumplimiento': '#6610f2'})

                                       #--------------  Da el formato a a la gráfica  ------------------#
    fig.update_layout(
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(color='#333'),
        xaxis=dict(title=None, gridcolor='#f0f0f0'),
        yaxis=dict(title=None, gridcolor='#f0f0f0'),
        legend=dict(title=None),
        margin=dict(l=20, r=20, t=50, b=20)
    )
     #--------------  Agrega la etiqueta de porcentaje en las barras de Cumplimiento (ya que este valor es porcentaje) -----------------#
    for trace in fig.data:
        if trace.name == "Cumplimiento":
            trace.text = [f"{y}%" for y in trace.y]
            trace.textposition = 'outside'

                                #-------------- Muestra el gráfico de barras para el estado de las AC ------------#
    st.plotly_chart(fig, use_container_width=True)



#================================= SE ABRE LA SECCIÓN 3 - "Descripción de los Riesgos y las Acciones de Control" ==============================================
#--------------------------------------------------------------------------------------------------------------------------------------------------
    st.markdown("""
          <div style='background-color:#621132; color:white; padding:10px; border-radius:5px; margin-top:30px; margin-bottom:30px; text-align:center;'>
        Descripción de los Riesgos y las Acciones de Control
      </div>
    """, unsafe_allow_html=True)

                        #------------------ Para el contenido de esta sección se utilizará df2 (ACTRI) --------------#

                    #--------------Primero:  Se crea un dataframe (filtered_df2) según el filtro seleccionado ------------#
                    #---------------Esto se hace por que estamos usando otra base, pero con los mismos filtros ------------#

    if sector != "Todas":
        filtered_df2 = df2[(df2['Sector'] == sector) & (df2['Año'] == year)]
    else:
        filtered_df2 = df2[(df2['Institución'] == institucion) & (df2['Año'] == year)]


            #-------------- Segundo: Se verifica si (data['AC_Total']) coincide con el número de filas en filtered_df2 ------------#
    if int(data['AC_Total']) != len(filtered_df2):
        st.markdown("""
          <p style='color:red; font-weight:bold; text-align:center;'>
            Las acciones de control registradas en el PTAR no coinciden con las Acciones de Control Registradas
          </p>
        """, unsafe_allow_html=True)

                  #------------------ Tercero: Se crean los encabezados para la tabla principal de esta sección --------------#
    table_html = """
      <div style='overflow-x:auto;'>
        <table style='width:100%; border-collapse:collapse; margin-bottom:20px;'>
          <tr style='background-color:#621132; color:white;'>
            <th style='padding:12px; text-align:center; border:1px solid #ddd;'>Año</th>
            <th style='padding:12px; text-align:center; border:1px solid #ddd;'>Siglas</th>
            <th style='padding:12px; text-align:center; border:1px solid #ddd;'>Riesgo</th>
            <th style='padding:12px; text-align:center; border:1px solid #ddd;'>Descripción del Riesgo</th>
            <th style='padding:12px; text-align:center; border:1px solid #ddd;'>No. de AC</th>
            <th style='padding:12px; text-align:center; border:1px solid #ddd;'>Descripción</th>
            <th style='padding:12px; text-align:center; border:1px solid #ddd;'>Avance Institución</th>
            <th style='padding:12px; text-align:center; border:1px solid #ddd;'>Avance OIC</th>
          </tr>
    """

                               #------------------ Cuarto: Se llenan los datos de la tabla principal --------------#
        # Primero muestra los valores de Avance como porcentaje
    for _, row in filtered_df2.iterrows():
        avance_inst = f"{round(row['Avance_Institución'], 2)}%" if pd.notna(row['Avance_Institución']) else ""
        avance_oic = f"{round(row['Avance_OIC'], 2)}%" if pd.notna(row['Avance_OIC']) else ""
        # Crea la tabla de html con los datos correspondientes
        table_html += "<tr>"
        table_html += f"<td style='padding:12px; text-align:center; border:1px solid #ddd;'>{row.get('Año','')}</td>"
        table_html += f"<td style='padding:12px; text-align:center; border:1px solid #ddd;'>{row.get('Siglas','')}</td>"
        table_html += f"<td style='padding:12px; text-align:center; border:1px solid #ddd;'>{row.get('Riesgo','')}</td>"
        table_html += f"<td style='padding:12px; text-align:center; border:1px solid #ddd;'>{row.get('Descripción_del_Riesgo','')}</td>"
        table_html += f"<td style='padding:12px; text-align:center; border:1px solid #ddd;'>{row.get('AC','')}</td>"
        table_html += f"<td style='padding:12px; text-align:justify; border:1px solid #ddd;'>{row.get('Descripcion','')}</td>"
        table_html += f"<td style='padding:12px; text-align:center; border:1px solid #ddd;'>{avance_inst}</td>"
        table_html += f"<td style='padding:12px; text-align:center; border:1px solid #ddd;'>{avance_oic}</td>"
        table_html += "</tr>"
    table_html += "</table></div>" #cierra la tabla fuera del for

                              #------------------ Quinto: Se muestra la tabla principal de la sección--------------#
    st.markdown(table_html, unsafe_allow_html=True)


#============================================= PIE DE PÁGINA DE LA SECCION PTAR - FUENTE SICOIN ==============================================
    st.markdown("""
      <div style='text-align:right; font-size:12px; color:#666; margin-top:20px;'>
        Fuente: Sistema de Control Interno (SICOIN)
      </div>
    """, unsafe_allow_html=True)

#================================= FIN DE LA SECCIÓN 3 - "Descripción de los Riesgos y las Acciones de Control" ==============================================
#--------------------------------------------------------------------------------------------------------------------------------------------------





###########################################################
###########################################################
###########################################################
# 2. PESTAÑA PTCI
###########################################################
###########################################################
###########################################################


#====================================== PREPARACIÓN DE DATOS ANTES DE MOSTRAR RESULTADOS EN LA PESTAÑA PTCI =====================================================================
#------------------------------------------------------------------------------------------------------------------------------------------------------------------


                        #------------------ Para el contenido de esta sección se utilizará df2, df3 y df4 --------------#

               #--------------Primero:  Se crean los dataframes (filtro_ptci y filtro_ptci_df4) según el filtro seleccionado ------------#
                    #---------------Esto se hace por que estamos usando otras bases, pero con los mismos filtros ------------#


#---- Pestaña PTCI
with tabs[1]:
    # Filtrar df3 y df4 con los mismos filtros
    if sector != "Todas":
        filtro_ptci = (df3['Sector'] == sector) & (df3['Año'] == year)
        filtro_ptci_df4 = (df4['Sector'] == sector) & (df4['Año'] == year)
    else:
        filtro_ptci = (df3['Institución'] == institucion) & (df3['Año'] == year)
        filtro_ptci_df4 = (df4['Institución'] == institucion) & (df4['Año'] == year)
    df_ptci = df3[filtro_ptci]
    df_ptci_df4 = df4[filtro_ptci_df4]

                           #--------------- Segundo: Revisa si el DataFrame filtrado df_ptci está vacío ------------#
      #---------------Esto se hace por que vamos a tomar un indicador similar a header pero lo imprimiremos directamente ------------#

    if df_ptci.empty:
        st.markdown("No hay datos para PTCI con los filtros seleccionados.")
    else:

      #---------------------- Obtiene el Cumplimiento en % según el sector (Este es el indicador que necesitamos) -------------------#
        if sector != "Todas":
            # Nuestro indicador será el promedio para sector (ya que son varias instituciones)
            cum_ngci = df_ptci['Cumplimiento_General_de_las_NGCI'].mean().round(2)
            cum_ngci_str = f"{cum_ngci}%"

           #Indicador para las AM
            acciones_mejora_actualizadas = df_ptci['TotalAcciones_de_Mejora_Programa_Actualizado'].sum()
            acciones_mejora_actualizadas_str = f"{acciones_mejora_actualizadas}"


        else:
            #  Nuestro indicador será el valor directo para institución (ya que solo es una)
            cum_ngci = df_ptci['Cumplimiento_General_de_las_NGCI'].iloc[0]
            cum_ngci_str = f"{round(cum_ngci, 2)}%"

               #Indicador para las AM
            acciones_mejora_actualizadas = df_ptci['TotalAcciones_de_Mejora_Programa_Actualizado'].iloc[0]
            acciones_mejora_actualizadas_str = f"{acciones_mejora_actualizadas}"


      #---------------------- Una vez preparados nuestros datos, estamos listos para mostrarlos en la pestaña PTCI -------------------#
#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------






#===================================================== MOSTRAR RESULTADOS EN LA PESTAÑA PTCI ==============================================
#===================================================== MOSTRAR RESULTADOS EN LA PESTAÑA PTCI ==============================================
#===================================================== MOSTRAR RESULTADOS EN LA PESTAÑA PTCI ==============================================




#================================== MOSTRAR INDICADOR PRINCIPAL DE LA PESTAÑA PTCI (Cumplimiento General de las NGCI) ==============================================
        st.markdown(f"""
            <div style='background-color:#f8f9fa; padding:20px; border-radius:10px; margin-bottom:20px; box-shadow:0 2px 4px rgba(0,0,0,0.1);'>
                <h2 style='text-align:center; color:#2e86c1; margin:0;'>
                    Total de Acciones de Mejora: <span style='color:#621132;'>{acciones_mejora_actualizadas}</span></br>
                    Cumplimiento general de las NGCI: <span style='color:#621132;'>{cum_ngci_str}</span>
                </h2>
            </div>
            """, unsafe_allow_html=True)



#============================================= SE ABRE LA SECCIÓN 1 - "Programa de Trabajo de Control Interno" ==============================================
#------------------------------------------------------------------------------------------------------------------------------------------------------------
        st.markdown("""
            <div style='background-color:#621132; color:white; padding:10px; border-radius:5px; margin-bottom:20px; text-align:center;'>
                Programa de Trabajo de Control Interno
            </div>
        """, unsafe_allow_html=True)

          #-------------- Parte 1: En esta primera parte se utilizará un condicional, ya que los indicadores principales (headers de PTCI) ------------#
                        #-----------------que se van a mostrar, dependerán de la condición sobre el sector -----------------#
                    #-----------------  Estos se mostraran como una tabla (Ya que tenemos mas de dos indicadores)-----------------#
                    #-----------------  Mapearemos nombres amigables pare entender mejor las variables en la appp-----------------#

        # Mapeo de nombres amigables
        friendly_names = {
            "Acciones_de_Mejora_Programa_Original": "Programa Original de Acciones de Mejora",
            "Se_Actualizó_el_Programa": "Se Actualizó el Programa",
            "No_Se_Actualizó_el_Programa": "No Se Actualizó el Programa",
            "TotalAcciones_de_Mejora_Programa_Actualizado": "Programa Actualizado de Acciones de Mejora"
        }

                #----------------- Guardaremos las columnas de nuestros indicadores a mostrar según la condición sobre el sector-----------------#
        if sector == "Todas":
            ptci_cols = [
                "Acciones_de_Mejora_Programa_Original",
                "Se_Actualizó_el_Programa",
                "No_Se_Actualizó_el_Programa",
                "TotalAcciones_de_Mejora_Programa_Actualizado"
            ]
        else:
            ptci_cols = [
                "Acciones_de_Mejora_Programa_Original",
                "TotalAcciones_de_Mejora_Programa_Actualizado"
            ]

                #-----------------Creamos el inicio de la tabla HTML que vamos a mostrar en PTCI-----------------#
        ptci_table = "<div style='overflow-x:auto; margin-bottom:20px;'><table style='width:100%; border-collapse:collapse;'>"
        ptci_table += "<tr style='background-color:#621132; color:white;'>"

                  #----------------- Creamos los headers con nombres amigables para la tabla -----------------#
        for col in ptci_cols:
            header_name = friendly_names.get(col, col)
            ptci_table += f"<th style='padding:12px; text-align:center; border:1px solid #ddd;'>{header_name}</th>"
        ptci_table += "</tr><tr>"

                #-------------- Parte 2: Llenamos los valores de nuestra tabla según la condición sobre el sector ------------#
        for col in ptci_cols:
            if sector == "Todas" and col in ["Se_Actualizó_el_Programa", "No_Se_Actualizó_el_Programa"]:
                cell_value = df_ptci[col].iloc[0] if not df_ptci.empty and col in df_ptci.columns else "N/A"
            else:
                numeric_value = pd.to_numeric(df_ptci[col], errors='coerce').fillna(0).sum() if col in df_ptci.columns else 0
                cell_value = int(round(numeric_value))
            ptci_table += f"<td style='padding:12px; text-align:center; border:1px solid #ddd; font-weight:500;'>{cell_value}</td>"
        ptci_table += "</tr></table></div>"

                #-------------- Parte 3: Finalmente mostramos la tabla con nuestros indicadores para el PTCI ------------#
        st.markdown(ptci_table, unsafe_allow_html=True)


#============================================= SE ABRE LA SECCIÓN 2 - "Programa de Trabajo de Control Interno - Desglose por Institución" =============================================
#------------------------------------------------------------------------------------------------------------------------------------------------------------#---------------------------------------------------------------------------------------

        # Condición para mostrar la Sección 2
        if sector != "Todas":
            st.markdown("""
              <div style='background-color:#621132; color:white; padding:10px; border-radius:5px; margin-bottom:10px; text-align:center;'>
                Detalle del Programa de Trabajo Desglosado por Institución
              </div>
            """, unsafe_allow_html=True)

            #------------- Filtro por Institución --------------FILTRO CÓDIGO KPP70
            selected_institucion = st.selectbox("Filtrar Institución del Sector", options=sorted(df_ptci["Institución"].unique()))

            #----------------- Desglose de las variables a mostrar -----------------#
            desglose = df_ptci[["Año", "Institución", "Cumplimiento_General_de_las_NGCI", "Informe_Anual_Finalizado", "SUBIO_ARCHIVO",
                                "Se_Actualizó_el_Programa", "No_Se_Actualizó_el_Programa",
                                "Acciones_de_Mejora_Programa_Original", "TotalAcciones_de_Mejora_Programa_Actualizado"]]

            # Filtrar el DataFrame según la institución seleccionada
            desglose = desglose[desglose["Institución"] == selected_institucion]

            #------------- Diccionario de etiquetas amigables --------------
            friendly_labels = {
                "Año": "Año",
                "Institución": "Institución",
                "Cumplimiento_General_de_las_NGCI": "Cumplimiento General NGCI",
                "Informe_Anual_Finalizado": "Informe Anual Finalizado",
                "SUBIO_ARCHIVO": "Subió Archivo",
                "Se_Actualizó_el_Programa": "Programa Actualizado",
                "No_Se_Actualizó_el_Programa": "Programa No Actualizado",
                "Acciones_de_Mejora_Programa_Original": "Acciones Mejora (Original)",
                "TotalAcciones_de_Mejora_Programa_Actualizado": "Acciones Mejora (Actualizado)"
            }

            #----------------- Creando las columnas de la Tabla HTML para el desglose -----------------#
            desglose_html = "<div style='overflow-x:auto; margin-bottom:20px; font-size:12px; padding:5px;'><table style='width:100%; border-collapse:collapse;'>"
            desglose_html += "<tr style='background-color:#621132; color:white;'>"

            #----------------- Llenado de tabla (cabeceras con etiquetas amigables) -----------------#
            for col in desglose.columns:
                friendly_name = friendly_labels.get(col, col)
                desglose_html += f"<th style='padding:5px; text-align:center; border:1px solid #ddd;'>{friendly_name}</th>"
            desglose_html += "</tr>"

            for _, row in desglose.iterrows():
                desglose_html += "<tr>"
                for col in desglose.columns:
                    value = row.get(col, '')
                    if col == "Cumplimiento_General_de_las_NGCI":
                        value = f"{int(value)}%" if pd.notna(value) else ""
                    desglose_html += f"<td style='padding:5px; text-align:center; border:1px solid #ddd;'>{value}</td>"
                desglose_html += "</tr>"
            desglose_html += "</table></div>"

            #-------------- Parte 2: Mostramos la tabla del programa de trabajo desglosado por institución --------------#
            st.markdown(desglose_html, unsafe_allow_html=True)



#============================================= SE ABRE LA SECCIÓN 3 - "Detalle de las Acciones de Mejora"================================= ==============================================
#------------------------------------------------------------------------------------------------------------------------------------------------------------
        st.markdown("""
          <div style='background-color:#621132; color:white; padding:10px; border-radius:5px; margin-bottom:20px; text-align:center;'>
            Detalle de las Acciones de Mejora
          </div>
        """, unsafe_allow_html=True)

        # ========== FILTRO DE INSTITUCIÓN PARA SECCIONES 3 Y 4 ======--------FILTRO CÓDIGO KPP71
        if sector != "Todas":
            # Obtener instituciones del sector y añadir opción "Todas"
            instituciones_sector = ["Todas"] + sorted(df_ptci["Institución"].unique().tolist())
            selected_institucion_am = st.selectbox(
                "Filtrar por Institución para Acciones de Mejora",
                options=instituciones_sector,
                index=0
            )
        else:
            selected_institucion_am = "Todas"


        # ========== PREPARAR DATOS SEGÚN FILTRO ==========
        # Para sección 3 (Detalle Acciones Mejora)
        if selected_institucion_am == "Todas":
            df_ptci_df4_filtrado = df_ptci_df4
        else:
            df_ptci_df4_filtrado = df_ptci_df4[df_ptci_df4["Institución"] == selected_institucion_am]

        # Para sección 4 (Seguimiento Acciones Mejora)
        if selected_institucion_am == "Todas":
            df_ptci_filtrado = df_ptci
        else:
            df_ptci_filtrado = df_ptci[df_ptci["Institución"] == selected_institucion_am]

        # ========== CONSTRUIR TABLA DETALLE ==========
        detalle_cols = ["Registradas", "Localizadas", "No_localizadas", "Suficientes", "Parcielmente_Suficientes", "Insuficientes"]
        detalle_table = "<div style='overflow-x:auto; margin-bottom:20px;'><table style='width:100%; border-collapse:collapse;'>"
        detalle_table += "<tr style='background-color:#621132; color:white;'>"

        for col in detalle_cols:
            detalle_table += f"<th style='padding:12px; text-align:center; border:1px solid #ddd;'>{col}</th>"
        detalle_table += "</tr><tr>"

        for col in detalle_cols:
            value = pd.to_numeric(df_ptci_df4_filtrado[col], errors='coerce').fillna(0).sum() if col in df_ptci_df4_filtrado.columns else 0
            detalle_table += f"<td style='padding:12px; text-align:center; border:1px solid #ddd; font-weight:500;'>{int(round(value))}</td>"

        detalle_table += "</tr></table></div>"
        st.markdown(detalle_table, unsafe_allow_html=True)

#============================================= SE ABRE LA SECCIÓN 4 - "Seguimiento de las Acciones de Mejora"=================================
#------------------------------------------------------------------------------------------------------------------------------------------------------------
        st.markdown("""
          <div style='background-color:#621132; color:white; padding:10px; border-radius:5px; margin-bottom:20px; text-align:center;'>
            Seguimiento de las Acciones de Mejora
          </div>
        """, unsafe_allow_html=True)

        # ========== PROCESAR DATOS PARA TABLA SEGUIMIENTO ==========
        data_ptci_dict = {}
        for t in trimestres:
            for estado in estados:
                key = f"{t}{estado}"
                if key in df_ptci_filtrado.columns:
                    # Manejar porcentaje de cumplimiento
                    if estado == "Cumplimiento":
                        if sector != "Todas" and selected_institucion_am == "Todas":
                            value = pd.to_numeric(df_ptci_filtrado[key], errors='coerce').mean()
                        else:
                            value = pd.to_numeric(df_ptci_filtrado[key], errors='coerce').sum()
                    else:
                        value = pd.to_numeric(df_ptci_filtrado[key], errors='coerce').sum()
                else:
                    value = 0
                data_ptci_dict[key] = int(round(value))

        # ========== CONSTRUIR TABLA SEGUIMIENTO ==========
        st.markdown("""
          <div style='overflow-x:auto; margin-bottom:20px;'>
            <table style='width:100%; border-collapse:collapse;'>
              <tr style='background-color:#621132; color:white; text-align:center;'>
                <th>Estatus de las Acciones de Mejora</th>
                <th>Primero</th>
                <th>Segundo</th>
                <th>Tercero</th>
                <th>Cuarto</th>
              </tr>
              <tr>
                <th style='background-color:#621132; color:white;'>Sin Avances</th>
                <td style='text-align:center; border:1px solid #ddd;'>{0}</td>
                <td style='text-align:center; border:1px solid #ddd;'>{1}</td>
                <td style='text-align:center; border:1px solid #ddd;'>{2}</td>
                <td style='text-align:center; border:1px solid #ddd;'>{3}</td>
              </tr>
              <tr>
                <th style='background-color:#621132; color:white;'>En Proceso</th>
                <td style='text-align:center; border:1px solid #ddd;'>{4}</td>
                <td style='text-align:center; border:1px solid #ddd;'>{5}</td>
                <td style='text-align:center; border:1px solid #ddd;'>{6}</td>
                <td style='text-align:center; border:1px solid #ddd;'>{7}</td>
              </tr>
              <tr>
                <th style='background-color:#621132; color:white;'>Concluidas</th>
                <td style='text-align:center; border:1px solid #ddd;'>{8}</td>
                <td style='text-align:center; border:1px solid #ddd;'>{9}</td>
                <td style='text-align:center; border:1px solid #ddd;'>{10}</td>
                <td style='text-align:center; border:1px solid #ddd;'>{11}</td>
              </tr>
              <tr>
                <th style='background-color:#621132; color:white;'>% de Cumplimiento</th>
                <td style='text-align:center; border:1px solid #ddd;'>{12}%</td>
                <td style='text-align:center; border:1px solid #ddd;'>{13}%</td>
                <td style='text-align:center; border:1px solid #ddd;'>{14}%</td>
                <td style='text-align:center; border:1px solid #ddd;'>{15}%</td>
              </tr>
            </table>
          </div>
        """.format(
          data_ptci_dict.get("1Sin_Avances",0), data_ptci_dict.get("2Sin_Avances",0), data_ptci_dict.get("3Sin_Avances",0), data_ptci_dict.get("4Sin_Avances",0),
          data_ptci_dict.get("1En_Proceso",0), data_ptci_dict.get("2En_Proceso",0), data_ptci_dict.get("3En_Proceso",0), data_ptci_dict.get("4En_Proceso",0),
          data_ptci_dict.get("1Concluidas",0), data_ptci_dict.get("2Concluidas",0), data_ptci_dict.get("3Concluidas",0), data_ptci_dict.get("4Concluidas",0),
          data_ptci_dict.get("1Cumplimiento",0), data_ptci_dict.get("2Cumplimiento",0), data_ptci_dict.get("3Cumplimiento",0), data_ptci_dict.get("4Cumplimiento",0)
        ), unsafe_allow_html=True)







              #-------------- Parte 3: Se crea el gráfico de barras para el seguimiento de las acciones de mejora ------------#
           #----------------- Para ello primero crea lista de diccionarios que contenga los datos para el gráfico -----------------#

# ========== ACTUALIZACIÓN DEL GRÁFICO ==========
        # Crear lista de diccionarios con los datos filtrados
        plot_data_ptci = []
        for t in trimestres:
            for estado in estados:
                key = f"{t}{estado}"
                plot_data_ptci.append({
                    'Trimestre': f' {t}',
                    'Estado': estado,
                    'Cantidad': data_ptci_dict.get(key, 0)
                })

        # Crear gráfico con datos filtrados
        fig_ptci = px.bar(
            pd.DataFrame(plot_data_ptci),
            x='Trimestre',
            y='Cantidad',
            color='Estado',
            barmode='group',
            height=400,
            color_discrete_map={
                'Sin_Avances': '#dc3545',
                'En_Proceso': '#ffc107',
                'Concluidas': '#28a745',
                'Cumplimiento': '#6610f2'
            }
        )

        # Añadir formato al gráfico
        fig_ptci.update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white',
            font=dict(color='#333'),
            xaxis=dict(title=None, gridcolor='#f0f0f0'),
            yaxis=dict(title=None, gridcolor='#f0f0f0'),
            legend=dict(title=None),
            margin=dict(l=20, r=20, t=50, b=20)
        )

        # Añadir etiquetas de porcentaje solo para cumplimiento
        for trace in fig_ptci.data:
            if trace.name == "Cumplimiento":
                trace.text = [f"{y}%" for y in trace.y]
                trace.textposition = 'outside'

        # Mostrar gráfico
        st.plotly_chart(fig_ptci, use_container_width=True)



#============================================= SE ABRE LA SECCIÓN 5 - "Descripción de los Procesos y Acciones de Mejora" =============================================
#------------------------------------------------------------------------------------------------------------------------------------------------------------
        st.markdown("""
          <div style='background-color:#621132; color:white; padding:10px; border-radius:5px; margin-top:30px; margin-bottom:30px; text-align:center;'>
            Descripción de los Procesos y las Acciones de Mejora
          </div>
        """, unsafe_allow_html=True)

        #------------- Filtros --------------
        col1, col2 = st.columns(2)
        with col1:
            selected_trimester = st.selectbox("Filtrar por Trimestre", options=sorted(df_ptci_df4["Trimestre"].unique()))
        with col2:
            # Añadir opción "Todas" al filtro de Siglas
            siglas_options = ["Todas"] + sorted(df_ptci_df4["Siglas"].unique().tolist())
            selected_siglas = st.selectbox("Filtrar por Siglas", options=siglas_options, index=0)

        # Filtrar el DataFrame según los filtros seleccionados
        if selected_siglas == "Todas":
            filtered_df = df_ptci_df4[df_ptci_df4["Trimestre"] == selected_trimester]
        else:
            filtered_df = df_ptci_df4[
                (df_ptci_df4["Trimestre"] == selected_trimester) &
                (df_ptci_df4["Siglas"] == selected_siglas)
            ]

        #-------------- Parte 1: Creamos la tabla que muestra la descripción de los Procesos y Acciones de Mejora ------------#
        headers_ptci = ["Año", "Trimestre", "Siglas", "Procesos", "AM", "Descripcion", "Fecha_Inicio", "Fecha_Termino",
                        "Avance_Institución", "Avance_OIC", "¿Evaluado?", "¿Favorable?", "¿AM_Congruete?", "¿Contribuye?"]

        desc_ptci_html = "<div style='overflow-x:auto;'><table style='width:100%; border-collapse:collapse; margin-bottom:20px;'>"
        desc_ptci_html += "<tr style='background-color:#621132; color:white;'>"

        for h in headers_ptci:
            desc_ptci_html += f"<th style='padding:12px; text-align:center; border:1px solid #ddd;'>{h}</th>"
        desc_ptci_html += "</tr>"

        #-------------- Llenamos la tabla ------------#
        for _, row in filtered_df.iterrows():
            desc_ptci_html += "<tr>"
            for h in headers_ptci:
                cell = row.get(h, "")
                if h in ["Avance_Institución", "Avance_OIC"]:
                    try:
                        cell = f"{int(float(cell))}%"
                    except:
                        cell = cell
                desc_ptci_html += f"<td style='padding:12px; text-align:center; border:1px solid #ddd;'>{cell}</td>"
            desc_ptci_html += "</tr>"
        desc_ptci_html += "</table></div>"

        # Verificación de correspondencia (actualizada para trabajar con múltiples instituciones)
        if selected_siglas == "Todas":
            acciones_mejora_actualizadas_AMTRI = len(filtered_df)
        else:
            acciones_mejora_actualizadas_AMTRI = len(filtered_df['Trimestre'] == 4)



        if selected_siglas == "Todas":
            if int(acciones_mejora_actualizadas) != acciones_mejora_actualizadas_AMTRI:
                st.markdown(f"""
                  <p style='color:red; font-weight:bold; text-align:center;'>
                    Las Acciones de Mejora registradas en el PTCI (Actualizado) no coinciden con las Acciones de Mejora Registradas en Sistema al 4to Trimestre <br>
                    AM en el PTCI = {acciones_mejora_actualizadas}<br>
                    AM en Sistema = {acciones_mejora_actualizadas_AMTRI}
                  </p>
                """, unsafe_allow_html=True)



        #-------------- Parte 2: Imprimimos la tabla ------------#
        st.markdown(desc_ptci_html, unsafe_allow_html=True)








#------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#============================================= PIE DE PÁGINA DE LA SECCION PTCI - FUENTE SICOIN ==============================================

    st.markdown("""
      <div style='text-align:right; font-size:12px; color:#666; margin-top:20px;'>
        Fuente: Sistema de Control Interno (SICOIN)
      </div>
    """, unsafe_allow_html=True)

#================================= FIN DE LA SECCIÓN 5 - "Descripción de los Procesos y Acciones de Mejora" ==============================================
#--------------------------------------------------------------------------------------------------------------------------------------------------






###########################################################
###########################################################
###########################################################
# PESTAÑA REPORTES
###########################################################
###########################################################
###########################################################


with tabs[2]:

    st.markdown("<h2>📋 CONSOLIDACIÓN DE LAS BASES DE DATOS SICOIN 📋</h2><p>Información Actualizada al 13/06/2025.</p>", unsafe_allow_html=True)

    import unicodedata
    import pandas as pd

    # Funciones de normalización
    def normalize_name(name):
        return str(name).strip().lower()

    def normalize_text(text):
        return unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode('utf-8').strip().lower()

    # Funciones de estilo para colorear la fila completa según verificación
    def style_row_instituciones(row):
        # Para la tabla de instituciones, se verifica la columna "¿Coincide el Nombre de la Institución?"
        if row["¿Coincide el Nombre de la Institución?"] == "✅":
            return ['background-color: #d2f8d2; color: green'] * len(row)
        elif row["¿Coincide el Nombre de la Institución?"] == "❌":
            return ['background-color: #f9d2d2; color: red'] * len(row)
        else:
            return [''] * len(row)

    def style_row_control(row):
        # Para el análisis de acciones de control, se verifica "¿Coincide Eliminando Duplicados?"
        if row["¿Coincide Eliminando Duplicados?"] == "✅":
            return ['background-color: #d2f8d2; color: green'] * len(row)
        elif row["¿Coincide Eliminando Duplicados?"] == "❌":
            return ['background-color: #f9d2d2; color: red'] * len(row)
        else:
            return [''] * len(row)

    def style_row_mejora(row):
        # Para el análisis de acciones de mejora, se considera que la diferencia cero es correcto
        if row["Diferencia"] == 0:
            return ['background-color: #d2f8d2; color: green'] * len(row)
        else:
            return ['background-color: #f9d2d2; color: red'] * len(row)

    # Función de estilo para los registros duplicados (todos en rojo)
    def style_row_dup(row):
        return ['background-color: #f9d2d2; color: red'] * len(row)



    ##########################################
    # BLOQUE 0: Comparación de nombres institucionales (SICOIN vs PEF 2025)
    ##########################################

    st.markdown('<p class="section-title">📋 Comparación de Nombres Institucionales (SICOIN vs PEF 2025)</p>', unsafe_allow_html=True)
    st.markdown("""
    ✅ Indica que el nombre coincide con el PEF 2025.
    
    ❌ Indica que no coincide (lo que requiere actualización).
      """)


# Procesar y renombrar la lista de instituciones (df5) a nombres amigables
    df_instituciones = df5.copy()

    df_instituciones.rename(columns={
        "NOMBRE_SICOIN": "Nombre de las Instituciones en el Sistema SICOIN",
        "SECTOR_SICOIN": "Nombre de los Sectores en el Sistema SICOIN",
        "SECTOR_PEF": "Sector Según el PEF 2025",
        "NOMBRE_PEF": "Nombre de la Institución Según el PEF 2025",
        "COINCIDE": "¿Coincide el Nombre de la Institución?"
    }, inplace=True)

    # Función para aplicar estilo a las filas según la coincidencia
    def style_row_instituciones(row):
        if row["¿Coincide el Nombre de la Institución?"] == "✅":
            # Fondo verde para coincidencia
            return ['background-color: #c8e6c9'] * len(row)
        elif row["¿Coincide el Nombre de la Institución?"] == "❌":
            # Fondo rojo para discrepancia
            return ['background-color: #ffcdd2'] * len(row)
        else:
            return [''] * len(row)

    # Expander para mostrar las discrepancias
    with st.expander("Ver Discrepancias Encontradas"):
        st.dataframe(df_instituciones.style.apply(style_row_instituciones, axis=1),
                    use_container_width=True)



    # Función de estilo condicional para pintar los registros basura de rojo
    def style_row_instituciones_basura(row):
        # Solo pintar si el valor de '¿Coincide el Nombre de la Institución?' es "❌"
        if row['¿Coincide el Nombre de la Institución?'] == "❌":
            return ['background-color: red' for _ in row]  # Pinta toda la fila de rojo
        else:
            return [''] * len(row)  # Sin estilo si no es "❌"

    # Datos de ejemplo de instituciones (como en tu código)
    instituciones_data = [
        {
            "Nombre de las Instituciones en el Sistema SICOIN": "Institución de Prueba (Se encuentra en PTCI)",
            "Nombre de los Sectores en el Sistema SICOIN": "",
            "Nombre Correcto del Sector Según el PEF 2025": "El registro es de Prueba por lo Tanto Eliminar",
            "Nombre Correcto de la Institución Según el PEF 2025": "El registro es de Prueba por lo Tanto Eliminar",
            "¿Coincide el Nombre de la Institución?": "❌"
        },
        {
            "Nombre de las Instituciones en el Sistema SICOIN": "Instituto de Tamaulipas Demo (Se encuentra en el PTAR)",
            "Nombre de los Sectores en el Sistema SICOIN": "",
            "Nombre Correcto del Sector Según el PEF 2025": "El registro es de Prueba por lo Tanto Eliminar",
            "Nombre Correcto de la Institución Según el PEF 2025": "El registro es de Prueba por lo Tanto Eliminar",
            "¿Coincide el Nombre de la Institución?": "❌"
        },
    ]

    # Crear el DataFrame de las instituciones
    df_instituciones_basura = pd.DataFrame(instituciones_data)

    # Mostrar el título para los registros basura
    st.markdown('<p class="section-title">📋 Registros Basura</p>', unsafe_allow_html=True)

    # Expander para mostrar los registros basura
    with st.expander("Ver Registros Basura"):
        st.dataframe(df_instituciones_basura.style.apply(style_row_instituciones_basura, axis=1), use_container_width=True)


    # --------------------------------------------------------------------------------
    # Tabla para las modificaciones necesarias a las Bases del SICOIN

    # Función de estilo condicional para la tabla de modificaciones:
    # - Si "¿Requiere modificación?" es "✅" se pinta de verde (columnas suficientes)
    # - Si es "❌" se pinta de rojo (requiere modificación)
    def style_modificaciones(row):
        if row['¿Contiene Datos Suficientes?'] == "✅":
            return ['background-color: lightgreen' for _ in row]
        else:
            return ['background-color: red' for _ in row]

    # Datos de ejemplo para las modificaciones, usando palomita y tache
    data_modificaciones = [
        {"Base SICOIN": "PTCI",         "¿Contiene Datos Suficientes?": "✅", "Modificación a realizar": ""},
        {"Base SICOIN": "PTAR",         "¿Contiene Datos Suficientes?": "✅", "Modificación a realizar": ""},
        {"Base SICOIN": "ACTrimestral", "¿Contiene Datos Suficientes?": "❌", "Modificación a realizar": 'Añadir Columna "Detalle del Riesgo"'},
        {"Base SICOIN": "AMTrimestral", "¿Contiene Datos Suficientes?": "❌", "Modificación a realizar": 'Añadir Columna "Sector"'}
    ]

    # Crear el DataFrame para las modificaciones
    df_modificaciones = pd.DataFrame(data_modificaciones)

    # Mostrar el título y la leyenda
    st.markdown('<p class="section-title">📋 Modificaciones Necesarias a las Bases del SICOIN</p>', unsafe_allow_html=True)
    st.markdown("""
    ✅ Indica que las columnas son suficientes para elaborar reportes estadísticos.

    ❌ Indica que requiere de modificaciones.
    """)


    # Expander para mostrar la tabla de modificaciones
    with st.expander("Ver Modificaciones"):
        st.dataframe(df_modificaciones.style.apply(style_modificaciones, axis=1), use_container_width=True)



    ##########################################
    # BLOQUE 1: Verificación de Acciones de Control (PTAR vs ACTRI)
    ##########################################
    st.markdown('<p class="section-title">📝 Verificación de Acciones de Control (PTAR vs ACTRI)</p>', unsafe_allow_html=True)
    st.markdown("""
    En esta sección se verifica que el total de acciones de control reportadas en el PTAR coincida con las registradas en el SISTEMA (Sin considerar Acciones Duplicadas).
    
    ✅ Indica que el número de acciones registradas (Sin duplicados) coincide con el total del PTAR
    
    ❌ Indica que existe una discrepancia.
    """)

    # Normalización de nombres para agrupación (se utiliza df1 y df2)
    df1["Institución_N"] = df1["Institución"].apply(normalize_text)
    df2["Institución_N"] = df2["Institución"].apply(normalize_text)

    # Agrupación en PTAR (tomando el primer valor de AC_Total por institución y año)
    ptar_group = df1.groupby(["Institución_N", "Año"], as_index=False)["AC_Total"].first()

    # Para ACTRI: total de acciones (conteo) y cantidad de acciones únicas (según clave AC)
    actri_group_all = df2.groupby(["Institución_N", "Año"], as_index=False).size().rename(columns={"size": "Acciones_ACTRI"})
    actri_group_unique = df2.groupby(["Institución_N", "Año"], as_index=False)["AC"].nunique().rename(columns={"AC": "Acciones_ACTRI_Unique"})

    # Duplicados en ACTRI
    dup_count = df2.groupby(["Institución_N", "Año", "AC"], as_index=False).size()
    dup_entries = dup_count[dup_count["size"] > 1]
    dup_summary = dup_entries.groupby(["Institución_N", "Año"], as_index=False)["size"].agg({"Cantidad_Duplicados": lambda x: x.sum() - len(x)})

    # Merge de los datos de control
    control_merge = pd.merge(ptar_group, actri_group_all, on=["Institución_N", "Año"], how="outer")
    control_merge = pd.merge(control_merge, actri_group_unique, on=["Institución_N", "Año"], how="outer")
    control_merge = pd.merge(control_merge, dup_summary, on=["Institución_N", "Año"], how="left")

    # Rellenar NaN y convertir a entero
    control_merge["AC_Total"] = control_merge["AC_Total"].fillna(0).astype(int)
    control_merge["Acciones_ACTRI"] = control_merge["Acciones_ACTRI"].fillna(0).astype(int)
    control_merge["Acciones_ACTRI_Unique"] = control_merge["Acciones_ACTRI_Unique"].fillna(0).astype(int)
    control_merge["Cantidad_Duplicados"] = control_merge["Cantidad_Duplicados"].fillna(0).astype(int)

    # Calcular la diferencia (usando el total vs. el conteo sin duplicados)
    control_merge["Diferencia"] = control_merge["AC_Total"] - control_merge["Acciones_ACTRI"]
    control_merge["Duplicado"] = control_merge["Cantidad_Duplicados"].apply(lambda x: "Sí" if x > 0 else "No")
    control_merge["¿Coincide Eliminando Duplicados?"] = control_merge.apply(
        lambda row: "✅" if row["AC_Total"] == row["Acciones_ACTRI_Unique"] else "❌",
        axis=1
    )

    # Extraer el nombre original de la institución (primer valor por grupo en df1) y hacer merge
    orig_names = df1.groupby(["Institución_N", "Año"], as_index=False)["Institución"].first()
    control_merge = pd.merge(orig_names, control_merge, on=["Institución_N", "Año"], how="right")

    # Omitir la columna 'Institución_N'
    if "Institución_N" in control_merge.columns:
        control_merge.drop(columns=["Institución_N"], inplace=True)

    # Renombrar columnas a etiquetas amigables
    control_merge.rename(columns={
        "AC_Total": "Acciones de Control en PTAR",
        "Acciones_ACTRI": "Acciones de Control en SISTEMA",
        "Duplicado": "¿El Sistema Contiene Duplicados?",
        "Cantidad_Duplicados": "Cantidad de AC Duplicadas",
        "Acciones_ACTRI_Unique": "Cantidad de AC Eliminando Duplicidad"
    }, inplace=True)

    # Reordenar columnas según lo solicitado:
    # (Año, Institución, Acciones de Control en PTAR, Acciones de Control en SISTEMA, Diferencia,
    #  ¿El Sistema Contiene Duplicados?, Cantidad de AC Duplicadas, Cantidad de AC Eliminando Duplicidad,
    #  ¿Coincide Eliminando Duplicados?)
    control_merge = control_merge[[
        "Año",
        "Institución",
        "Acciones de Control en PTAR",
        "Acciones de Control en SISTEMA",
        "Diferencia",
        "¿El Sistema Contiene Duplicados?",
        "Cantidad de AC Duplicadas",
        "Cantidad de AC Eliminando Duplicidad",
        "¿Coincide Eliminando Duplicados?"
    ]]

    # Ordenar para visualizar
    control_merge.sort_values(["Año", "Institución"], inplace=True)

    # Primer expander: Tabla completa de análisis (aplicando estilo a la fila completa)
    with st.expander("Ver Análisis Completo de Acciones de Control"):
        st.dataframe(control_merge.style.apply(style_row_control, axis=1),
                     use_container_width=True)

    # Segundo expander: Resumen de Claves de Acción Duplicadas en ACTRI (con nombres reales y filas en rojo)
    dup_ac_counts = df2.groupby(['Institución', 'Año', 'AC'], as_index=False).size()
    dup_ac_counts = dup_ac_counts[dup_ac_counts['size'] > 1]
    with st.expander("Resumen de Claves de Acción Duplicadas en ACTRI"):
        if not dup_ac_counts.empty:
            dup_ac_counts.rename(columns={
                "size": "Cantidad de Duplicados",
                "AC": "Clave AC"
            }, inplace=True)
            st.dataframe(dup_ac_counts.style.apply(style_row_dup, axis=1),
                         use_container_width=True)
        else:
            st.success("✅ No se encontraron claves de acción duplicadas en ACTRI.")

    # Tercer expander: Registros con discrepancia, renombrado a "Ver Registros con Discrepancia Aún Después de Eliminar Duplicados"
    no_coincidencia = control_merge[control_merge["¿Coincide Eliminando Duplicados?"] == "❌"]
    with st.expander("Ver Registros con Discrepancia Aún Después de Eliminar Duplicados"):
        if not no_coincidencia.empty:
            st.dataframe(no_coincidencia.style.apply(style_row_control, axis=1),
                         use_container_width=True)
        else:
            st.success("✅ Todas las acciones coinciden después de eliminar duplicados")



    ##########################################
    # BLOQUE 2: Verificación de Acciones de Mejora (PTCI vs AMTRI - Trimestre 4)
    ##########################################
    st.markdown('<p class="section-title">📈 Verificación de Acciones de Mejora (PTCI vs AMTRI - Trimestre 4)</p>', unsafe_allow_html=True)
    st.markdown("""
    En este bloque se comparan las acciones de mejora reportadas en el PTCI con las registradas en el SISTEMA AMTRI para el Trimestre 4.
    Se calcula la diferencia entre ambos valores; una diferencia de 0 (fondo verde) indica conformidad, mientras que cualquier diferencia (fondo rojo) señala una discrepancia.

    En esta sección se verifica que el total de acciones de mejora reportadas en el PTCI coincida con las registradas en el SISTEMA el último trimestre reportado (Sin considerar Acciones Duplicadas).
    
    ✅ Indica que el número de acciones registradas (Sin duplicados) coincide con el total del PTCI
    
    ❌ Indica que existe una discrepancia.


    """)

    # Normalización de nombres
    df3["Institución_N"] = df3["Institución"].apply(normalize_text)
    df4["Institución_N"] = df4["Institución"].apply(normalize_text)

    # Agrupar en PTCI (tomando el primer valor de TotalAcciones_de_Mejora_Programa_Actualizado)
    ptci_group = df3.groupby(["Institución_N", "Año"], as_index=False)["TotalAcciones_de_Mejora_Programa_Actualizado"].first()

    # Filtrar AMTRI solo para el trimestre 4 y agrupar (conteo de registros)
    amtri_filtered = df4[df4["Trimestre"] == 4]
    amtri_group = amtri_filtered.groupby(["Institución_N", "Año"], as_index=False).size().rename(columns={"size": "Acciones_AMTRI"})

    # Merge para comparar
    mejora_merge = pd.merge(ptci_group, amtri_group, on=["Institución_N", "Año"], how="outer")
    mejora_merge["TotalAcciones_de_Mejora_Programa_Actualizado"] = mejora_merge["TotalAcciones_de_Mejora_Programa_Actualizado"].fillna(0).astype(int)
    mejora_merge["Acciones_AMTRI"] = mejora_merge["Acciones_AMTRI"].fillna(0).astype(int)
    mejora_merge["Diferencia"] = mejora_merge["TotalAcciones_de_Mejora_Programa_Actualizado"] - mejora_merge["Acciones_AMTRI"]

    # Agregar el nombre original de la institución (desde df3) y eliminar la columna normalizada
    orig_names_ptci = df3.groupby(["Institución_N", "Año"], as_index=False)["Institución"].first()
    mejora_merge = pd.merge(orig_names_ptci, mejora_merge, on=["Institución_N", "Año"], how="right")
    if "Institución_N" in mejora_merge.columns:
        mejora_merge.drop(columns=["Institución_N"], inplace=True)

    # Renombrar columnas a etiquetas amigables
    mejora_merge.rename(columns={
        "TotalAcciones_de_Mejora_Programa_Actualizado": "Acciones de Mejora en PTCI",
        "Acciones_AMTRI": "Acciones de Mejora en SISTEMA"
    }, inplace=True)

    # Reordenar columnas: (Año, Institución, Acciones de Mejora en PTCI, Acciones de Mejora en SISTEMA, Diferencia)
    mejora_merge = mejora_merge[[
        "Año",
        "Institución",
        "Acciones de Mejora en PTCI",
        "Acciones de Mejora en SISTEMA",
        "Diferencia"
    ]]
    mejora_merge.sort_values(["Año", "Institución"], inplace=True)

    with st.expander("Ver Análisis de Acciones de Mejora"):
        if not mejora_merge.empty:
            st.dataframe(mejora_merge.style.apply(style_row_mejora, axis=1),
                         use_container_width=True)
        else:
            st.success("✅ No se encontraron discrepancias en las acciones de mejora.")


    ##########################################
    # Resumen Final de los Análisis
    ##########################################
    st.markdown("""
    ---
    ### Resumen General de Análisis
    - **Cantidad de Registros de Prueba que aparecen en las bases de datos (eliminar estos registros):** 2
      - Institución de Prueba
      - Instituto de Tamaulipas Demo

    *Nota: Los valores numéricos anteriores son los resultados obtenidos de la consolidación real de las bases de datos.*
    """, unsafe_allow_html=True)




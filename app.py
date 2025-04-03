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
@st.cache_resource(ttl="1h", show_spinner="Descargando datos actualizados desde Sheets...")
def descargar_y_cargar_datos():
    # Conecta usando las credenciales de la sección correspondiente
    gc = gspread.service_account_from_dict(st.secrets['gcp_service_account'])

    # Abre el libro de Sheets llamado "SICOIN_BASE"
    sh = gc.open("SICOIN_BASE")

    # Selecciona las hojas correspondientes
    worksheet1 = sh.worksheet("PTAR")    # Hoja para PTAR
    worksheet2 = sh.worksheet("ACTRI")   # Hoja para ACTRI
    worksheet3 = sh.worksheet("PTCI")    # Hoja para PTCI
    worksheet4 = sh.worksheet("AMTRI")   # Hoja para AMTRI

    # Obtén todos los registros y conviértelos a DataFrames
    return {
        "PTAR": pd.DataFrame(worksheet1.get_all_records()),
        "ACTRI": pd.DataFrame(worksheet2.get_all_records()),
        "PTCI": pd.DataFrame(worksheet3.get_all_records()),
        "AMTRI": pd.DataFrame(worksheet4.get_all_records())
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
#========================= OBTIENE TAMBIÉN LOS INDICADORES PRINCIPALES DE ACCIONES DE CONTROL Y RIESGOS (Stats) ==============================================
#==================================== OBTIENE TAMBIÉN LAS TABLAS: RIESGOS, CUADRANTE Y ESTRATEGIA ==============================================
def generate_dashboard(institucion, year, sector):
  #----- Parte 1 de la función: Calcula data para reportes -----#
    if sector != "Todas":                                       # Caso 1: Sector != "Todas"
        filtered = df1[(df1['Sector'] == sector) & (df1['Año'] == year)]
        instituciones_list = "<ul style='margin:0; padding-left:20px;'>" + "".join(
          f"<li>{inst}</li>" for inst in filtered['Institución'].unique()) + "</ul>"
        header = f"""
        <div style='background-color:#f8f9fa; padding:15px; border-radius:10px; margin-bottom:20px; box-shadow:0 2px 4px rgba(0,0,0,0.1);'>
          <h3 style='color:#621132; margin:0; font-size:14px;'>
            Sector: {sector}<br>
            Instituciones: {instituciones_list}
          </h3>
        </div>
        """
        data = filtered.sum(numeric_only=True).to_dict()
        for t in trimestres:
            key = f"{t}Cumplimiento"
            if key in filtered.columns:
                avg_value = pd.to_numeric(filtered[key], errors='coerce').fillna(0).mean()
                data[key] = round(avg_value, 2)
    else:                                                     # Caso 2: sector = "Todas" (Filtro por Institución y Año)
        filtered = df1[(df1['Institución'] == institucion) & (df1['Año'] == year)]
        header = f"""
        <div style='background-color:#f8f9fa; padding:15px; border-radius:10px; margin-bottom:20px; box-shadow:0 2px 4px rgba(0,0,0,0.1);'>
          <h3 style='color:#621132; margin:0; font-size:14px;'>
            Institución: {institucion}<br>
            Sector: {filtered['Sector'].iloc[0]}<br>
            Siglas: {filtered['Siglas'].iloc[0]}
          </h3>
        </div>
        """
        data = filtered.iloc[0].to_dict()

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
    risk_html = """
    <div style='overflow-x:auto; margin-bottom:20px;'>
      <table style='width:100%; border-collapse:collapse;'>
        <tr style='background-color:#621132; color:white;'>
    """
    for col in risk_cols:
        risk_html += f"<th style='padding:12px; text-align:center; border:1px solid #ddd;'>{col}</th>"
    risk_html += "</tr><tr>"
    for col in risk_cols:
        risk_html += f"<td style='padding:12px; text-align:center; border:1px solid #ddd; font-weight:500;'>{data[col]}</td>"
    risk_html += "</tr></table></div>"

    cuadrante_html = """
    <div style='overflow-x:auto; margin-bottom:20px;'>
      <table style='width:100%; border-collapse:collapse;'>
        <tr style='background-color:#621132; color:white;'>
    """
    colors = ['#dc3545', '#ffc107', '#28a745', '#007bff']
    for col, color in zip(cuadrante_cols, colors):
        cuadrante_html += f"<th style='background-color:{color}; padding:12px; text-align:center; border:1px solid #ddd;'>{col}</th>"
    cuadrante_html += "</tr><tr>"
    for col in cuadrante_cols:
        cuadrante_html += f"<td style='padding:12px; text-align:center; border:1px solid #ddd; font-weight:500;'>{data[col]}</td>"
    cuadrante_html += "</tr></table></div>"

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
st.markdown(header, unsafe_allow_html=True)

#================================================== CREACIÓN DE PESTAÑAS PTAR, PTCI Y REPORTES =========================================================
tabs = st.tabs(["PTAR", "PTCI", "REPORTES"])

#===================================================== MOSTRAR RESULTADOS EN LA PESTAÑA PTAR ==============================================
with tabs[0]:
    st.markdown(stats, unsafe_allow_html=True)

    st.markdown("""
      <div style='background-color:#621132; color:white; padding:10px; border-radius:5px; margin-bottom:20px; text-align:center;'>
        Clasificación de Riesgos
      </div>
    """, unsafe_allow_html=True)
    st.markdown(risk_html, unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
          <div style='background-color:#621132; color:white; padding:10px; border-radius:5px; margin-bottom:20px; text-align:center;'>
            Cuadrante
          </div>
        """, unsafe_allow_html=True)
        st.markdown(cuadrante_html, unsafe_allow_html=True)
    with col2:
        st.markdown("""
          <div style='background-color:#621132; color:white; padding:10px; border-radius:5px; margin-bottom:20px; text-align:center;'>
            Estrategia
          </div>
        """, unsafe_allow_html=True)
        st.markdown(estrategia_html, unsafe_allow_html=True)

    st.markdown("""
      <div style='background-color:#621132; color:white; padding:10px; border-radius:5px; margin-bottom:20px; text-align:center;'>
        Seguimiento de las Acciones de Control
      </div>
    """, unsafe_allow_html=True)

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

    plot_data = []
    for t in trimestres:
        for estado in estados:
            plot_data.append({'Trimestre': f' {t}', 'Estado': estado, 'Cantidad': data.get(f"{t}{estado}", 0)})
    fig = px.bar(pd.DataFrame(plot_data), x='Trimestre', y='Cantidad', color='Estado',
                 barmode='group', height=400,
                 color_discrete_map={'Sin_Avances': '#dc3545', 'En_Proceso': '#ffc107',
                                     'Concluidas': '#28a745', 'Cumplimiento': '#6610f2'})
    fig.update_layout(
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(color='#333'),
        xaxis=dict(title=None, gridcolor='#f0f0f0'),
        yaxis=dict(title=None, gridcolor='#f0f0f0'),
        legend=dict(title=None),
        margin=dict(l=20, r=20, t=50, b=20)
    )
    for trace in fig.data:
        if trace.name == "Cumplimiento":
            trace.text = [f"{y}%" for y in trace.y]
            trace.textposition = 'outside'
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("""
          <div style='background-color:#621132; color:white; padding:10px; border-radius:5px; margin-top:30px; margin-bottom:30px; text-align:center;'>
        Descripción de los Riesgos y las Acciones de Control
      </div>
    """, unsafe_allow_html=True)

    if sector != "Todas":
        filtered_df2 = df2[(df2['Sector'] == sector) & (df2['Año'] == year)]
    else:
        filtered_df2 = df2[(df2['Institución'] == institucion) & (df2['Año'] == year)]

    if int(data['AC_Total']) != len(filtered_df2):
        st.markdown("""
          <p style='color:red; font-weight:bold; text-align:center;'>
            Las acciones de control registradas en el PTAR no coinciden con las Acciones de Control Registradas
          </p>
        """, unsafe_allow_html=True)

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
    for _, row in filtered_df2.iterrows():
        avance_inst = f"{round(row['Avance_Institución'], 2)}%" if pd.notna(row['Avance_Institución']) else ""
        avance_oic = f"{round(row['Avance_OIC'], 2)}%" if pd.notna(row['Avance_OIC']) else ""
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
    table_html += "</table></div>"
    st.markdown(table_html, unsafe_allow_html=True)

    st.markdown("""
      <div style='text-align:right; font-size:12px; color:#666; margin-top:20px;'>
        Fuente: Sistema de Control Interno (SICOIN)
      </div>
    """, unsafe_allow_html=True)

#============================================= FIN DE LA PESTAÑA PTAR =========================================================

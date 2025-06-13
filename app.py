import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import io
import numpy as np

# Excel conditional formatting
import xlsxwriter

# ────────────────────────────────────────────────────────────
# Reglas de color por flujo médico
thresholds = {
    "N4-5A": [
        {"rule":"less",    "desde":"00:30:00", "hasta":None,      "color":"#96cc6c"},
        {"rule":"between","desde":"00:30:01", "hasta":"00:45:00","color":"#fdfd96"},
        {"rule":"between","desde":"00:45:01", "hasta":"01:30:00","color":"#f5c15b"},
        {"rule":"greater", "desde":"01:30:01", "hasta":None,      "color":"#ff6961"},
    ],
    "N4-5P": [{"rule":"less",    "desde":"00:30:00", "hasta":None,      "color":"#96cc6c"},
        {"rule":"between","desde":"00:30:01", "hasta":"00:45:00","color":"#fdfd96"},
        {"rule":"between","desde":"00:45:01", "hasta":"01:30:00","color":"#f5c15b"},
        {"rule":"greater", "desde":"01:30:01", "hasta":None,      "color":"#ff6961"},],
    "N4-5T": [{"rule":"less",    "desde":"00:30:00", "hasta":None,      "color":"#96cc6c"},
        {"rule":"between","desde":"00:30:01", "hasta":"00:45:00","color":"#fdfd96"},
        {"rule":"between","desde":"00:45:01", "hasta":"01:30:00","color":"#f5c15b"},
        {"rule":"greater", "desde":"01:30:01", "hasta":None,      "color":"#ff6961"},],
    "N3A": [{"rule":"less",    "desde":"00:15:00", "hasta":None,      "color":"#96cc6c"},
        {"rule":"between","desde":"00:15:01", "hasta":"00:30:00","color":"#fdfd96"},
        {"rule":"greater", "desde":"00:30:01", "hasta":None,      "color":"#ff6961"},],
    "N3T": [{"rule":"less",    "desde":"00:15:00", "hasta":None,      "color":"#96cc6c"},
        {"rule":"between","desde":"00:15:01", "hasta":"00:30:00","color":"#fdfd96"},
        {"rule":"greater", "desde":"00:30:01", "hasta":None,      "color":"#ff6961"},],
    "N3P": [{"rule":"less",    "desde":"00:15:00", "hasta":None,      "color":"#96cc6c"},
        {"rule":"between","desde":"00:15:01", "hasta":"00:30:00","color":"#fdfd96"},
        {"rule":"greater", "desde":"00:30:01", "hasta":None,      "color":"#ff6961"},],
     

}

# Función para convertir color hex a RGB normalizado
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16)/255.0 for i in (0, 2, 4))

# ────────────────────────────────────────────────────────────

def minutos_a_hhmmss(minutos):
    total = int(minutos * 60)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

st.set_page_config(page_title="Informe Guardia", layout="wide")
st.title("📊 Informe Guardia - Flujo Pacientes y Recursos")

menu = st.sidebar.radio(
    "Menú principal",
    ("Carga de datos", "Estadística demoras", "Estadística por médicos")
)

# Variables globales para compartir datos entre secciones (opcional)
if 'df' not in st.session_state:
    st.session_state.df = None
if 'uploaded' not in st.session_state:
    st.session_state.uploaded = None
    
    
# 1) Carga de datos
if menu == "Carga de datos":
    st.header("Carga de datos")
    uploaded = st.file_uploader("📂 Subí el archivo de datos", type=["csv","xls","xlsx","ods"])
    if not uploaded:
        st.info("Espera archivo para comenzar.")
        st.stop()

    try:
        ext = uploaded.name.lower().split('.')[-1]
        if ext == 'csv':
            df = pd.read_csv(uploaded, sep=';', decimal=',')
        elif ext in ['xls','xlsx']:
            df = pd.read_excel(uploaded, sheet_name="Base Madre")
        elif ext == 'ods':
            df = pd.read_excel(uploaded, sheet_name="Base Madre", engine='odf')
        else:
            st.error("❌ Formato no soportado.")
            st.stop()
        st.success("✅ Archivo cargado correctamente. Puede continuar con las estadísticas")
        st.session_state.df = df
        st.session_state.uploaded = uploaded
    except Exception as e:
        st.error(f"❌ Error al cargar el archivo: {str(e)}")
        st.stop()


elif menu == "Estadística demoras":
    st.header("Estadística demoras")
    if st.session_state.df is None:
        st.info("Primero debés cargar un archivo en la sección *Carga de datos*.")
        st.stop()

    else:
        df = st.session_state.df
        uploaded = st.session_state.uploaded
        demora_tipo = st.radio("Tipo de Demora:", ["Máxima","Promedio"])
        flujos = df['Flujo_Pacientes'].dropna().unique().tolist()
        flujo_sel = st.multiselect("Flujos Pacientes (obligatorio):", flujos)
        responsables = df['Responsable'].dropna().unique().tolist()
        resp_sel = st.multiselect("Responsable (opcional):", responsables)

        if st.button("🚀 Generar Informe"):
            if not flujo_sel:
                st.warning("⚠️ Debe seleccionar al menos un flujo.")
                st.stop()

            try:
                # 3) Filtrado y agregación
                dff = df[df['Flujo_Pacientes'].isin(flujo_sel)].copy()
                if resp_sel:
                    dff = dff[dff['Responsable'].isin(resp_sel)]
                dff['Fecha'] = pd.to_datetime(dff['Fecha'], format='%d/%m/%y', errors='coerce')\
                            .dt.strftime('%d/%m/%y')
                if demora_tipo == 'Máxima':
                    # Tomar la demora máxima de cada flujo, sumar entre flujos
                    tmp = dff.groupby(['Fecha', 'time_slot_ini', 'Flujo_Pacientes'])['Tiempo_espera__min'].max().reset_index()
                    df_final = tmp.groupby(['Fecha', 'time_slot_ini'])['Tiempo_espera__min'].sum().reset_index(name='demora_maxima')
                elif demora_tipo == 'Promedio':
                    # Tomar el promedio de cada flujo, sumar entre flujos
                    tmp = dff.groupby(['Fecha', 'time_slot_ini', 'Flujo_Pacientes'])['Tiempo_espera__min'].mean().reset_index()
                    df_final = tmp.groupby(['Fecha', 'time_slot_ini'])['Tiempo_espera__min'].sum().reset_index(name='demora_maxima')

                # Pacientes
                dff_med = dff if len(flujo_sel)==1 else dff[dff['Grupo']=='Médico']
                cnt = dff_med.groupby(['Fecha','time_slot_ini'])['Nro Paciente'].count().reset_index(name='cantidad_pacientes')
                df_final = df_final.merge(cnt, on=['Fecha','time_slot_ini'], how='left')

                # Recursos Médico/Triage
                rec = dff[dff['Matricula']!=0].groupby(['Fecha','time_slot_ini','Grupo'])['Matricula']\
                    .nunique().reset_index(name='matriculas')
                rec['Grupo'] = rec['Grupo'].replace({'Enfermería':'Triage'})
                piv_rec = rec.pivot(index=['Fecha','time_slot_ini'], columns='Grupo', values='matriculas').fillna(0).reset_index()
                for col in ['Médico','Triage']:
                    if col not in piv_rec: 
                        piv_rec[col] = 0
                df_final = df_final.merge(piv_rec, on=['Fecha','time_slot_ini'], how='left')

                # Llenar NaNs
                df_final['cantidad_pacientes'] = df_final['cantidad_pacientes'].fillna(0)
                df_final['Médico'] = df_final['Médico'].fillna(0)
                df_final['Triage'] = df_final['Triage'].fillna(0)

                # Formato y orden de slots
                df_final['demora_fmt'] = df_final['demora_maxima'].apply(minutos_a_hhmmss)
                df_final['slot_sort'] = df_final['time_slot_ini'].str.extract(r"\[(\d+)-").astype(int)
                df_final.sort_values(['slot_sort','Fecha'], inplace=True)
                slots = df_final['time_slot_ini'].unique().tolist()

                # Pivot para Streamlit
                pivot = df_final.pivot(index='time_slot_ini', columns='Fecha')[['demora_fmt','cantidad_pacientes','Médico','Triage']]
                fechas_disponibles = sorted(df_final['Fecha'].unique())
                cols = [(m,f) for f in fechas_disponibles for m in ['demora_fmt','cantidad_pacientes','Médico','Triage']]
                pivot = pivot[cols].reindex(slots)
                
                for col in ['cantidad_pacientes','Médico','Triage']:
                    pivot[col] = pivot[col].fillna(0).astype(int)

                # 4) Estilos condicionales para Streamlit
                pivot_num = df_final.pivot(index='time_slot_ini', columns='Fecha')['demora_maxima'].reindex(slots)
                style_df = pd.DataFrame('', index=pivot.index, columns=pivot.columns)
                
                flujo_med = None
                if 'Médico' in dff['Grupo'].unique():
                    flujo_med = next((f for f in flujo_sel if f in thresholds), None)
                    if flujo_med:
                        reglas = thresholds[flujo_med]
                        for s in pivot_num.index:
                            for f in pivot_num.columns:
                                if pd.isna(pivot_num.loc[s,f]): 
                                    continue
                                v = pivot_num.loc[s,f]
                                td = pd.to_timedelta(v, unit='m')
                                for rg in reglas:
                                    d0 = pd.to_timedelta(rg['desde'])
                                    d1 = pd.to_timedelta(rg['hasta']) if rg['hasta'] else None
                                    cond = ((rg['rule']=='less' and td<=d0) or
                                            (rg['rule']=='greater' and td>d0) or
                                            (rg['rule']=='between' and d0<=td<=d1))
                                    if cond:
                                        style_df.loc[s,('demora_fmt',f)] = f"background-color:{rg['color']}"
                                        break
                
                st.write(pivot.style.apply(lambda _: style_df, axis=None))

                # 5) Gráficos en Streamlit
                st.subheader("📊 Gráficos")
                for metric in ['cantidad_pacientes','demora_maxima','Médico','Triage']:
                    dfg = df_final.groupby(['time_slot_ini','Fecha'])[metric].max().unstack().loc[slots]
                    fig, ax = plt.subplots(figsize=(12,6))
                    dfg.plot(kind='bar', ax=ax)
                    ax.set_title(f"{metric.replace('_',' ').title()} por hora - Demora {demora_tipo}")
                    ax.set_xlabel("Franja horaria")
                    ax.set_ylabel(metric.replace('_',' ').title())
                    ax.legend(title="Fecha", bbox_to_anchor=(1,1))
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    st.pyplot(fig)
                    plt.close()

                # 6) Descargar Excel con colores 
                st.subheader("⬇️ Descargar Excel")
                buf_xl = io.BytesIO()
                with pd.ExcelWriter(buf_xl, engine='xlsxwriter') as writer:
                    pivot.to_excel(writer, sheet_name='Informe', index=True)
                    wb = writer.book
                    ws = writer.sheets['Informe']
                    
                    if flujo_med and flujo_med in thresholds:
                        fechas = pivot.columns.levels[1] if hasattr(pivot.columns, 'levels') else fechas_disponibles
                        for ci, fch in enumerate(fechas, start=1):
                            rng = f"{chr(65+ci)}2:{chr(65+ci)}{len(pivot)+1}"
                            for rg in thresholds[flujo_med]:
                                d0 = pd.to_timedelta(rg['desde']).total_seconds()/60
                                d1 = pd.to_timedelta(rg['hasta']).total_seconds()/60 if rg['hasta'] else None
                                fmt = wb.add_format({'bg_color':rg['color']})
                                if rg['rule']=='between' and d1 is not None:
                                    ws.conditional_format(rng, {'type':'cell','criteria':'between','minimum':d0,'maximum':d1,'format':fmt})
                                elif rg['rule']=='greater':
                                    ws.conditional_format(rng, {'type':'cell','criteria':'>','value':d0,'format':fmt})
                                elif rg['rule']=='less':
                                    ws.conditional_format(rng, {'type':'cell','criteria':'<','value':d0,'format':fmt})
                
                buf_xl.seek(0)
                st.download_button("📥 Descargar Excel", buf_xl,
                                "informe_guardia_colores.xlsx",
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

                # 7) Descargar PDF MEJORADO - Sin títulos en medio de tablas
                st.subheader("⬇️ Descargar PDF")
                buf_pdf = io.BytesIO()
                
                with PdfPages(buf_pdf) as pdf:
                    # ═══════════════════════════════════════
                    # PÁGINA DE CARÁTULA
                    # ═══════════════════════════════════════
                    fig = plt.figure(figsize=(8.27, 11.69))
                    ax = fig.add_subplot(111)
                    ax.axis("off")
                    
                    # Título principal
                    ax.text(0.5, 0.8, "Informe Guardia", ha="center", va="center", 
                        fontsize=28, weight='bold', transform=ax.transAxes)
                    
                    # Información del informe
                    ax.text(0.5, 0.65, f"Flujos: {', '.join(flujo_sel)}", ha="center", va="center", 
                        fontsize=16, transform=ax.transAxes)
                    ax.text(0.5, 0.6, f"Demora: {demora_tipo}", ha="center", va="center", 
                        fontsize=16, transform=ax.transAxes)
                    
                    # Fecha de generación
                    from datetime import datetime
                    fecha_generacion = datetime.now().strftime("%d/%m/%Y %H:%M")
                    ax.text(0.5, 0.3, f"Generado el: {fecha_generacion}", ha="center", va="center", 
                        fontsize=12, style='italic', transform=ax.transAxes)
                    
                    pdf.savefig(fig, bbox_inches="tight")
                    plt.close(fig)

                    # ═══════════════════════════════════════
                    # PÁGINAS DE TABLAS DE DATOS
                    # ═══════════════════════════════════════
                    fechas_por_pagina = 3
                    num_paginas_tabla = (len(fechas_disponibles) + fechas_por_pagina - 1) // fechas_por_pagina
                    
                    for pagina in range(num_paginas_tabla):
                        fig = plt.figure(figsize=(16, 11))
                        
                        # Calcular fechas para esta página
                        inicio_fecha = pagina * fechas_por_pagina
                        fin_fecha = min(inicio_fecha + fechas_por_pagina, len(fechas_disponibles))
                        fechas_pagina = fechas_disponibles[inicio_fecha:fin_fecha]
                        
                        # Filtrar datos para esta página
                        df_pagina = df_final[df_final['Fecha'].isin(fechas_pagina)].copy()
                        pivot_pagina = df_pagina.pivot(index='time_slot_ini', columns='Fecha')[['demora_fmt','cantidad_pacientes','Médico','Triage']].reindex(slots)
                        
                        # Rellenar NaNs
                        for col in ['cantidad_pacientes','Médico','Triage']:
                            pivot_pagina[col] = pivot_pagina[col].fillna(0).astype(int)
                        
                        # ═══ TÍTULO DE LA PÁGINA ═══
                        fig.suptitle(f'Informe Detallado - Página {pagina + 1} de {num_paginas_tabla}', 
                                fontsize=16, weight='bold', y=0.95)
                        
                        # ═══ PREPARAR DATOS DE LA TABLA ═══
                        tabla_data = []
                        headers = ['Franja\nHoraria']
                        
                        # Crear headers organizados por fecha
                        for fecha in fechas_pagina:
                            headers.extend([f'{fecha}\nTiempo', f'{fecha}\nPacientes', f'{fecha}\nMédicos', f'{fecha}\nTriage'])
                        
                        # Preparar filas de datos
                        for slot in slots:
                            fila = [slot]
                            for fecha in fechas_pagina:
                                try:
                                    tiempo = pivot_pagina.loc[slot, ('demora_fmt', fecha)]
                                    pacientes = pivot_pagina.loc[slot, ('cantidad_pacientes', fecha)]
                                    medicos = pivot_pagina.loc[slot, ('Médico', fecha)]
                                    triage = pivot_pagina.loc[slot, ('Triage', fecha)]
                                    
                                    fila.extend([
                                        str(tiempo) if pd.notna(tiempo) else '00:00:00',
                                        str(int(pacientes)) if pd.notna(pacientes) else '0',
                                        str(int(medicos)) if pd.notna(medicos) else '0',
                                        str(int(triage)) if pd.notna(triage) else '0'
                                    ])
                                except:
                                    fila.extend(['00:00:00', '0', '0', '0'])
                            tabla_data.append(fila)
                        
                        # ═══ CREAR Y CONFIGURAR LA TABLA ═══
                        ax = fig.add_subplot(111)
                        ax.axis("off")
                        
                        # Crear tabla centrada en el área disponible
                        table = ax.table(
                            cellText=tabla_data,
                            colLabels=headers,
                            loc='center',
                            cellLoc='center',
                            bbox=[0.05, 0.15, 0.9, 0.7]  # [x, y, width, height] en coordenadas de figura
                        )
                        
                        # Configurar estilo de la tabla
                        table.auto_set_font_size(False)
                        table.set_fontsize(9)
                        table.scale(1, 2.5)  # Escalar solo verticalmente
                        
                        # ═══ COLOREAR HEADERS ═══
                        colors_header = {
                            'Franja': '#CDCECF',    
                            'Tiempo': '#CDCECF',    
                            'Pacientes': '#CDCECF', 
                            'Médicos': '#CDCECF',   
                            'Triage': '#CDCECF'     
                        }
                        
                        for col_idx, header in enumerate(headers):
                            if 'Franja' in header:
                                color = colors_header['Franja']
                            elif 'Tiempo' in header:
                                color = colors_header['Tiempo']
                            elif 'Pacientes' in header:
                                color = colors_header['Pacientes']
                            elif 'Médicos' in header:
                                color = colors_header['Médicos']
                            elif 'Triage' in header:
                                color = colors_header['Triage']
                            else:
                                color = '#424242'
                            
                            table[(0, col_idx)].set_facecolor(color)
                            table[(0, col_idx)].set_text_props(weight='bold', color='white', fontsize=8)
                        
                        # ═══ APLICAR COLORES CONDICIONALES ═══
                        if flujo_med and flujo_med in thresholds:
                            reglas = thresholds[flujo_med]
                            
                            for row_idx, slot in enumerate(slots):
                                for fecha_idx, fecha in enumerate(fechas_pagina):
                                    if fecha in df_pagina['Fecha'].values:
                                        df_slot = df_pagina[(df_pagina['time_slot_ini'] == slot) & (df_pagina['Fecha'] == fecha)]
                                        if not df_slot.empty:
                                            valor_tiempo = df_slot['demora_maxima'].iloc[0]
                                            if pd.notna(valor_tiempo):
                                                td = pd.to_timedelta(valor_tiempo, unit='m')
                                                
                                                for rg in reglas:
                                                    d0 = pd.to_timedelta(rg['desde'])
                                                    d1 = pd.to_timedelta(rg['hasta']) if rg['hasta'] else None
                                                    cond = ((rg['rule']=='less' and td<=d0) or
                                                            (rg['rule']=='greater' and td>d0) or
                                                            (rg['rule']=='between' and d0<=td<=d1))
                                                    if cond:
                                                        tiempo_col = 1 + fecha_idx * 4  # Columna de tiempo
                                                        table[(row_idx + 1, tiempo_col)].set_facecolor(hex_to_rgb(rg['color']))
                                                        break
                        
                        # ═══ ALTERNAR COLORES DE FILAS ═══
                        for row_idx in range(1, len(tabla_data) + 1):
                            if row_idx % 2 == 0:
                                for col_idx in range(len(headers)):
                                    current_color = table[(row_idx, col_idx)].get_facecolor()
                                    if current_color == (1.0, 1.0, 1.0, 1.0):  # Solo si es blanco
                                        table[(row_idx, col_idx)].set_facecolor('#F8F8F8')
                        
                        # ═══ LEYENDA DE COLORES (solo en primera página) ═══
                        if flujo_med and flujo_med in thresholds and pagina == 0:
                            leyenda_text = 'Leyenda de Colores (Tiempo de Espera):\n'
                            for regla in thresholds[flujo_med]:
                                if regla['rule'] == 'less':
                                    rango = f"≤ {regla['desde']}"
                                elif regla['rule'] == 'greater':
                                    rango = f"> {regla['desde']}"
                                elif regla['rule'] == 'between':
                                    rango = f"{regla['desde']} - {regla['hasta']}"
                                
                                leyenda_text += f"● {rango}  "
                            
                            ax.text(0.05, 0.08, leyenda_text, transform=ax.transAxes, 
                                fontsize=10, weight='bold', va='top')
                        
                        pdf.savefig(fig, bbox_inches="tight")
                        plt.close(fig)

                    # ═══════════════════════════════════════
                    # PÁGINAS DE GRÁFICOS
                    # ═══════════════════════════════════════
                    metrics_info = {
                        'cantidad_pacientes': 'Cantidad de Pacientes',
                        'demora_maxima': f'Demora {demora_tipo} (minutos)',
                        'Médico': 'Recursos Médicos',
                        'Triage': 'Recursos Triage'
                    }
                    
                    for metric, title in metrics_info.items():
                        fig = plt.figure(figsize=(14, 10))
                        ax = fig.add_subplot(111)
                        
                        # Preparar datos del gráfico
                        dfg = df_final.groupby(['time_slot_ini','Fecha'])[metric].max().unstack().loc[slots]
                        
                        # Crear gráfico de barras
                        dfg.plot(kind='bar', ax=ax, width=0.8, figsize=(14, 8))
                        
                        # Configuración del gráfico
                        ax.set_title(title, fontsize=16, weight='bold', pad=30)
                        ax.set_xlabel("Franja horaria", fontsize=14)
                        ax.set_ylabel(title, fontsize=14)
                        ax.legend(title="Fecha", bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=12)
                        
                        # Rotar etiquetas del eje x
                        plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
                        
                        # Agregar grilla
                        ax.grid(True, alpha=0.3, linestyle='--')
                        
                        # Ajustar layout
                        plt.tight_layout()
                        
                        pdf.savefig(fig, bbox_inches="tight", dpi=150)
                        plt.close(fig)

                buf_pdf.seek(0)
                st.download_button("📥 Descargar PDF", buf_pdf, "informe_guardia.pdf", "application/pdf")
                
            except Exception as e:
                st.error(f"❌ Error al generar el informe: {str(e)}")
                st.write("Detalles del error:")
                st.exception(e)
elif menu == "Estadística por médicos":
    st.header("Estadística por médicos")
    st.info("🚧 Sitio en construcción. Proximamente disponible.")            

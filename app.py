# app.py

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import io

def minutos_a_hhmmss(minutos):
    total_seconds = int(minutos * 60)
    horas = total_seconds // 3600
    minutos_rest = (total_seconds % 3600) // 60
    segundos = total_seconds % 60
    return f"{horas:02d}:{minutos_rest:02d}:{segundos:02d}"

# Streamlit app
st.set_page_config(page_title="Informe Guardia", layout="wide")

st.title("📊 Informe Guardia - Flujo Pacientes y Recursos")

uploaded_file = st.file_uploader("📂 Subí el archivo de datos", type=["csv", "xls", "xlsx", "ods"])

if uploaded_file is not None:
    with st.spinner("⏳ Cargando archivo..."):
        ext = uploaded_file.name.lower().split('.')[-1]
        if ext == 'csv':
            df_datos = pd.read_csv(uploaded_file, sep=';', decimal=',')
        elif ext in ['xls', 'xlsx']:
            df_datos = pd.read_excel(uploaded_file)
        elif ext == 'ods':
            df_datos = pd.read_excel(uploaded_file, engine='odf')
        else:
            st.error("❌ Formato no soportado.")
            st.stop()

    st.success("✅ Archivo cargado correctamente.")

    demora_tipo = st.radio("Tipo de Demora:", options=["Máxima", "Promedio"])

    flujo_options = df_datos["Flujo_Pacientes"].dropna().unique().tolist()
    flujo_selected = st.multiselect("Flujos Pacientes (obligatorio):", options=flujo_options)

    responsable_options = df_datos["Responsable"].dropna().unique().tolist()
    responsable_selected = st.multiselect("Responsable (opcional):", options=responsable_options)

    if st.button("🚀 Generar Informe"):
        with st.spinner("⏳ Generando informe..."):

            if not flujo_selected:
                st.warning("⚠️ Debe seleccionar al menos un flujo.")
                st.stop()

            df = df_datos[df_datos["Flujo_Pacientes"].isin(flujo_selected)].copy()

            if responsable_selected:
                df = df[df["Responsable"].isin(responsable_selected)]

            df["Fecha"] = pd.to_datetime(df["Fecha"], format="%d/%m/%y", errors='coerce').dt.strftime("%d/%m/%y")

            demora_agg = 'max' if demora_tipo == 'Máxima' else 'mean'

            df_max_por_flujo = df.groupby(["Fecha", "time_slot_ini", "Flujo_Pacientes"]).agg(
                demora_maxima_flujo=('Tiempo_espera__min', demora_agg)
            ).reset_index()

            df_max_final = df_max_por_flujo.groupby(["Fecha", "time_slot_ini"]).agg(
                demora_maxima=('demora_maxima_flujo', 'sum')
            ).reset_index()

            if len(flujo_selected) == 1:
                df_pacientes = df.groupby(["Fecha", "time_slot_ini"]).agg(
                    cantidad_pacientes=('Nro Paciente', 'count')
                ).reset_index()
            else:
                df_medico = df[df["Grupo"] == "Médico"]
                df_pacientes = df_medico.groupby(["Fecha", "time_slot_ini"]).agg(
                    cantidad_pacientes=('Nro Paciente', 'count')
                ).reset_index()

            df_recursos_real = df[df['Matricula'] != 0].groupby(
                ['Fecha', 'time_slot_ini', 'Grupo']
            ).agg(
                matriculas_distintas=('Matricula', pd.Series.nunique)
            ).reset_index()

            df_recursos_real["Grupo"] = df_recursos_real["Grupo"].replace({"Enfermería": "Triage"})

            df_recursos_pivot = df_recursos_real.pivot_table(
                index=['Fecha', 'time_slot_ini'],
                columns='Grupo',
                values='matriculas_distintas',
                fill_value=0
            ).reset_index()

            for col in ['Médico', 'Triage']:
                if col not in df_recursos_pivot.columns:
                    df_recursos_pivot[col] = 0

            df_final = df_max_final.merge(df_pacientes, on=['Fecha', 'time_slot_ini'], how='left')
            df_final = df_final.merge(df_recursos_pivot, on=['Fecha', 'time_slot_ini'], how='left')

            df_final['demora_maxima_fmt'] = df_final['demora_maxima'].apply(minutos_a_hhmmss)
            df_final['slot_sort'] = df_final['time_slot_ini'].apply(lambda x: int(x.split('-')[0].replace('[','').replace(']','')))
            df_final = df_final.sort_values(by=['slot_sort', 'Fecha'])

            # Crear orden de slots
            orden_slots = df_final[['time_slot_ini', 'slot_sort']].drop_duplicates().set_index('time_slot_ini').sort_values('slot_sort').index.tolist()

            df_pivot = df_final.pivot(index='time_slot_ini', columns='Fecha')[['demora_maxima_fmt', 'cantidad_pacientes', 'Médico', 'Triage']]

            # Aca va el bloque que te di:
            ordered_columns = []
            for fecha in sorted(df_final['Fecha'].unique()):
                for metric in ['demora_maxima_fmt', 'cantidad_pacientes', 'Médico', 'Triage']:
                    ordered_columns.append((metric, fecha))

            df_pivot = df_pivot[ordered_columns]

            
            df_pivot = df_pivot.reindex(orden_slots)

            # Mostrar tabla
            st.subheader(f"📋 Tabla de Informe - Demora {demora_tipo}")
            st.dataframe(df_pivot)

            # Mostrar gráficos
            st.subheader("📊 Gráficos")

            for metric in ['cantidad_pacientes', 'demora_maxima', 'Médico', 'Triage']:
                df_g = df_final.groupby(['Fecha', 'time_slot_ini'])[metric].max().unstack()
                df_g = df_g.T.reset_index()
                df_g['slot_sort'] = df_g['time_slot_ini'].apply(lambda x: int(x.split('-')[0].replace('[','').replace(']','')))
                df_g = df_g.sort_values(by='slot_sort').set_index('time_slot_ini')

                fig, ax = plt.subplots(figsize=(8, 2.5))
                df_g.drop(columns=['slot_sort']).plot(ax=ax, kind='bar')
                ax.set_title(f"{metric.replace('_', ' ').title()} por hora - Demora {demora_tipo}")
                ax.set_xlabel("Franja horaria")
                ax.set_ylabel(metric.replace('_', ' ').title())
                ax.legend(title="Fecha", bbox_to_anchor=(1.0, 1.0))

                st.pyplot(fig)

            # Exportar a Excel
            st.subheader("⬇️ Descargar Resultados")

            output_excel = io.BytesIO()
            df_pivot.to_excel(output_excel)
            output_excel.seek(0)

            st.download_button(
                label="📥 Descargar Excel",
                data=output_excel,
                file_name="informe_guardia.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            # Exportar a PDF
            output_pdf = io.BytesIO()
            with PdfPages(output_pdf) as pdf:
                fig, ax = plt.subplots(figsize=(16, 6))
                ax.axis('tight')
                ax.axis('off')
                table_data = df_pivot.reset_index().head(30)
                tabla = ax.table(cellText=table_data.values, colLabels=table_data.columns, loc='center', fontsize=8)
                pdf.savefig(fig)
                plt.close()

                for metric in ['cantidad_pacientes', 'demora_maxima', 'Médico', 'Triage']:
                    df_g = df_final.groupby(['Fecha', 'time_slot_ini'])[metric].max().unstack()
                    df_g = df_g.T.reset_index()
                    df_g['slot_sort'] = df_g['time_slot_ini'].apply(lambda x: int(x.split('-')[0].replace('[','').replace(']','')))
                    df_g = df_g.sort_values(by='slot_sort').set_index('time_slot_ini')

                    fig, ax = plt.subplots(figsize=(12, 4))
                    df_g.drop(columns=['slot_sort']).plot(ax=ax, kind='bar')
                    ax.set_title(f"{metric.replace('_', ' ').title()} por hora - Demora {demora_tipo}")
                    ax.set_xlabel("Franja horaria")
                    ax.set_ylabel(metric.replace('_', ' ').title())
                    ax.legend(title="Fecha", bbox_to_anchor=(1.0, 1.0))

                    pdf.savefig(fig)
                    plt.close()

            output_pdf.seek(0)

            st.download_button(
                label="📥 Descargar PDF",
                data=output_pdf,
                file_name="informe_guardia.pdf",
                mime="application/pdf"
            )

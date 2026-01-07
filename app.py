import streamlit as st
import pandas as pd
import numpy as np
from supabase import create_client, Client
from datetime import timedelta, date

# --- CONFIGURACIÓN E INICIO ---
st.set_page_config(page_title="Gestor de Trámites", layout="wide")

# Credenciales (En local las pones aquí, en la nube van en "Secrets")
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# --- FUNCIONES ---

def get_data(table):
    response = supabase.table(table).select("*").execute()
    return pd.DataFrame(response.data)

def calc_vencimiento(fecha_inicio):
    # Cálculo simple de 6 días hábiles usando numpy
    return np.busday_offset(fecha_inicio, 6, roll='forward').astype(date)

# --- INTERFAZ ---

st.title("📂 Control de Trámites y Seguimientos")

# Menú lateral
menu = st.sidebar.radio("Navegación", ["Mis Trámites", "Nuevo Trámite", "Configuración (Listas)"])

# ---------------- SECCIÓN: NUEVO TRÁMITE ----------------
if menu == "Nuevo Trámite":
    st.header("Registrar Nuevo Trámite")
    
    # Cargar catálogos
    df_paises = get_data("cat_paises")
    df_tipos = get_data("cat_tipos")
    df_estados = get_data("cat_estados")
    df_tramites = get_data("tramites") # Para seleccionar trámite padre
    
    with st.form("form_tramite"):
        col1, col2 = st.columns(2)
        asunto_p = col1.text_input("Asunto Principal")
        asunto_s = col2.text_input("Asunto Secundario")
        
        c1, c2, c3 = st.columns(3)
        fecha_rec = c1.date_input("Fecha Recibido", date.today())
        
        # Selectbox usando los ID y Nombres de la BD
        tipo = c2.selectbox("Tipo", df_tipos['nombre'].tolist())
        pais = c3.selectbox("País", df_paises['nombre'].tolist())
        
        estado = st.selectbox("Estado Inicial", df_estados['nombre'].tolist())
        obs = st.text_area("Observaciones")
        
        # Opción para subtarea
        es_subtarea = st.checkbox("¿Es una subtarea de otro trámite?")
        padre_id = None
        if es_subtarea and not df_tramites.empty:
            tramite_padre = st.selectbox("Selecciona el Trámite Padre", 
                                         df_tramites['id'].astype(str) + " - " + df_tramites['asunto_principal'])
            padre_id = int(tramite_padre.split(" - ")[0])

        submitted = st.form_submit_button("Guardar Trámite")
        
        if submitted:
            # Recuperar IDs basados en los nombres seleccionados
            tipo_id = int(df_tipos[df_tipos['nombre'] == tipo]['id'].values[0])
            pais_id = int(df_paises[df_paises['nombre'] == pais]['id'].values[0])
            estado_id = int(df_estados[df_estados['nombre'] == estado]['id'].values[0])
            
            # Calcular vencimiento
            fecha_venc = str(calc_vencimiento(fecha_rec))
            
            data = {
                "asunto_principal": asunto_p,
                "asunto_secundario": asunto_s,
                "fecha_recibido": str(fecha_rec),
                "fecha_vencimiento": fecha_venc,
                "tipo_id": tipo_id,
                "pais_id": pais_id,
                "estado_id": estado_id,
                "observaciones": obs,
                "tramite_padre_id": padre_id
            }
            
            supabase.table("tramites").insert(data).execute()
            st.success(f"Trámite guardado. Vence el: {fecha_venc}")

# ---------------- SECCIÓN: MIS TRÁMITES (BANDEJA) ----------------
elif menu == "Mis Trámites":
    st.header("Bandeja de Trámites")
    
    # Traemos datos haciendo un JOIN manual o vista (aquí simplificado)
    # Nota: En producción, usarías una View SQL para traer nombres en vez de IDs
    df = get_data("tramites")
    
    if not df.empty:
        st.dataframe(df[['id', 'asunto_principal', 'fecha_vencimiento', 'tramite_padre_id']])
        
        # Selector para ver detalles y seguimientos
        selected_id = st.selectbox("Selecciona ID para ver detalles y seguimientos", df['id'].unique())
        
        if selected_id:
            st.divider()
            st.subheader(f"Detalles del Trámite #{selected_id}")
            
            # --- SECCIÓN SEGUIMIENTOS ---
            st.markdown("#### 📝 Historial de Seguimientos")
            
            # Cargar seguimientos de este ID
            seg_data = supabase.table("seguimientos").select("*").eq("tramite_id", selected_id).execute()
            df_seg = pd.DataFrame(seg_data.data)
            
            if not df_seg.empty:
                for index, row in df_seg.iterrows():
                    st.info(f"📅 {row['fecha_seguimiento']}: {row['anotaciones']}")
            else:
                st.caption("No hay seguimientos registrados.")
            
            # Formulario rápido para agregar seguimiento
            with st.form("nuevo_seg"):
                col_s1, col_s2 = st.columns([1,3])
                f_seg = col_s1.date_input("Fecha")
                nota_seg = col_s2.text_input("Nueva anotación")
                btn_seg = st.form_submit_button("Agregar Seguimiento")
                
                if btn_seg:
                    supabase.table("seguimientos").insert({
                        "tramite_id": int(selected_id),
                        "fecha_seguimiento": str(f_seg),
                        "anotaciones": nota_seg
                    }).execute()
                    st.rerun()

# ---------------- SECCIÓN: CONFIGURACIÓN ----------------
elif menu == "Configuración (Listas)":
    st.header("Editar Catálogos")
    opcion = st.selectbox("¿Qué lista deseas editar?", ["Paises", "Tipos de Trámite", "Estados"])
    
    tabla_map = {"Paises": "cat_paises", "Tipos de Trámite": "cat_tipos", "Estados": "cat_estados"}
    tabla_actual = tabla_map[opcion]
    
    df_cat = get_data(tabla_actual)
    st.dataframe(df_cat)
    
    nuevo_item = st.text_input(f"Agregar nuevo a {opcion}")
    if st.button("Agregar"):
        supabase.table(tabla_actual).insert({"nombre": nuevo_item}).execute()
        st.success("Agregado")
        st.rerun()

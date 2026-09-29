import streamlit as st
import datetime
import calendar
import pandas as pd
import plotly.express as px

import os
from colorthief import ColorThief
from meeting_manager import (
    obtener_servicios_google, inicializar_hojas, obtener_datos, 
    agregar_sala, agregar_personal, agendar_reunion, cancelar_reunion,
    actualizar_participantes, obtener_usuarios, agregar_usuario, actualizar_usuario
)

# Detectar logo para usarlo como Favicon y en la UI
logo_icon = "📅"
logo_path = None
if os.path.exists("assets"):
    for f in os.listdir("assets"):
        if f.lower() in ["logo.png", "logo.jpg", "logo.jpeg"]:
            logo_path = os.path.join("assets", f)
            logo_icon = logo_path
            break

st.set_page_config(page_title="Nexus Sync - Gestión de Reuniones", page_icon=logo_icon, layout="wide")

# ==========================================
# LÓGICA DE MARCA BLANCA
# ==========================================
def rgb_to_hex(rgb):
    return '#{:02x}{:02x}{:02x}'.format(rgb[0], rgb[1], rgb[2])

@st.cache_data
def extraer_color_dominante(ruta_logo):
    try:
        color_thief = ColorThief(ruta_logo)
        # Bajar un poco la calidad de escaneo para que sea instantáneo
        dominante_rgb = color_thief.get_color(quality=5) 
        return rgb_to_hex(dominante_rgb)
    except Exception:
        return "#1e3a8a"

def aplicar_marca_blanca():
    global logo_path
    color_primario = "#1e3a8a" # Azul por defecto de Nexus Sync
    
    if logo_path:
        color_primario = extraer_color_dominante(logo_path)
            
    # Inyectar CSS Dinámico para teñir toda la aplicación
    css = f"""
    <style>
    /* Títulos y textos principales */
    h1, h2, h3, h4 {{ color: {color_primario} !important; }}
    
    /* Botones primarios */
    .stButton > button {{ 
        background-color: {color_primario} !important; 
        color: white !important; 
        border-color: {color_primario} !important;
    }}
    .stButton > button:hover {{
        background-color: white !important;
        color: {color_primario} !important;
        border-color: {color_primario} !important;
    }}
    
    /* Tabs (Pestañas) activas */
    div[data-baseweb="tab-list"] button[aria-selected="true"] {{
        color: {color_primario} !important;
        border-bottom-color: {color_primario} !important;
    }}
    
    /* Barra decorativa superior de Streamlit */
    #stDecoration {{
        background-image: linear-gradient(90deg, {color_primario}, {color_primario}) !important;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
    return logo_path, color_primario

def login():
    logo_path, color_primario = aplicar_marca_blanca()
    
    # Encabezado (Logo ajustado estéticamente)
    col_img1, col_img2, col_img3 = st.columns([2, 1, 2])
    with col_img2:
        if logo_path:
            st.image(logo_path, use_container_width=True)
        else:
            st.markdown(f"<h1 style='text-align: center; color: {color_primario};'>Nexus Sync</h1>", unsafe_allow_html=True)
    
    st.markdown("<h4 style='text-align: center; color: gray;'>Plataforma Inteligente de Gestión de Reuniones</h4>", unsafe_allow_html=True)
    st.write("---")
    
    # Formulario de login
    col_a, col_b, col_c = st.columns([1, 2, 1])
    with col_b:
        st.write("Por favor, inicia sesión para acceder al sistema administrativo.")
        usuario_input = st.text_input("Usuario")
        password_input = st.text_input("Contraseña", type="password")
        
        if st.button("Ingresar al Sistema", use_container_width=True):
            try:
                _, sh_service = obtener_servicios_google()
                usuarios_db = obtener_usuarios(sh_service)
                
                autenticado = False
                rol_asignado = ""
                
                for u in usuarios_db:
                    if u['usuario'] == usuario_input and u['password'] == password_input:
                        autenticado = True
                        rol_asignado = u['rol']
                        st.session_state['fila_usuario'] = u['fila_index']
                        break
                        
                if autenticado:
                    st.session_state['autenticado'] = True
                    st.session_state['usuario_actual'] = usuario_input
                    st.session_state['rol_actual'] = rol_asignado
                    st.session_state['password_actual'] = password_input
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos")
            except Exception as e:
                st.error(f"Error conectando a la base de datos: {e}")

def main_app():
    logo_path, color_primario = aplicar_marca_blanca()
    
    try:
        cal_service, sh_service = obtener_servicios_google()
        inicializar_hojas(sh_service)
    except Exception as e:
        st.error(f"Error conectando con Google: {e}")
        return

    # PANEL LATERAL
    if logo_path:
        st.sidebar.image(logo_path, use_container_width=True)
    st.sidebar.title("Panel Administrativo")
    st.sidebar.write(f"Conectado como: **{st.session_state['usuario_actual']}**")
    st.sidebar.write(f"Rol: **{st.session_state['rol_actual']}**")
    
    with st.sidebar.expander("🔑 Cambiar mi Contraseña"):
        with st.form("form_cambiar_pass", clear_on_submit=True):
            nueva_pass = st.text_input("Nueva contraseña", type="password")
            if st.form_submit_button("Actualizar contraseña"):
                if nueva_pass:
                    actualizar_usuario(sh_service, st.session_state['fila_usuario'], st.session_state['usuario_actual'], nueva_pass, st.session_state['rol_actual'])
                    st.session_state['password_actual'] = nueva_pass
                    st.success("Contraseña actualizada exitosamente.")
                else:
                    st.error("Ingresa una contraseña válida.")
                
    st.sidebar.write("---")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['autenticado'] = False
        st.rerun()
        
    st.title("📅 Gestor de Reuniones")

    # Cargar datos de Google Sheets
    salas_data = obtener_datos(sh_service, 'Salas!A2:A')
    lista_salas = [row[0] for row in salas_data if row]
    lista_salas.append("➕ Otra (Externa / Nueva)")

    personal_data = obtener_datos(sh_service, 'Personal!A2:D')
    opciones_personal = {}
    mapeo_personal = {} 
    
    for row in personal_data:
        if len(row) >= 2:
            nombre = row[0]
            correo = row[1].strip()
            sector = row[2] if len(row) >= 3 else "Sin Sector"
            estamento = row[3] if len(row) >= 4 else "Sin Estamento"
            
            etiqueta = f"{nombre} | {sector} ({correo})"
            opciones_personal[etiqueta] = correo
            mapeo_personal[correo] = {'sector': sector, 'estamento': estamento, 'nombre': nombre}

    # CONTROL DE ACCESOS SEGÚN ROL
    es_directivo = (st.session_state.get('rol_actual') == 'Directivo')
    
    nombres_tabs = ["📌 Agendar Reunión", "🗓 Mis Reuniones", "⚙️ Gestión de Personal y Salas"]
    if es_directivo:
        nombres_tabs.extend(["📅 Calendario", "📊 Dashboard", "🔐 Gestión de Usuarios"])

    tabs = st.tabs(nombres_tabs)

    # ----------------------------------------------------
    # TAB 1: AGENDAR
    # ----------------------------------------------------
    with tabs[0]:
        with st.form("form_agendar", clear_on_submit=True):
            st.write("Agendar una nueva reunión:")
            titulo = st.text_input("Título de la Reunión")
            sala_seleccionada = st.selectbox("Seleccionar Sala", lista_salas)
            
            sala_final = sala_seleccionada
            guardar_sala = False
            if sala_seleccionada == "➕ Otra (Externa / Nueva)":
                sala_final = st.text_input("Escribe el nombre de la sala o ubicación externa:")
                guardar_sala = st.checkbox("Guardar esta sala en el sistema para futuras reuniones")
            
            col1, col2 = st.columns(2)
            with col1:
                fecha = st.date_input("Fecha", min_value=datetime.date.today())
            with col2:
                hora_inicio = st.time_input("Hora de Inicio", value=datetime.time(10, 0))
                hora_fin = st.time_input("Hora de Fin", value=datetime.time(11, 0))
                
            participantes_sel = st.multiselect("Participantes (Personal Interno)", list(opciones_personal.keys()))
            correos_externos = st.text_input("Correos Externos (Opcional, separados por coma)")
            
            if st.form_submit_button("Agendar y Enviar Invitaciones"):
                if not titulo or not sala_final:
                    st.error("Título y Sala son obligatorios.")
                elif hora_fin <= hora_inicio:
                    st.error("La hora de fin debe ser posterior a la de inicio.")
                else:
                    inicio_dt = datetime.datetime.combine(fecha, hora_inicio)
                    fin_dt = datetime.datetime.combine(fecha, hora_fin)
                    
                    # ---------------------------------------------------------
                    # VALIDACIÓN DE CHOQUE DE HORARIOS EN LA MISMA SALA
                    # ---------------------------------------------------------
                    reuniones_existentes = obtener_datos(sh_service, 'Reuniones!A2:I')
                    choque = False
                    for r in reuniones_existentes:
                        if len(r) >= 8 and r[7] == 'Activa' and r[2] == sala_final:
                            try:
                                r_inicio = datetime.datetime.strptime(r[3].replace("T", " ")[:19], "%Y-%m-%d %H:%M:%S")
                                r_fin = datetime.datetime.strptime(r[4].replace("T", " ")[:19], "%Y-%m-%d %H:%M:%S")
                                # Fórmula de superposición de tiempos: (Start A < End B) and (End A > Start B)
                                if (inicio_dt < r_fin) and (fin_dt > r_inicio):
                                    choque = True
                                    break
                            except Exception:
                                pass
                                
                    if choque:
                        st.error(f"❌ ¡Choque de Horario! La sala '{sala_final}' ya tiene una reunión activa en ese bloque de tiempo. Cancela la anterior o elige otra sala/horario.")
                    else:
                        if guardar_sala and sala_final:
                            agregar_sala(sh_service, sala_final)
                        
                        emails = [opciones_personal[lbl] for lbl in participantes_sel]
                        if correos_externos:
                            emails.extend([x.strip() for x in correos_externos.split(",") if x.strip()])
                            
                        inicio_iso = inicio_dt.isoformat()
                        fin_iso = fin_dt.isoformat()
                        
                        try:
                            agendar_reunion(cal_service, sh_service, titulo, sala_final, inicio_iso, fin_iso, emails, st.session_state['usuario_actual'])
                            st.success("🎉 Reunión agendada exitosamente. El formulario se ha limpiado para la próxima reunión.")
                        except Exception as e:
                            st.error(f"Error: {e}")

    # ----------------------------------------------------
    # TAB 2: MIS REUNIONES (CON EDICIÓN DE PARTICIPANTES)
    # ----------------------------------------------------
    with tabs[1]:
        if st.button("🔄 Refrescar Lista"):
            st.rerun()
            
        reuniones_data = obtener_datos(sh_service, 'Reuniones!A1:I')
        hay_reuniones = False
        
        # Invertimos para ver primero las más nuevas en la lista
        for idx in range(len(reuniones_data)-1, 0, -1):
            fila = reuniones_data[idx]
            if len(fila) < 9: continue
            if fila[7] == 'Cancelada': continue
            hay_reuniones = True
            
            with st.expander(f"🔴 {fila[1]} - {fila[3][:10]}"):
                st.write(f"**Sala/Ubicación:** {fila[2]}")
                st.write(f"**Fecha y Hora:** {fila[3].replace('T', ' ')} a {fila[4].replace('T', ' ')}")
                st.write(f"**Agendado por:** {fila[6]}")
                
                correos_actuales = [c.strip() for c in fila[5].split(",") if c.strip()]
                etiquetas_actuales = []
                for lbl, c in opciones_personal.items():
                    if c in correos_actuales:
                        etiquetas_actuales.append(lbl)
                
                st.write("---")
                st.write("**Modificar Participantes**")
                
                nuevos_participantes = st.multiselect(
                    "Participantes Internos", 
                    list(opciones_personal.keys()), 
                    default=etiquetas_actuales,
                    key=f"edit_part_{idx}"
                )
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("Guardar Nuevos Participantes", key=f"upd_{idx}"):
                        nuevos_correos = [opciones_personal[lbl] for lbl in nuevos_participantes]
                        for c in correos_actuales:
                            if c not in mapeo_personal and c not in nuevos_correos:
                                nuevos_correos.append(c)
                        
                        actualizar_participantes(cal_service, sh_service, fila[8], idx, nuevos_correos)
                        st.success("Participantes actualizados.")
                        st.rerun()
                
                with col_btn2:
                    if st.button("Cancelar esta Reunión", key=f"del_{idx}", type="primary"):
                        cancelar_reunion(cal_service, sh_service, fila[8], idx)
                        st.success("Reunión cancelada y guardada en el registro.")
                        st.rerun()
                    
        if not hay_reuniones:
            st.info("No hay reuniones activas registradas en la base de datos.")

    # ----------------------------------------------------
    # TAB 3: GESTIÓN (AGREGAR PERSONAL)
    # ----------------------------------------------------
    with tabs[2]:
        st.subheader("Agregar Nuevo Personal al Sistema")
        
        # Extraer estamentos únicos existentes en la base de datos
        est_unicos = sorted(list(set([row[3] for row in personal_data if len(row) >= 4 and row[3].strip()])))
        if not est_unicos:
            est_unicos = ["Médico", "Enfermería", "TENS", "Administrativo", "Directivo"]
            
        with st.form("form_personal", clear_on_submit=True):
            n_nombre = st.text_input("Nombre Completo")
            n_correo = st.text_input("Correo Electrónico")
            n_sector = st.text_input("Sector / Departamento")
            
            col_est1, col_est2 = st.columns(2)
            with col_est1:
                n_estamento_sel = st.selectbox("Selecciona un Estamento Existente", est_unicos)
            with col_est2:
                n_estamento_nuevo = st.text_input("O escribe uno nuevo (reemplaza al anterior)")
            
            if st.form_submit_button("Guardar Empleado"):
                estamento_final = n_estamento_nuevo.strip() if n_estamento_nuevo.strip() else n_estamento_sel
                if n_nombre and n_correo:
                    agregar_personal(sh_service, n_nombre, n_correo, n_sector, estamento_final)
                    st.success("Personal agregado. Refresca la página para verlo en la lista.")
                else:
                    st.error("El nombre y correo son obligatorios.")

    # TABS EXCLUSIVOS PARA DIRECTIVOS
    if es_directivo:
        # ----------------------------------------------------
        # TAB 4: AGENDA INSTITUCIONAL (VISTA NATIVA GARANTIZADA)
        # ----------------------------------------------------
        with tabs[3]:
            st.header("📅 Agenda Institucional")
            st.write("Explora las reuniones históricas y futuras agrupadas por día.")
            
            reuniones_data = obtener_datos(sh_service, 'Reuniones!A2:I')
            
            eventos = []
            for fila in reuniones_data:
                if len(fila) >= 9 and fila[7] in ['Activa', 'Cancelada']:
                    try:
                        fecha_str = fila[3].replace("T", " ")[:19]
                        fin_str = fila[4].replace("T", " ")[:19]
                        dt_inicio = datetime.datetime.strptime(fecha_str, "%Y-%m-%d %H:%M:%S")
                        dt_fin = datetime.datetime.strptime(fin_str, "%Y-%m-%d %H:%M:%S")
                        
                        eventos.append({
                            "titulo": fila[1],
                            "sala": fila[2],
                            "inicio": dt_inicio,
                            "fin": dt_fin,
                            "participantes": fila[5],
                            "estado": fila[7]
                        })
                    except Exception:
                        pass
                        
            if not eventos:
                st.info("No hay reuniones programadas en el sistema.")
            else:
                col_m, col_y, _ = st.columns([1, 1, 2])
                meses_es = {1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio", 
                            7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"}
                
                now = datetime.datetime.now()
                anos_disponibles = sorted(list(set([e['inicio'].year for e in eventos])))
                if now.year not in anos_disponibles:
                    anos_disponibles.append(now.year)
                    anos_disponibles.sort()
                    
                with col_m:
                    mes_sel = st.selectbox("Filtrar por Mes", options=list(meses_es.keys()), format_func=lambda x: meses_es[x], index=now.month - 1)
                with col_y:
                    ano_sel = st.selectbox("Filtrar por Año", options=anos_disponibles, index=anos_disponibles.index(now.year))
                    
                st.write("---")
                eventos_filtrados = [e for e in eventos if e['inicio'].month == mes_sel and e['inicio'].year == ano_sel]
                eventos_filtrados.sort(key=lambda x: x['inicio'])
                
                if not eventos_filtrados:
                    st.warning(f"No hay reuniones registradas en {meses_es[mes_sel]} de {ano_sel}.")
                
                # --- RENDERIZADO DEL CALENDARIO HTML MATRIZ ---
                cal_matrix = calendar.monthcalendar(ano_sel, mes_sel)
                dias_semana = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
                
                html_cal = "<table style='width:100%; border-collapse: collapse; margin-top: 10px; font-family: sans-serif;'>"
                # Cabecera de días
                html_cal += "<tr>" + "".join([f"<th style='border: 1px solid #ddd; padding: 10px; text-align: center; background-color: {color_primario}; color: white; width: 14%;'>{d}</th>" for d in dias_semana]) + "</tr>"
                
                for semana in cal_matrix:
                    html_cal += "<tr>"
                    for dia in semana:
                        if dia == 0:
                            # Día vacío (pertenece al mes anterior/siguiente)
                            html_cal += "<td style='border: 1px solid #ddd; padding: 5px; height: 120px; background-color: #f9f9f9; opacity: 0.5;'></td>"
                        else:
                            # Filtrar eventos de este día exacto
                            eventos_dia = [e for e in eventos_filtrados if e['inicio'].day == dia]
                            html_eventos = ""
                            
                            for ev in eventos_dia:
                                if ev['estado'] == 'Activa':
                                    bg_color = color_primario
                                    txt_color = "white"
                                    tachado = ""
                                else:
                                    bg_color = "#ff4b4b" # Rojo cancelado
                                    txt_color = "white"
                                    tachado = "text-decoration: line-through; opacity: 0.7;"
                                    
                                html_eventos += f"""
                                <div style='background-color: {bg_color}; color: {txt_color}; border-radius: 4px; padding: 3px 5px; margin-top: 4px; font-size: 11px; {tachado} line-height: 1.2;'>
                                    <b>{ev['inicio'].strftime('%H:%M')}</b> - {ev['titulo']}<br>
                                    <span style='font-size: 9px;'>📍 {ev['sala']}</span>
                                </div>
                                """
                                
                            # Si es hoy, resaltar el número
                            es_hoy = (dia == now.day and mes_sel == now.month and ano_sel == now.year)
                            estilo_num = f"background-color: {color_primario}; color: white; border-radius: 50%; padding: 2px 6px; display: inline-block;" if es_hoy else "color: gray; font-weight: bold;"
                            
                            html_cal += f"<td style='border: 1px solid #ddd; padding: 5px; vertical-align: top; height: 120px;'>"
                            html_cal += f"<div style='text-align: right; margin-bottom: 5px;'><span style='{estilo_num}'>{dia}</span></div>"
                            html_cal += f"{html_eventos}</td>"
                            
                    html_cal += "</tr>"
                    
                html_cal += "</table>"
                
                # Inyectar el calendario HTML interactivo en Streamlit
                st.markdown(html_cal, unsafe_allow_html=True)

        # ----------------------------------------------------
        # TAB 5: DASHBOARD (SECTORES, ESTAMENTO, CARGA)
        # ----------------------------------------------------
        with tabs[4]:
            st.header("📊 Dashboard de Carga de Reuniones")
            
            reuniones_data = obtener_datos(sh_service, 'Reuniones!A2:I')
            data_graficos = []
            for fila in reuniones_data:
                if len(fila) < 9 or fila[7] == 'Cancelada': continue
                inicio = datetime.datetime.fromisoformat(fila[3])
                semana = inicio.strftime("%Y-W%W")
                correos_participantes = [c.strip() for c in fila[5].split(",") if c.strip()]
                for c in correos_participantes:
                    if c in mapeo_personal:
                        data_graficos.append({
                            "Semana": semana,
                            "Sector": mapeo_personal[c]['sector'],
                            "Estamento": mapeo_personal[c]['estamento'],
                            "Reuniones": 1
                        })
            
            if data_graficos:
                df = pd.DataFrame(data_graficos)
                st.markdown("### 🔍 Filtros de Análisis")
                col_filt1, col_filt2 = st.columns(2)
                
                sectores_unicos = sorted(df['Sector'].unique())
                estamentos_unicos = sorted(df['Estamento'].unique())
                
                with col_filt1:
                    sel_sectores = st.multiselect("Filtrar por Sector", sectores_unicos, default=sectores_unicos)
                with col_filt2:
                    sel_estamentos = st.multiselect("Filtrar por Estamento", estamentos_unicos, default=estamentos_unicos)
                
                df_filtrado = df[df['Sector'].isin(sel_sectores) & df['Estamento'].isin(sel_estamentos)]
                st.write("---")
                
                if not df_filtrado.empty:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.subheader("Carga por Sector")
                        df_sector = df_filtrado.groupby('Sector')['Reuniones'].sum().reset_index()
                        fig_sec = px.bar(df_sector, x='Sector', y='Reuniones', color='Sector', text='Reuniones', title="Reuniones por Sector")
                        st.plotly_chart(fig_sec, use_container_width=True)
                        
                    with col2:
                        st.subheader("Carga por Estamento")
                        df_est = df_filtrado.groupby('Estamento')['Reuniones'].sum().reset_index()
                        fig_est = px.bar(df_est, x='Reuniones', y='Estamento', color='Estamento', text='Reuniones', orientation='h', title="Reuniones por Estamento")
                        fig_est.update_layout(yaxis={'categoryorder': 'total ascending'})
                        st.plotly_chart(fig_est, use_container_width=True)
                        
                    st.subheader("Carga Semanal Histórica")
                    df_sem = df_filtrado.groupby('Semana')['Reuniones'].sum().reset_index().sort_values('Semana')
                    fig_sem = px.area(df_sem, x='Semana', y='Reuniones', markers=True, title="Evolución de Carga Semanal")
                    st.plotly_chart(fig_sem, use_container_width=True)
                else:
                    st.warning("No hay datos que coincidan con los filtros seleccionados.")
            else:
                st.info("No hay suficientes datos de participantes internos para mostrar métricas.")

        # ----------------------------------------------------
        # TAB 6: GESTIÓN DE USUARIOS
        # ----------------------------------------------------
        with tabs[5]:
            st.header("🔐 Gestión de Usuarios y Roles")
            st.write("Administra quién puede acceder al sistema.")
            
            usuarios_db = obtener_usuarios(sh_service)
            
            with st.form("form_nuevo_usuario", clear_on_submit=True):
                st.subheader("Crear Nuevo Perfil")
                c1, c2, c3 = st.columns(3)
                with c1:
                    nu_usuario = st.text_input("Nombre de Usuario")
                with c2:
                    nu_pass = st.text_input("Contraseña")
                with c3:
                    nu_rol = st.selectbox("Rol", ["Administrativo", "Directivo"])
                    
                if st.form_submit_button("Crear Usuario"):
                    if nu_usuario and nu_pass:
                        agregar_usuario(sh_service, nu_usuario, nu_pass, nu_rol)
                        st.success(f"Usuario {nu_usuario} creado exitosamente.")
                        st.rerun()
                    else:
                        st.error("Completa usuario y contraseña.")
                        
            st.write("---")
            st.subheader("Perfiles Existentes")
            for u in usuarios_db:
                with st.expander(f"👤 {u['usuario']} ({u['rol']})"):
                    col_u1, col_u2, col_u3 = st.columns(3)
                    with col_u1:
                        edit_rol = st.selectbox("Cambiar Rol", ["Administrativo", "Directivo"], index=0 if u['rol']=="Administrativo" else 1, key=f"rol_{u['fila_index']}")
                    with col_u2:
                        edit_pass = st.text_input("Nueva Contraseña (Opcional)", type="password", key=f"pass_{u['fila_index']}")
                    with col_u3:
                        st.write("")
                        st.write("")
                        if st.button("Guardar Cambios", key=f"save_{u['fila_index']}"):
                            pass_final = edit_pass if edit_pass else u['password']
                            actualizar_usuario(sh_service, u['fila_index'], u['usuario'], pass_final, edit_rol)
                            st.success("Perfil actualizado correctamente.")
                            st.rerun()

if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

if st.session_state['autenticado']:
    main_app()
else:
    login()

# ==========================================
# PIE DE PÁGINA (FIRMA)
# ==========================================
st.markdown(
    """
    <hr style="margin-top: 50px;">
    <div style="text-align: center; color: gray; padding: 10px;">
        <p style="margin: 0; font-size: 14px;">Un producto de <strong>Nexus Soluciones</strong></p>
        <p style="margin: 0; font-size: 12px;">Desarrollado y dirigido por <strong>Víctor Fernández Ruiz</strong> | Innovación en Salud</p>
    </div>
    """, 
    unsafe_allow_html=True
)

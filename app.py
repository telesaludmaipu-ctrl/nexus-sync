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
    actualizar_participantes, obtener_usuarios, agregar_usuario, actualizar_usuario,
    obtener_configuracion, guardar_configuracion, marcar_reunion_realizada,
    autorizar_reunion, rechazar_reunion
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

st.set_page_config(page_title="CESFAM Maipú - Gestión de Reuniones", page_icon=logo_icon, layout="wide")

# ==========================================
# LÓGICA DE MARCA BLANCA
# ==========================================
def rgb_to_hex(rgb):
    return '#{:02x}{:02x}{:02x}'.format(rgb[0], rgb[1], rgb[2])

def parsear_fecha_segura(valor):
    if not valor:
        return None
    val = str(valor).replace("T", " ").strip()
    partes = val.split(" ")
    if len(partes) == 2:
        d, t = partes
        t_nums = t.split(":")
        if len(t_nums) >= 2:
            hh = t_nums[0].zfill(2)
            mm = t_nums[1].zfill(2)
            ss = t_nums[2].zfill(2) if len(t_nums) > 2 else "00"
            val = f"{d} {hh}:{mm}:{ss}"
    try:
        return datetime.datetime.strptime(val[:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        try:
            return datetime.datetime.fromisoformat(str(valor))
        except Exception:
            return None

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
    
    /* Panel lateral más angosto */
    [data-testid="stSidebar"] {{
        min-width: 250px !important;
        max-width: 260px !important;
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
            st.markdown(f"<h1 style='text-align: center; color: {color_primario};'>CESFAM Maipú</h1>", unsafe_allow_html=True)
    
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
    st.sidebar.caption("⚡ Motor v2.0 (Service Account)")
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
        nombres_tabs.extend(["📅 Calendario", "📊 Dashboard", "🛡️ Autorizaciones", "🔐 Gestión de Usuarios"])

    tabs = st.tabs(nombres_tabs)

    # ----------------------------------------------------
    # TAB 1: AGENDAR
    # ----------------------------------------------------
    with tabs[0]:
        if es_directivo:
            st.info("👑 **Modo Directivo:** Tu reunión se creará y convocará de inmediato en el calendario institucional y a los participantes.")
        else:
            st.info("ℹ️ **Modo Funcionario / Encargado:** Tu reunión quedará registrada como **Pendiente** y se enviará un aviso por correo a la Dirección para su debida autorización.")
            
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
            
            submit_label = "Agendar y Convocar Reunión" if es_directivo else "Enviar Solicitud a Autorización Directiva"
            if st.form_submit_button(submit_label):
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
                        if len(r) >= 8 and r[7] in ['Activa', 'Pendiente'] and r[2] == sala_final:
                            r_inicio = parsear_fecha_segura(r[3])
                            r_fin = parsear_fecha_segura(r[4])
                            if r_inicio and r_fin:
                                if (inicio_dt < r_fin) and (fin_dt > r_inicio):
                                    choque = True
                                    break
                                
                    if choque:
                        st.error(f"❌ ¡Choque de Horario! La sala '{sala_final}' ya tiene una reunión activa o pendiente en ese bloque de tiempo. Cancela la anterior o elige otra sala/horario.")
                    else:
                        if guardar_sala and sala_final:
                            agregar_sala(sh_service, sala_final)
                        
                        emails = [opciones_personal[lbl] for lbl in participantes_sel]
                        if correos_externos:
                            emails.extend([x.strip() for x in correos_externos.split(",") if x.strip()])
                            
                        inicio_iso = inicio_dt.isoformat()
                        fin_iso = fin_dt.isoformat()
                        
                        requiere_autorizacion = (not es_directivo)
                        try:
                            ok_mail, msg_mail = agendar_reunion(
                                cal_service, sh_service, titulo, sala_final, 
                                inicio_iso, fin_iso, emails, 
                                st.session_state['usuario_actual'], 
                                requiere_autorizacion=requiere_autorizacion
                            )
                            if requiere_autorizacion:
                                st.success("📋 Solicitud enviada exitosamente. Quedó registrada como PENDIENTE de autorización por la Dirección y se notificó al Director por correo.")
                            else:
                                if ok_mail:
                                    st.success("🎉 Reunión agendada exitosamente e invitaciones enviadas a los correos.")
                                else:
                                    st.warning(f"⚠️ Reunión registrada en calendario y planilla, pero hubo un detalle con el correo: {msg_mail}")
                        except Exception as e:
                            st.error(f"Error: {e}")

    # ----------------------------------------------------
    # TAB 2: MIS REUNIONES (CON CONTROL DE ESTADOS Y BLOQUEO)
    # ----------------------------------------------------
    with tabs[1]:
        if st.button("🔄 Refrescar Lista"):
            st.rerun()
            
        reuniones_data = obtener_datos(sh_service, 'Reuniones!A1:I')
        hay_reuniones = False
        ahora = datetime.datetime.now()
        
        # Invertimos para ver primero las más nuevas en la lista
        for idx in range(len(reuniones_data)-1, 0, -1):
            fila = reuniones_data[idx]
            if len(fila) < 9: continue
            estado_reunion = fila[7]
            if estado_reunion == 'Cancelada': continue
            hay_reuniones = True
            
            dt_inicio = parsear_fecha_segura(fila[3])
            dt_fin = parsear_fecha_segura(fila[4])
            
            es_pasada = bool(dt_fin and dt_fin < ahora) or (estado_reunion == 'Realizada')
            
            # Asignar badge representativo
            if estado_reunion == 'Pendiente':
                badge_estado = "🟡 [PENDIENTE DE AUTORIZACIÓN]"
            elif estado_reunion == 'Realizada':
                badge_estado = "✅ [REALIZADA]"
            elif estado_reunion == 'Rechazada':
                badge_estado = "❌ [RECHAZADA]"
            elif es_pasada:
                badge_estado = "⏳ [FINALIZADA]"
            else:
                badge_estado = "🔵 [ACTIVA]"
            
            with st.expander(f"{badge_estado} {fila[1]} - {fila[3][:10]}"):
                c_inf1, c_inf2 = st.columns(2)
                with c_inf1:
                    st.write(f"**Sala/Ubicación:** {fila[2]}")
                    st.write(f"**Fecha y Hora:** {fila[3].replace('T', ' ')} a {fila[4].replace('T', ' ')}")
                with c_inf2:
                    st.write(f"**Agendado por:** {fila[6]}")
                    st.write(f"**Estado Actual:** **{estado_reunion}**")
                
                # Botón para marcar como Realizada (reuniones activas)
                if estado_reunion == 'Activa':
                    if st.button("✅ Marcar como Realizada", key=f"done_{idx}"):
                        marcar_reunion_realizada(sh_service, idx)
                        st.success("Reunión marcada como Realizada.")
                        st.rerun()

                st.write("---")
                
                # BLOQUEO SI ES PASADA O YA REALIZADA/RECHAZADA
                if es_pasada or estado_reunion in ['Realizada', 'Rechazada']:
                    st.info("🔒 Esta reunión ya se realizó o finalizó su horario. Las opciones de edición de participantes y cancelación se encuentran bloqueadas por seguridad del registro histórico.")
                elif estado_reunion == 'Pendiente':
                    st.warning("⏳ Esta reunión está a la espera de ser autorizada por la Dirección. No se han enviado convocatorias oficiales.")
                    if st.button("❌ Desistir / Cancelar Solicitud", key=f"del_pend_{idx}", type="primary"):
                        cancelar_reunion(cal_service, sh_service, fila[8], idx)
                        st.success("Solicitud retirada del sistema.")
                        st.rerun()
                else:
                    # REUNIÓN ACTIVA Y FUTURA: Permitir edición de participantes y cancelación
                    st.write("**Modificar Participantes**")
                    correos_actuales = [c.strip() for c in fila[5].split(",") if c.strip()]
                    etiquetas_actuales = []
                    for lbl, c in opciones_personal.items():
                        if c in correos_actuales:
                            etiquetas_actuales.append(lbl)
                    
                    nuevos_participantes = st.multiselect(
                        "Participantes Internos", 
                        list(opciones_personal.keys()), 
                        default=etiquetas_actuales,
                        key=f"edit_part_{idx}"
                    )
                    
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        if st.button("💾 Guardar Nuevos Participantes", key=f"upd_{idx}"):
                            nuevos_correos = [opciones_personal[lbl] for lbl in nuevos_participantes]
                            for c in correos_actuales:
                                if c not in mapeo_personal and c not in nuevos_correos:
                                    nuevos_correos.append(c)
                            
                            actualizar_participantes(cal_service, sh_service, fila[8], idx, nuevos_correos)
                            st.success("Participantes actualizados.")
                            st.rerun()
                    
                    with col_btn2:
                        if st.button("🚨 Cancelar esta Reunión", key=f"del_{idx}", type="primary"):
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
                if len(fila) >= 9 and fila[7] in ['Activa', 'Realizada', 'Cancelada']:
                    dt_inicio = parsear_fecha_segura(fila[3])
                    dt_fin = parsear_fecha_segura(fila[4])
                    if dt_inicio and dt_fin:
                        eventos.append({
                            "titulo": fila[1],
                            "sala": fila[2],
                            "inicio": dt_inicio,
                            "fin": dt_fin,
                            "participantes": fila[5],
                            "estado": fila[7]
                        })
                        
            if not eventos:
                st.info("No hay reuniones programadas en el sistema.")
            else:
                now = datetime.datetime.now()
                
                # Inicializar estado del calendario en session_state para sincronización con flechas
                if 'cal_mes' not in st.session_state:
                    st.session_state['cal_mes'] = now.month
                if 'cal_ano' not in st.session_state:
                    st.session_state['cal_ano'] = now.year

                # Buscar la próxima reunión activa futura para el contador regresivo
                reuniones_futuras = [e for e in eventos if e['estado'] == 'Activa' and e['inicio'] > now]
                reuniones_futuras.sort(key=lambda x: x['inicio'])
                proxima_reunion = reuniones_futuras[0] if reuniones_futuras else None

                col_m, col_y, col_count = st.columns([1, 1, 2])
                meses_es = {1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio", 
                            7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"}
                
                anos_disponibles = sorted(list(set([e['inicio'].year for e in eventos] + [now.year, now.year + 1, now.year - 1])))
                if st.session_state['cal_ano'] not in anos_disponibles:
                    anos_disponibles.append(st.session_state['cal_ano'])
                    anos_disponibles.sort()
                    
                with col_m:
                    def actualizar_mes():
                        st.session_state['cal_mes'] = st.session_state['sel_box_mes']

                    mes_sel = st.selectbox(
                        "Filtrar por Mes", 
                        options=list(meses_es.keys()), 
                        format_func=lambda x: meses_es[x], 
                        index=st.session_state['cal_mes'] - 1,
                        key="sel_box_mes",
                        on_change=actualizar_mes
                    )
                with col_y:
                    def actualizar_ano():
                        st.session_state['cal_ano'] = st.session_state['sel_box_ano']

                    ano_sel = st.selectbox(
                        "Filtrar por Año", 
                        options=anos_disponibles, 
                        index=anos_disponibles.index(st.session_state['cal_ano']),
                        key="sel_box_ano",
                        on_change=actualizar_ano
                    )
                    
                with col_count:
                    if proxima_reunion:
                        delta = proxima_reunion['inicio'] - now
                        dias = delta.days
                        horas = delta.seconds // 3600
                        mins = (delta.seconds % 3600) // 60
                        
                        st.markdown(f"""
                        <div style="background: linear-gradient(135deg, {color_primario} 0%, #0f172a 100%); color: white; padding: 10px 14px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; opacity: 0.85;">⏳ Próxima Reunión (Cuenta Regresiva)</div>
                            <div style="font-size: 18px; font-weight: bold; margin: 2px 0;">{dias}d {horas}h {mins}m restantes</div>
                            <div style="font-size: 12px; opacity: 0.9; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">📌 {proxima_reunion['titulo']} &nbsp;|&nbsp; 📍 {proxima_reunion['sala']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown("""
                        <div style="background-color: #f1f5f9; color: #475569; padding: 12px 14px; border-radius: 8px; border: 1px solid #e2e8f0;">
                            <div style="font-size: 11px; text-transform: uppercase;">⏳ Próxima Reunión</div>
                            <div style="font-size: 15px; font-weight: bold; color: #10b981;">✅ Sin reuniones pendientes a futuro</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                st.write("---")

                # --- CONTROL DE NAVEGACIÓN CON FLECHAS Y TÍTULO SOBRE LA MATRIZ ---
                def paso_mes(delta):
                    m = st.session_state['cal_mes'] + delta
                    a = st.session_state['cal_ano']
                    if m < 1:
                        st.session_state['cal_mes'] = 12
                        st.session_state['cal_ano'] = a - 1
                    elif m > 12:
                        st.session_state['cal_mes'] = 1
                        st.session_state['cal_ano'] = a + 1
                    else:
                        st.session_state['cal_mes'] = m

                col_arr_izq, col_arr_tit, col_arr_der = st.columns([1, 4, 1])
                with col_arr_izq:
                    if st.button("◀ Mes Anterior", key="btn_prev_mes", use_container_width=True):
                        paso_mes(-1)
                        st.rerun()
                with col_arr_tit:
                    st.markdown(f"<h3 style='text-align: center; margin: 0; color: {color_primario};'>🗓️ {meses_es[st.session_state['cal_mes']]} de {st.session_state['cal_ano']}</h3>", unsafe_allow_html=True)
                with col_arr_der:
                    if st.button("Mes Siguiente ▶", key="btn_next_mes", use_container_width=True):
                        paso_mes(1)
                        st.rerun()

                mes_actual = st.session_state['cal_mes']
                ano_actual = st.session_state['cal_ano']

                eventos_filtrados = [e for e in eventos if e['inicio'].month == mes_actual and e['inicio'].year == ano_actual]
                eventos_filtrados.sort(key=lambda x: x['inicio'])
                
                if not eventos_filtrados:
                    st.warning(f"No hay reuniones registradas en {meses_es[mes_actual]} de {ano_actual}.")
                
                # --- RENDERIZADO DEL CALENDARIO HTML MATRIZ ---
                cal_matrix = calendar.monthcalendar(ano_actual, mes_actual)
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
                                elif ev['estado'] == 'Realizada':
                                    bg_color = "#10b981" # Verde completada
                                    txt_color = "white"
                                    tachado = ""
                                else:
                                    bg_color = "#ff4b4b" # Rojo cancelado
                                    txt_color = "white"
                                    tachado = "text-decoration: line-through; opacity: 0.7;"
                                    
                                html_eventos += f"<div style='background-color: {bg_color}; color: {txt_color}; border-radius: 4px; padding: 3px 5px; margin-top: 4px; font-size: 11px; {tachado} line-height: 1.2;'><b>{ev['inicio'].strftime('%H:%M')}</b> - {ev['titulo']}<br><span style='font-size: 9px;'>📍 {ev['sala']} ({ev['estado']})</span></div>"
                                
                            # Si es hoy, resaltar el número
                            es_hoy = (dia == now.day and mes_actual == now.month and ano_actual == now.year)
                            estilo_num = f"background-color: {color_primario}; color: white; border-radius: 50%; padding: 2px 6px; display: inline-block;" if es_hoy else "color: gray; font-weight: bold;"
                            
                            html_cal += f"<td style='border: 1px solid #ddd; padding: 5px; vertical-align: top; height: 120px;'>"
                            html_cal += f"<div style='text-align: right; margin-bottom: 5px;'><span style='{estilo_num}'>{dia}</span></div>"
                            html_cal += f"{html_eventos}</td>"
                            
                    html_cal += "</tr>"
                    
                html_cal += "</table>"
                
                # Limpiar cualquier salto de línea extra que rompa el markdown
                html_cal = html_cal.replace("\\n", "")
                
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
                inicio = parsear_fecha_segura(fila[3])
                if not inicio: continue
                semana = inicio.strftime("%Y-W%W")
                correos_participantes = [c.strip() for c in fila[5].split(",") if c.strip()]
                for c in correos_participantes:
                    if c in mapeo_personal:
                        data_graficos.append({
                            "Fecha": inicio.date(),
                            "Semana": semana,
                            "Sector": mapeo_personal[c]['sector'],
                            "Estamento": mapeo_personal[c]['estamento'],
                            "Reuniones": 1
                        })
            
            if data_graficos:
                df = pd.DataFrame(data_graficos)
                st.markdown("### 🔍 Filtros de Análisis")
                
                min_fecha = df['Fecha'].min()
                max_fecha = df['Fecha'].max()
                
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    f_desde = st.date_input("🗓️ Fecha Desde (Inicio de rango)", value=min_fecha)
                with col_f2:
                    f_hasta = st.date_input("🗓️ Fecha Hasta (Fin de rango)", value=max_fecha)
                
                col_filt1, col_filt2 = st.columns(2)
                sectores_unicos = sorted(df['Sector'].unique())
                estamentos_unicos = sorted(df['Estamento'].unique())
                
                with col_filt1:
                    sel_sectores = st.multiselect("Filtrar por Sector", sectores_unicos, default=sectores_unicos)
                with col_filt2:
                    sel_estamentos = st.multiselect("Filtrar por Estamento", estamentos_unicos, default=estamentos_unicos)
                
                df_filtrado = df[
                    (df['Fecha'] >= f_desde) & 
                    (df['Fecha'] <= f_hasta) & 
                    (df['Sector'].isin(sel_sectores)) & 
                    (df['Estamento'].isin(sel_estamentos))
                ]
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
        # TAB 6: AUTORIZACIONES (CONTROL DIRECTIVO)
        # ----------------------------------------------------
        with tabs[5]:
            st.header("🛡️ Control y Autorización de Reuniones")
            st.write("Módulo de control de gestión. Revisa y autoriza las solicitudes de reunión generadas por los encargados de programa y funcionarios antes de ser publicadas en el calendario oficial y notificadas a los equipos.")
            
            # --- ASIGNACIÓN DE DIRECTOR AUTORIZADOR ---
            st.subheader("👤 Funcionario Autorizador Asignado")
            email_director_actual = obtener_configuracion(sh_service, 'director_autorizador', 'telesaludmaipu@gmail.com')
            
            col_aut1, col_aut2 = st.columns([3, 1])
            with col_aut1:
                opciones_directores = {}
                idx_defecto = 0
                for idx_p, (lbl, mail) in enumerate(opciones_personal.items()):
                    opciones_directores[lbl] = mail
                    if mail == email_director_actual:
                        idx_defecto = idx_p
                
                if not opciones_directores:
                    opciones_directores = {"telesaludmaipu@gmail.com": "telesaludmaipu@gmail.com"}
                
                director_sel_label = st.selectbox(
                    "Selecciona el Directivo responsable de autorizar (recibirá los correos de alerta cuando se cree una reunión):",
                    options=list(opciones_directores.keys()),
                    index=idx_defecto if idx_defecto < len(opciones_directores) else 0
                )
                correo_director_sel = opciones_directores.get(director_sel_label, email_director_actual)
            
            with col_aut2:
                st.write("")
                st.write("")
                if st.button("💾 Asignar Autorizador", use_container_width=True):
                    guardar_configuracion(sh_service, 'director_autorizador', correo_director_sel)
                    st.success(f"Director autorizador actualizado: {correo_director_sel}")
                    st.rerun()
                    
            st.caption(f"📧 Correo actualmente configurado para recibir alertas de autorización: **{email_director_actual}**")
            st.write("---")
            
            # --- BANDEJA DE SOLICITUDES PENDIENTES ---
            st.subheader("📥 Solicitudes Pendientes de Aprobación")
            
            reuniones_todas = obtener_datos(sh_service, 'Reuniones!A1:I')
            solicitudes_pendientes = []
            for idx, fila in enumerate(reuniones_todas):
                if idx == 0: continue
                if len(fila) >= 8 and fila[7] == 'Pendiente':
                    solicitudes_pendientes.append((idx, fila))
                    
            if not solicitudes_pendientes:
                st.success("✅ No hay solicitudes pendientes de autorización en este momento. Todas las reuniones están al día.")
            else:
                st.info(f"Tienes **{len(solicitudes_pendientes)}** solicitud(es) esperando tu revisión.")
                
                for idx, fila in solicitudes_pendientes:
                    titulo_sol = fila[1] if len(fila) > 1 else "Sin Título"
                    sala_sol = fila[2] if len(fila) > 2 else "Sin Sala"
                    inicio_sol = fila[3] if len(fila) > 3 else ""
                    fin_sol = fila[4] if len(fila) > 4 else ""
                    part_sol = fila[5] if len(fila) > 5 else ""
                    creador_sol = fila[6] if len(fila) > 6 else ""
                    
                    with st.expander(f"⏳ Solicitud: {titulo_sol} | Convocado por: {creador_sol}", expanded=True):
                        c_det1, c_det2 = st.columns(2)
                        with c_det1:
                            st.write(f"**📌 Título:** {titulo_sol}")
                            st.write(f"**📍 Sala / Ubicación:** {sala_sol}")
                            st.write(f"**🗓️ Horario:** {inicio_sol.replace('T', ' ')} a {fin_sol.replace('T', ' ')}")
                        with c_det2:
                            st.write(f"**👤 Solicitado por:** {creador_sol}")
                            st.write(f"**👥 Participantes:** {part_sol}")
                            
                        correos_participantes = [c.strip() for c in part_sol.split(",") if c.strip()]
                        
                        col_acc1, col_acc2 = st.columns(2)
                        with col_acc1:
                            if st.button("✅ Autorizar y Enviar a Todo el Equipo", key=f"btn_aut_{idx}", type="primary", use_container_width=True):
                                with st.spinner("Creando evento en Google Calendar y despachando invitaciones por correo..."):
                                    ok_aut, msg_aut = autorizar_reunion(
                                        cal_service, sh_service, idx, titulo_sol, sala_sol,
                                        inicio_sol, fin_sol, correos_participantes, creador_sol
                                    )
                                    if ok_aut:
                                        st.success(f"🎉 ¡Reunión autorizada con éxito! {msg_aut}")
                                        st.rerun()
                                    else:
                                        st.error(f"Error autorizando reunión: {msg_aut}")
                        with col_acc2:
                            if st.button("❌ Rechazar Solicitud", key=f"btn_rech_{idx}", use_container_width=True):
                                ok_rech, msg_rech = rechazar_reunion(sh_service, idx, titulo_sol, creador_sol)
                                st.warning("La solicitud ha sido rechazada.")
                                st.rerun()

        # ----------------------------------------------------
        # TAB 7: GESTIÓN DE USUARIOS
        # ----------------------------------------------------
        with tabs[6]:
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

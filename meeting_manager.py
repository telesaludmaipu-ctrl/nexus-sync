import os
import datetime
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import glob
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import streamlit as st

SCOPES = [
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/spreadsheets'
]

SPREADSHEET_ID = '1zfhpffSAT4DRiDWx34SVvsF8FQbKNR-DTm9DKJs6PK4'
CALENDAR_ID = 'telesaludmaipu@gmail.com'
SMTP_USER_DEFAULT = ''
SMTP_PASS_DEFAULT = ''

def obtener_servicios_google():
    creds = None
    base_dir = os.path.dirname(os.path.abspath(__file__))
    token_path = os.path.join(base_dir, 'token.json')
    credentials_path = os.path.join(base_dir, 'credentials.json')
    
    # 1. Prioridad: Buscar archivo JSON de Cuenta de Servicio (Service Account)
    sa_files = glob.glob(os.path.join(base_dir, "sistema-de-reuniones-*.json")) + glob.glob(os.path.join(base_dir, "*service_account*.json"))
    if sa_files and os.path.exists(sa_files[0]):
        creds = service_account.Credentials.from_service_account_file(sa_files[0], scopes=SCOPES)
        calendar_service = build('calendar', 'v3', credentials=creds)
        sheets_service = build('sheets', 'v4', credentials=creds)
        return calendar_service, sheets_service

    # 2. Buscar Cuenta de Servicio en Secrets de Streamlit Cloud
    try:
        if 'gcp_service_account' in st.secrets:
            sa_info = dict(st.secrets['gcp_service_account'])
            creds = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)
            calendar_service = build('calendar', 'v3', credentials=creds)
            sheets_service = build('sheets', 'v4', credentials=creds)
            return calendar_service, sheets_service
    except Exception:
        pass

    # 3. Fallback: OAuth tradicional (token.json o google_token en secrets)
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    else:
        try:
            if 'google_token' in st.secrets:
                token_info = dict(st.secrets['google_token'])
                creds = Credentials.from_authorized_user_info(token_info, SCOPES)
        except Exception:
            pass

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                raise FileNotFoundError("Falta archivo de credenciales y no hay st.secrets configurados.")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
            
        en_nube = False
        try:
            if 'google_token' in st.secrets or 'gcp_service_account' in st.secrets:
                en_nube = True
        except Exception:
            pass
            
        if not en_nube:
            with open(token_path, 'w') as token:
                token.write(creds.to_json())

    calendar_service = build('calendar', 'v3', credentials=creds)
    sheets_service = build('sheets', 'v4', credentials=creds)
    return calendar_service, sheets_service

def inicializar_hojas(sheets_service):
    """Crea las pestañas necesarias en el Sheet y asegura los encabezados."""
    sheet_metadata = sheets_service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    sheets = sheet_metadata.get('sheets', '')
    titles = [s['properties']['title'] for s in sheets]

    requests = []
    if 'Reuniones' not in titles:
        requests.append({'addSheet': {'properties': {'title': 'Reuniones'}}})
    if 'Salas' not in titles:
        requests.append({'addSheet': {'properties': {'title': 'Salas'}}})
    if 'Personal' not in titles:
        requests.append({'addSheet': {'properties': {'title': 'Personal'}}})
    
    if requests:
        sheets_service.spreadsheets().batchUpdate(spreadsheetId=SPREADSHEET_ID, body={'requests': requests}).execute()

    def asegurar_encabezados(hoja, encabezados):
        result = sheets_service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=f"{hoja}!A1:Z1").execute()
        if not result.get('values'):
            sheets_service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID, range=f"{hoja}!A1",
                valueInputOption='RAW', body={'values': [encabezados]}).execute()

    asegurar_encabezados('Reuniones', ['Timestamp', 'Titulo', 'Sala', 'Fecha Inicio', 'Fecha Fin', 'Participantes', 'Creado Por', 'Estado', 'Event ID'])
    asegurar_encabezados('Salas', ['Nombre de Sala'])
    asegurar_encabezados('Personal', ['Nombre', 'Correo', 'Sector', 'Estamento'])

def obtener_datos(sheets_service, rango):
    result = sheets_service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=rango).execute()
    return result.get('values', [])

def agregar_sala(sheets_service, nombre):
    body = {'values': [[nombre]]}
    sheets_service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID, range='Salas!A1', 
        valueInputOption='USER_ENTERED', body=body).execute()

def agregar_personal(sheets_service, nombre, correo, sector, estamento):
    body = {'values': [[nombre, correo, sector, estamento]]}
    sheets_service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID, range='Personal!A1', 
        valueInputOption='USER_ENTERED', body=body).execute()

def obtener_usuarios(sheets_service):
    datos = obtener_datos(sheets_service, 'Usuarios!A2:C')
    usuarios = []
    for i, fila in enumerate(datos):
        if len(fila) >= 3:
            usuarios.append({'fila_index': i + 2, 'usuario': fila[0], 'password': fila[1], 'rol': fila[2]})
    return usuarios

def agregar_usuario(sheets_service, usuario, password, rol):
    body = {'values': [[usuario, password, rol]]}
    sheets_service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID, range='Usuarios!A1', 
        valueInputOption='USER_ENTERED', body=body).execute()

def actualizar_usuario(sheets_service, fila_index, usuario, password, rol):
    rango = f"Usuarios!A{fila_index}:C{fila_index}"
    body = {'values': [[usuario, password, rol]]}
    sheets_service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID, range=rango,
        valueInputOption='USER_ENTERED', body=body).execute()

def obtener_credenciales_smtp():
    email = SMTP_USER_DEFAULT
    pwd = SMTP_PASS_DEFAULT
    try:
        if 'smtp' in st.secrets:
            email = st.secrets['smtp'].get('email', email)
            pwd = st.secrets['smtp'].get('password', pwd).replace(' ', '')
    except Exception:
        pass
    return email, pwd

def enviar_invitacion_email(titulo, sala, fecha_inicio_iso, fecha_fin_iso, emails_participantes, usuario, event_id=None, metodo='REQUEST'):
    if not emails_participantes:
        return
        
    smtp_user, smtp_pass = obtener_credenciales_smtp()
    if not smtp_user or not smtp_pass:
        print("Aviso: No hay credenciales SMTP configuradas.")
        return

    try:
        dt_ini = datetime.datetime.fromisoformat(fecha_inicio_iso)
        dt_fin = datetime.datetime.fromisoformat(fecha_fin_iso)
    except Exception as e:
        print(f"Error parseando fecha para email: {e}")
        return
        
    fecha_legible = dt_ini.strftime("%d/%m/%Y")
    hora_ini_legible = dt_ini.strftime("%H:%M")
    hora_fin_legible = dt_fin.strftime("%H:%M")
    
    dt_now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    ini_str = dt_ini.strftime('%Y%m%dT%H%M%S')
    fin_str = dt_fin.strftime('%Y%m%dT%H%M%S')
    
    uid = event_id if event_id else f"nexus_{int(datetime.datetime.now().timestamp())}"
    status = 'CONFIRMED' if metodo == 'REQUEST' else 'CANCELLED'
    asunto = f"Invitación: {titulo} - {fecha_legible} {hora_ini_legible} hrs" if metodo == 'REQUEST' else f"CANCELADA: {titulo} - {fecha_legible}"

    attendees_ics = []
    for em in emails_participantes:
        attendees_ics.append(f"ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE;CN={em}:mailto:{em}")
    att_block = "\r\n".join(attendees_ics)

    ics_content = (
        "BEGIN:VCALENDAR\r\n"
        "PRODID:-//Nexus Soluciones//Nexus Sync 1.0//ES\r\n"
        "VERSION:2.0\r\n"
        "CALSCALE:GREGORIAN\r\n"
        f"METHOD:{metodo}\r\n"
        "BEGIN:VTIMEZONE\r\n"
        "TZID:America/Santiago\r\n"
        "BEGIN:STANDARD\r\n"
        "DTSTART:19700101T000000\r\n"
        "TZOFFSETFROM:-0300\r\n"
        "TZOFFSETTO:-0300\r\n"
        "TZNAME:-03\r\n"
        "END:STANDARD\r\n"
        "END:VTIMEZONE\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}@nexus.sync\r\n"
        f"DTSTAMP:{dt_now}\r\n"
        f"DTSTART;TZID=America/Santiago:{ini_str}\r\n"
        f"DTEND;TZID=America/Santiago:{fin_str}\r\n"
        f"SUMMARY:{titulo}\r\n"
        f"LOCATION:{sala}\r\n"
        f"DESCRIPTION:Reunión convocada por: {usuario}\\nSala: {sala}\\nParticipantes: {', '.join(emails_participantes)}\r\n"
        f"ORGANIZER;CN=\"Nexus Sync - CESFAM\":mailto:{smtp_user}\r\n"
        f"{att_block}\r\n"
        f"STATUS:{status}\r\n"
        "SEQUENCE:0\r\n"
        "BEGIN:VALARM\r\n"
        "TRIGGER:-PT2H\r\n"
        "ACTION:DISPLAY\r\n"
        "DESCRIPTION:Recordatorio: 2 horas antes\r\n"
        "END:VALARM\r\n"
        "BEGIN:VALARM\r\n"
        "TRIGGER:-P1D\r\n"
        "ACTION:DISPLAY\r\n"
        "DESCRIPTION:Recordatorio: 1 día antes\r\n"
        "END:VALARM\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )

    color_header = "#1e3a8a" if metodo == 'REQUEST' else "#dc2626"
    titulo_header = "📅 Nueva Reunión Convocada" if metodo == 'REQUEST' else "❌ Reunión Cancelada"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f6f8; padding: 20px; margin: 0;">
        <div style="max-width: 600px; margin: auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <div style="background-color: {color_header}; color: #ffffff; padding: 20px; text-align: center;">
                <h2 style="margin: 0;">{titulo_header}</h2>
                <p style="margin: 5px 0 0 0; opacity: 0.9;">Nexus Sync - Gestión de Reuniones CESFAM</p>
            </div>
            <div style="padding: 25px;">
                <h3 style="color: #1f2937; margin-top: 0;">{titulo}</h3>
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                    <tr>
                        <td style="padding: 8px 0; color: #6b7280; width: 130px;"><b>🗓️ Fecha:</b></td>
                        <td style="padding: 8px 0; color: #111827;"><b>{fecha_legible}</b></td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #6b7280;"><b>⏰ Horario:</b></td>
                        <td style="padding: 8px 0; color: #111827;">{hora_ini_legible} a {hora_fin_legible} hrs</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #6b7280;"><b>📍 Sala / Lugar:</b></td>
                        <td style="padding: 8px 0; color: #111827;"><b>{sala}</b></td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #6b7280;"><b>👤 Convocado por:</b></td>
                        <td style="padding: 8px 0; color: #111827;">{usuario}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #6b7280; vertical-align: top;"><b>👥 Participantes:</b></td>
                        <td style="padding: 8px 0; color: #374151; font-size: 13px;">{', '.join(emails_participantes)}</td>
                    </tr>
                </table>
                <div style="background-color: #e0f2fe; border-left: 4px solid #0284c7; padding: 12px; border-radius: 4px; font-size: 13px; color: #0369a1;">
                    💡 <b>Tip de Calendario:</b> Si tu cliente de correo no añade la reunión automáticamente, abre el archivo adjunto <b>invitacion.ics</b> para guardarla en tu celular o Outlook.
                </div>
            </div>
            <div style="background-color: #f9fafb; padding: 15px; text-align: center; font-size: 11px; color: #9ca3af; border-top: 1px solid #e5e7eb;">
                Nexus Soluciones | Innovación y Gestión Tecnológica
            </div>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart("mixed")
    msg["Subject"] = asunto
    msg["From"] = f"Nexus Sync <{smtp_user}>"
    msg["To"] = ", ".join(emails_participantes)

    msg_alt = MIMEMultipart("alternative")
    msg_alt.attach(MIMEText(f"Reunión: {titulo}\nFecha: {fecha_legible}\nHorario: {hora_ini_legible} - {hora_fin_legible}\nSala: {sala}\n", "plain", "utf-8"))
    msg_alt.attach(MIMEText(html_body, "html", "utf-8"))

    part_cal = MIMEText(ics_content, "calendar; method=" + metodo, "utf-8")
    part_cal.add_header("Content-Class", "urn:content-classes:calendarmessage")
    msg_alt.attach(part_cal)
    msg.attach(msg_alt)

    part_file = MIMEBase("text", "calendar", name="invitacion.ics")
    part_file.set_payload(ics_content.encode("utf-8"))
    encoders.encode_base64(part_file)
    part_file.add_header("Content-Disposition", "attachment; filename=\"invitacion.ics\"")
    msg.attach(part_file)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, emails_participantes, msg.as_string())
        print(f"Invitaciones enviadas con éxito a: {', '.join(emails_participantes)}")
    except Exception as e:
        print(f"Error al enviar correo SMTP: {e}")

def actualizar_participantes(calendar_service, sheets_service, event_id, fila_index, emails_participantes):
    """Actualiza los invitados en Calendar, Sheets y reenvía correos."""
    participantes_str = ", ".join(emails_participantes)
    
    # 1. Actualizar descripción en Google Calendar con la Cuenta de Servicio
    try:
        ev = calendar_service.events().get(calendarId=CALENDAR_ID, eventId=event_id).execute()
        ev['description'] = f"Participantes actualizados:\n- " + "\n- ".join(emails_participantes)
        calendar_service.events().update(calendarId=CALENDAR_ID, eventId=event_id, body=ev).execute()
    except Exception as e:
        print(f"Aviso actualizando calendar: {e}")
        
    # 2. Actualizar en Google Sheets
    rango = f"Reuniones!F{fila_index + 1}"
    sheets_service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID, range=rango,
        valueInputOption='USER_ENTERED', body={'values': [[participantes_str]]}).execute()

    # 3. Reenviar invitación por correo a los participantes
    try:
        reunion = obtener_datos(sheets_service, f"Reuniones!B{fila_index + 1}:E{fila_index + 1}")
        if reunion and len(reunion[0]) >= 4:
            titulo = reunion[0][0]
            sala = reunion[0][1]
            inicio_iso = reunion[0][2]
            fin_iso = reunion[0][3]
            enviar_invitacion_email(titulo, sala, inicio_iso, fin_iso, emails_participantes, "Administrador", event_id, metodo='REQUEST')
    except Exception as e:
        print(f"Error reenviando invitación: {e}")

def agendar_reunion(calendar_service, sheets_service, titulo, sala, fecha_inicio_iso, fecha_fin_iso, emails_participantes, usuario):
    participantes_str = ", ".join(emails_participantes)
    
    descripcion_evento = (
        f"Reunión convocada por: {usuario}\n"
        f"Sala: {sala}\n"
        f"Participantes convocados:\n- " + "\n- ".join(emails_participantes)
    )

    evento = {
        'summary': f"{titulo} ({sala})",
        'location': sala,
        'description': descripcion_evento,
        'start': {'dateTime': fecha_inicio_iso, 'timeZone': 'America/Santiago'},
        'end': {'dateTime': fecha_fin_iso, 'timeZone': 'America/Santiago'},
        'reminders': {
            'useDefault': False, 
            'overrides': [
                {'method': 'popup', 'minutes': 120},
                {'method': 'email', 'minutes': 1440}
            ]
        },
    }
    
    # 1. Crear evento en Google Calendar institucional con la Cuenta de Servicio
    event_result = calendar_service.events().insert(calendarId=CALENDAR_ID, body=evento).execute()
    event_id = event_result['id']

    # 2. Guardar en Google Sheets para Looker Studio y Dashboard
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fila = [[timestamp, titulo, sala, fecha_inicio_iso, fecha_fin_iso, participantes_str, usuario, 'Activa', event_id]]
    
    sheets_service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID, range='Reuniones!A1',
        valueInputOption='USER_ENTERED', body={'values': fila}).execute()

    # 3. Enviar invitaciones por correo con archivo .ics interactivo
    enviar_invitacion_email(titulo, sala, fecha_inicio_iso, fecha_fin_iso, emails_participantes, usuario, event_id, metodo='REQUEST')

def cancelar_reunion(calendar_service, sheets_service, event_id, fila_index):
    # 1. Obtener datos antes de cancelar para mandar notificación
    try:
        reunion = obtener_datos(sheets_service, f"Reuniones!B{fila_index + 1}:F{fila_index + 1}")
        if reunion and len(reunion[0]) >= 5:
            titulo = reunion[0][0]
            sala = reunion[0][1]
            inicio_iso = reunion[0][2]
            fin_iso = reunion[0][3]
            participantes = [c.strip() for c in reunion[0][4].split(",") if c.strip()]
            enviar_invitacion_email(titulo, sala, inicio_iso, fin_iso, participantes, "Administrador", event_id, metodo='CANCEL')
    except Exception as e:
        print(f"Aviso al notificar cancelación: {e}")

    # 2. Eliminar de Google Calendar
    try:
        calendar_service.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
    except Exception as e:
        print(f"Aviso: El evento ya no estaba en el calendario o hubo un error: {e}")
    
    # 3. Actualizar estado a 'Cancelada' en Google Sheets
    rango_estado = f"Reuniones!H{fila_index + 1}"
    sheets_service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID, range=rango_estado,
        valueInputOption='USER_ENTERED', body={'values': [['Cancelada']]}).execute()

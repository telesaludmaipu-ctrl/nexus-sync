import os
import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/spreadsheets'
]

SPREADSHEET_ID = '1zfhpffSAT4DRiDWx34SVvsF8FQbKNR-DTm9DKJs6PK4'

import streamlit as st

def obtener_servicios_google():
    creds = None
    base_dir = os.path.dirname(os.path.abspath(__file__))
    token_path = os.path.join(base_dir, 'token.json')
    credentials_path = os.path.join(base_dir, 'credentials.json')
    
    # 1. Intentar leer token local
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    # 2. Intentar leer desde st.secrets (Nube)
    elif 'google_token' in st.secrets:
        token_info = dict(st.secrets['google_token'])
        creds = Credentials.from_authorized_user_info(token_info, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                raise FileNotFoundError("Falta credentials.json y no hay st.secrets configurados.")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Guardar localmente solo si no estamos en la nube
        if not ('google_token' in st.secrets):
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

def actualizar_participantes(calendar_service, sheets_service, event_id, fila_index, emails_participantes):
    """Actualiza los invitados en Calendar y en Sheets."""
    attendees = [{'email': email} for email in emails_participantes]
    try:
        calendar_service.events().patch(
            calendarId='primary', eventId=event_id, 
            body={'attendees': attendees}, sendUpdates='all'
        ).execute()
    except Exception as e:
        print(f"No se pudo actualizar en calendar: {e}")
        
    participantes_str = ", ".join(emails_participantes)
    rango = f"Reuniones!F{fila_index + 1}"
    sheets_service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID, range=rango,
        valueInputOption='USER_ENTERED', body={'values': [[participantes_str]]}).execute()

def agendar_reunion(calendar_service, sheets_service, titulo, sala, fecha_inicio_iso, fecha_fin_iso, emails_participantes, usuario):
    attendees = [{'email': email} for email in emails_participantes]
    
    # Calcular recordatorios:
    # 1. En la mañana (08:00 AM) del día anterior a la reunión
    inicio_dt = datetime.datetime.fromisoformat(fecha_inicio_iso)
    dia_anterior_manana = (inicio_dt - datetime.timedelta(days=1)).replace(hour=8, minute=0, second=0)
    minutos_antes_manana = int((inicio_dt - dia_anterior_manana).total_seconds() / 60)
    
    # Si por alguna razón la reunión se agenda para hoy mismo o algo falla, 
    # garantizamos al menos un recordatorio de 24 horas como resguardo
    if minutos_antes_manana <= 0:
        minutos_antes_manana = 1440 
        
    # 2. 2 horas antes de la reunión
    minutos_2_horas = 120

    evento = {
        'summary': titulo,
        'location': sala,
        'start': {'dateTime': fecha_inicio_iso, 'timeZone': 'America/Santiago'},
        'end': {'dateTime': fecha_fin_iso, 'timeZone': 'America/Santiago'},
        'attendees': attendees,
        'reminders': {
            'useDefault': False, 
            'overrides': [
                {'method': 'email', 'minutes': minutos_antes_manana}, 
                {'method': 'popup', 'minutes': minutos_2_horas}
            ]
        },
    }
    
    event_result = calendar_service.events().insert(calendarId='primary', body=evento, sendUpdates='all').execute()
    event_id = event_result['id']

    participantes_str = ", ".join(emails_participantes)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fila = [[timestamp, titulo, sala, fecha_inicio_iso, fecha_fin_iso, participantes_str, usuario, 'Activa', event_id]]
    
    sheets_service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID, range='Reuniones!A1',
        valueInputOption='USER_ENTERED', body={'values': fila}).execute()

def cancelar_reunion(calendar_service, sheets_service, event_id, fila_index):
    # 1. Eliminar del calendario
    try:
        calendar_service.events().delete(calendarId='primary', eventId=event_id, sendUpdates='all').execute()
    except Exception as e:
        print(f"Aviso: El evento ya no estaba en el calendario o hubo un error: {e}")
    
    # 2. Actualizar estado a "Cancelada" en Google Sheets para trazabilidad
    rango_estado = f"Reuniones!H{fila_index + 1}"
    sheets_service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID, range=rango_estado,
        valueInputOption='USER_ENTERED', body={'values': [['Cancelada']]}).execute()

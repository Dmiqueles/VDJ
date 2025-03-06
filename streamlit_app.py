import streamlit as st
import gspread
from datetime import datetime, date, timedelta
from oauth2client.service_account import ServiceAccountCredentials
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
import pandas as pd
import itertools

# Configuración inicial de la página (debe ser la primera llamada)
st.set_page_config(
    page_title="RUDO.VOD",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --------------------------
# 1. Sistema de Login Simple
# --------------------------
def check_login():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        
    if not st.session_state.logged_in:
        with st.container():
            col1, col2, col3 = st.columns([1, 3, 1])
            with col2:
                st.title("🔐 Acceso")
                user = st.text_input("Usuario")
                password = st.text_input("Contraseña", type="password")
                
                if st.button("Ingresar", use_container_width=True):
                    if user == "admin" and password == "admin123":
                        st.session_state.logged_in = True
                        st.session_state.mode = None  # Inicializar el modo
                        st.rerun()  # Recargar la aplicación
                    else:
                        st.error("Credenciales incorrectas")
        st.stop()  # Detener la ejecución si no se ha iniciado sesión

    # Selección de modos después del login
    if st.session_state.logged_in and 'mode' not in st.session_state:
        with st.container():
            col1, col2, col3 = st.columns([1, 3, 1])
            with col2:
                st.title("🎛️ Selecciona el Modo")
                mode = st.radio(
                    "Elige el modo de interfaz:",
                    ["Modo Simple", "Modo Completo"],
                    index=0  # Por defecto, Modo Simple
                )
                if st.button("Continuar", use_container_width=True):
                    st.session_state.mode = mode
                    st.rerun()  # Recargar la aplicación para aplicar el modo
        st.stop()  # Detener la ejecución hasta que se seleccione un modo

# Función para autenticar Google Sheets usando Streamlit Secrets
def authenticate_google_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # Obtener credenciales desde st.secrets
        credentials_dict = st.secrets["google_sheets"]
        
        # Crear credenciales desde el diccionario
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
        client = gspread.authorize(credentials)
        
        return client
    except Exception as e:
        st.error(f"Error al autenticar Google Sheets: {e}")
        return None

# Función para cargar programas desde Google Sheets
def load_programs_from_google_sheet(sheet_name):
    client = authenticate_google_sheets()
    if not client:
        return []
    try:
        spreadsheet_id = '1Ka9YhP860lZlibXudUkr7an7zGs-spO54KBmidpNr1A'  # ID de tu Google Sheet
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)  # Seleccionar la hoja por nombre
        data = worksheet.get_all_records()
        programs = [{'name': row['Name'], 'duration': row['Duration']} for row in data]
        st.session_state.messages.append({"type": "success", "content": f"Programas cargados correctamente desde la hoja: {sheet_name}"})
        return programs
    except Exception as e:
        st.session_state.messages.append({"type": "error", "content": f"Error al cargar programas desde la hoja {sheet_name}: {e}"})
        return []

# Función para cargar promos desde Google Sheets
def load_promos_from_google_sheet():
    client = authenticate_google_sheets()
    if not client:
        return []
    try:
        spreadsheet_id = '17AtkM82WEWczbzLvHSq-XYQbiAImTNkmSguDlDg_46g'
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.sheet1
        data = worksheet.get_all_records()
        promos = []
        for row in data:
            try:
                h, m, s = map(int, row['Duration'].split(':'))
                duration_seconds = h * 3600 + m * 60 + s
                promos.append({'name': row['Name'], 'duration': duration_seconds})
            except ValueError:
                st.session_state.messages.append({"type": "error", "content": f"Error al procesar la duración de la promo '{row['Name']}'. Formato inválido: {row['Duration']}"})
        st.session_state.messages.append({"type": "success", "content": "Promos cargadas correctamente"})
        return promos
    except Exception as e:
        st.session_state.messages.append({"type": "error", "content": f"Error al cargar promos: {e}"})
        return []

# Función para cargar rellenos desde una hoja específica de Google Sheets
def load_fillers_from_google_sheet(sheet_name):
    client = authenticate_google_sheets()
    if not client:
        return []
    try:
        spreadsheet_id = '1MjcPISQEPUvYAHqVtW7nvweqfXhaS_cAbREjeG3uK-I'
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)  # Seleccionar la hoja por nombre
        data = worksheet.get_all_records()
        fillers = []
        for row in data:
            try:
                h, m, s = map(int, row['Duration'].split(':'))
                duration_seconds = h * 3600 + m * 60 + s
                fillers.append({'name': row['Name'], 'duration': duration_seconds})
            except ValueError:
                st.session_state.messages.append({"type": "error", "content": f"Error al procesar la duración del relleno '{row['Name']}'. Formato inválido: {row['Duration']}"})
        st.session_state.messages.append({"type": "success", "content": f"Rellenos cargados correctamente desde la hoja: {sheet_name}"})
        return fillers
    except Exception as e:
        st.session_state.messages.append({"type": "error", "content": f"Error al cargar rellenos: {e}"})
        return []


# Función para cargar programas nocturnos desde Google Sheets
def load_night_programs_from_google_sheet():
    client = authenticate_google_sheets()
    if not client:
        return []
    try:
        spreadsheet_id = '1Ka9YhP860lZlibXudUkr7an7zGs-spO54KBmidpNr1A'  # Reemplaza con el ID de tu hoja de programas nocturnos
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.sheet1
        data = worksheet.get_all_records()
        programs = [{'name': row['Name'], 'duration': row['Duration']} for row in data]
        st.session_state.messages.append({"type": "success", "content": "Programas nocturnos cargados correctamente"})
        return programs
    except Exception as e:
        st.session_state.messages.append({"type": "error", "content": f"Error al cargar programas nocturnos: {e}"})
        return []

# Función para listar las hojas disponibles en el Google Sheet
def list_sheets():
    client = authenticate_google_sheets()
    if not client:
        return []
    try:
        spreadsheet_id = '1MjcPISQEPUvYAHqVtW7nvweqfXhaS_cAbREjeG3uK-I'
        spreadsheet = client.open_by_key(spreadsheet_id)
        sheets = [sheet.title for sheet in spreadsheet.worksheets()]
        return sheets
    except Exception as e:
        st.session_state.messages.append({"type": "error", "content": f"Error al listar las hojas: {e}"})
        return []

def hex_to_rgb(hex_color):
    """
    Convierte un color hexadecimal en un diccionario con valores RGB.
    Ejemplo: "#ea4335" -> {"red": 0.9176, "green": 0.2627, "blue": 0.2078}
    """
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    return {"red": r, "green": g, "blue": b}

# Función para exportar a Google Sheets con colores personalizados
def export_to_google_sheets(playlist, sheet_title, selected_sheet):
    try:
        client = authenticate_google_sheets()
        if not client:
            return
        
        # Inicializar la lista de formatos
        formats = []
        
        spreadsheet_id = '1SeKSZLR7IWrVVj9ny5hezcS-Nro06Amp9S29W6pMovU'  # Reemplaza con tu ID
        spreadsheet = client.open_by_key(spreadsheet_id)

        # Crear una nueva hoja dentro del Google Sheet
        worksheet = spreadsheet.add_worksheet(title=sheet_title, rows="100", cols="6")

        # Escribir los encabezados en la primera fila
        headers = ['Item', 'Hora de Inicio', 'Nombre', 'Duración', 'Tipo', 'Relleno']
        worksheet.update(values=[headers], range_name='A1:F1')

        # Obtener la configuración del relleno seleccionado
        relleno_info = relleno_config.get(selected_sheet, {})
        type_colors = relleno_info.get("type_colors", {})

        # Crear las filas de datos
        rows = []
        for i, block in enumerate(playlist, start=2):  # Comenzar desde la fila 2
            rows.append([
                block['item'],  # Número de ítem
                block['start_time'],
                block['name'],
                block['duration'],
                block['type'],
                block.get('relleno', ''),  # Agregar el relleno seleccionado
            ])

            # Determinar el color de fondo según el tipo de contenido
            background_color = type_colors.get(block['type'], "#FFFFFF")  # Color por defecto si no se encuentra

            # Aplicar formato de color a la fila
            row_range = f'A{i}:F{i}'
            formats.append({
                "range": row_range,
                "format": {
                    "backgroundColor": hex_to_rgb(background_color),
                    "textFormat": {"bold": block['type'] in ['Program', 'Tanda']}
                }
            })

        # Escribir las filas en una sola llamada
        worksheet.update(values=rows, range_name=f'A2:F{len(rows) + 1}')

        # Aplicar los formatos en un solo lote
        worksheet.batch_format(formats)

        # Aplicar formato a los encabezados
        worksheet.format('A1:F1', {
            'backgroundColor': hex_to_rgb("#007ACC"),  # Azul claro
            'textFormat': {'bold': True, 'foregroundColor': hex_to_rgb("#FFFFFF")}  # Blanco
        })

        st.session_state.messages.append({"type": "success", "content": f"Playlist exportada correctamente a Google Sheets: {spreadsheet.url} -> {sheet_title}"})
    except Exception as e:
        st.session_state.messages.append({"type": "error", "content": f"Error al exportar a Google Sheets: {e}"})
        
def find_exact_combination(target, content_list):
    # Versión optimizada para grandes volúmenes
    dp = {0: []}
    for content in sorted(content_list, key=lambda x: -x['duration']):
        for s in list(dp.keys()):
            new_sum = s + content['duration']
            if new_sum <= target:
                if new_sum not in dp or len(dp[new_sum]) > len(dp[s]) + 1:
                    dp[new_sum] = dp[s] + [content]
    return dp.get(target, None)

# Mover format_duration fuera 
def format_duration(s):
    if not isinstance(s, (int, float)) or s < 0:
        return "00:00:00"
    return f"{int(s//3600):02d}:{int((s//60)%60):02d}:{int(s%60):02d}"

# Función para seleccionar un programa que no sea el último y que quepa en el tiempo restante
def select_program(user_programs, last_program, time_remaining):
    for program in user_programs:
        if program['name'] != last_program and program['duration_seconds'] <= time_remaining:
            return program
    return None

# Función para agregar promos y rellenos al bloque especial
def add_promos_and_fillers(block_special, time_remaining, promos, fillers, item_counter, current_time):
    combination = find_optimal_combination(time_remaining, promos + fillers)
    if combination:
        for content in combination:
            content_type = 'Promo' if content in promos else 'Filler'
            block_special.append({
                "item": item_counter,
                "start_time": current_time.strftime("%H:%M:%S"),
                "name": content['name'],
                "duration": format_duration(content['duration_seconds']),
                "duration_seconds": content['duration_seconds'],
                "type": content_type,
                "block": "Especial"
            })
            item_counter += 1
            current_time += timedelta(seconds=content['duration_seconds'])
            time_remaining -= content['duration_seconds']
    return block_special, item_counter, current_time, time_remaining

# Diccionario de configuración de rellenos
relleno_config = {
    "Cultura": {
        "Normal": {"background": "#bf9000", "text": "#000000"},
        "¿Sabías qué?": {"background": "#93c47d", "text": "#000000"},
        "En tus palabras": {"background": "#ff6d01", "text": "#000000"},
        "Texto de tanda": "TANDA RELLENO 1 MIN CULTURA NEW",
        "Color de tanda": "#f1c232",
        "type_colors": {
            'Program': '#FFFFFF',  # Blanco
            'Tanda': '#f1c232',    # Amarillo (color de tanda para Cultura)
            'Promo': '#46bdc6',    # Turquesa
            'Filler': '#bf9000',   # Marrón (color de fondo normal para Cultura)
            'Tanda Parcial': '#FFFF00',  # Amarillo
        }
    },
    "Teleseries": {
        "Color de fondo": "#9d34a8",
        "Color de texto": "#000000",
        "Texto de tanda": "TANDA 60 SEGUNDOS 13T NEW",
        "Color de tanda": "#b4a7d6",
        "type_colors": {
            'Program': '#FFFFFF',  # Blanco
            'Tanda': '#b4a7d6',    # Lila (color de tanda para Teleseries)
            'Promo': '#46bdc6',    # Turquesa
            'Filler': '#9d34a8',   # Morado (color de fondo para Teleseries)
            'Tanda Parcial': '#FFFF00',  # Amarillo
        }
    },
    "Realities": {
        "Color de fondo": "#ff0000",
        "Color de texto": "#000000",
        "Texto de tanda": "TANDA 60 SEGUNDOS 13R NEW",
        "Color de tanda": "#f06e63",
        "type_colors": {
            'Program': '#FFFFFF',  # Blanco
            'Tanda': '#f06e63',    # Rojo claro (color de tanda para Realities)
            'Promo': '#46bdc6',    # Turquesa
            'Filler': '#ff0000',   # Rojo (color de fondo para Realities)
            'Tanda Parcial': '#FFFF00',  # Amarillo
        }
    },
    "Festival": {
        "Color de fondo": "#d83787",
        "Color de texto": "#000000",
        "Texto de tanda": "TANDA 60 SEGUNDOS 13FESTIVAL NEW",
        "Color de tanda": "#c27ba0",
        "type_colors": {
            'Program': '#FFFFFF',  # Blanco
            'Tanda': '#c27ba0',    # Rosa (color de tanda para Festival)
            'Promo': '#46bdc6',    # Turquesa
            'Filler': '#d83787',   # Rosa oscuro (color de fondo para Festival)
            'Tanda Parcial': '#FFFF00',  # Amarillo
        }
    },
    "Pop": {
        "Color de fondo": "#ea4335",
        "Color de texto": "#000000",
        "Texto de tanda": "TANDA 60 SEGUNDOS 13POP",
        "Color de tanda": "#fbbc04",
        "type_colors": {
            'Program': '#FFFFFF',  # Blanco
            'Tanda': '#fbbc04',    # Naranja (color de tanda para Pop)
            'Promo': '#46bdc6',    # Turquesa
            'Filler': '#ea4335',   # Rojo (color de fondo para Pop)
            'Tanda Parcial': '#FFFF00',  # Amarillo
        }
    },
}

# Función para generar la playlist
def generate_playlist(start_time, end_time, promos, fillers, user_programs, selected_sheet, include_block_zero=True):
    def format_duration(s):
        if not isinstance(s, (int, float)) or s < 0:
            return "00:00:00"
        return f"{int(s//3600):02d}:{int((s//60)%60):02d}:{int(s%60):02d}"

    # Obtener la configuración del relleno seleccionado
    relleno_info = relleno_config.get(selected_sheet, {})
    tanda_text = relleno_info.get("Texto de tanda", "TANDA 60s")  # Texto de tanda personalizado

    # Verificar si el horario de fin es del día siguiente
    start_date = date.today()
    if end_time < start_time:
        end_date = start_date + timedelta(days=1)  # El horario de fin es del día siguiente
    else:
        end_date = start_date  # El horario de fin es del mismo día

    # Convertir a datetime
    start_datetime = datetime.combine(start_date, start_time)
    end_datetime = datetime.combine(end_date, end_time)

    current_time = start_datetime
    playlist = []
    item_counter = 1

    # Bloque 0 (Tanda inicial) - Solo si include_block_zero es True
    if include_block_zero:
        playlist.append({
            "item": item_counter,
            "start_time": current_time.strftime("%H:%M:%S"),
            "name": tanda_text,  # Usar el texto de tanda personalizado
            "duration": "00:01:00",
            "duration_seconds": 60,
            "type": "Tanda",
            "block": 0,
            "relleno": selected_sheet,  # Agregar el relleno seleccionado
        })
        item_counter += 1
        current_time += timedelta(seconds=60)

    # Precalcular duraciones
    for program in user_programs:
        program['duration_seconds'] = parse_duration(program['duration'])
    for promo in promos:
        promo['duration_seconds'] = parse_duration(promo['duration'])
    for filler in fillers:
        filler['duration_seconds'] = parse_duration(filler['duration'])

    # Generar bloques iniciales
    initial_blocks = []
    while user_programs:
        block = []
        program = user_programs.pop(0)
        program_duration = program['duration_seconds']
        
        # Programa principal
        block.append({
            "item": item_counter,
            "start_time": current_time.strftime("%H:%M:%S"),
            "name": program['name'],
            "duration": format_duration(program_duration),
            "duration_seconds": program_duration,
            "type": "Program",
            "block": len(initial_blocks) + 1,
            "relleno": selected_sheet,  # Agregar el relleno seleccionado
        })
        item_counter += 1
        current_time += timedelta(seconds=program_duration)

        # Calcular tiempo hasta siguiente bloque
        next_block_time = calculate_time_to_next_block(current_time)
        remaining_block_time = (next_block_time - current_time).total_seconds()
        remaining_block_time = max(remaining_block_time, 0)

        # Tanda de 60s obligatoria
        if remaining_block_time >= 60:
            block.append({
                "item": item_counter,
                "start_time": current_time.strftime("%H:%M:%S"),
                "name": tanda_text,  # Usar el texto de tanda personalizado
                "duration": "00:01:00",
                "duration_seconds": 60,
                "type": "Tanda",
                "block": len(initial_blocks) + 1,
                "relleno": selected_sheet,  # Agregar el relleno seleccionado
            })
            item_counter += 1
            current_time += timedelta(seconds=60)
            remaining_block_time -= 60

        # Rellenar con promos/rellenos
        if remaining_block_time > 0:
            combination = find_optimal_combination(remaining_block_time, promos + fillers)
            if combination:
                for content in combination:
                    content_type = 'Promo' if content in promos else 'Filler'
                    block.append({
                        "item": item_counter,
                        "start_time": current_time.strftime("%H:%M:%S"),
                        "name": content['name'],
                        "duration": format_duration(content['duration_seconds']),
                        "duration_seconds": content['duration_seconds'],
                        "type": content_type,
                        "block": len(initial_blocks) + 1,
                        "relleno": selected_sheet,  # Agregar el relleno seleccionado
                    })
                    item_counter += 1
                    current_time += timedelta(seconds=content['duration_seconds'])
                    remaining_block_time -= content['duration_seconds']

        # Tanda parcial residual
        if remaining_block_time > 0:
            block.append({
                "item": item_counter,
                "start_time": current_time.strftime("%H:%M:%S"),
                "name": f"Tanda Parcial ({int(remaining_block_time)}s)",
                "duration": format_duration(remaining_block_time),
                "duration_seconds": remaining_block_time,
                "type": "Tanda Parcial",
                "block": len(initial_blocks) + 1,
                "relleno": selected_sheet,  # Agregar el relleno seleccionado
            })
            item_counter += 1
            current_time += timedelta(seconds=remaining_block_time)

        initial_blocks.append(block)
        # Agregar bloque inicial a la playlist
        for item in block:
            playlist.append(item)

    # Repetición cíclica de bloques
    block_index = 0
    while current_time < end_datetime:
        current_block = initial_blocks[block_index % len(initial_blocks)]
        block_duration = sum(item['duration_seconds'] for item in current_block)
        
        if current_time + timedelta(seconds=block_duration) > end_datetime:
            break

        for item in current_block:
            playlist.append({
                "item": item_counter,
                "start_time": current_time.strftime("%H:%M:%S"),
                "name": item['name'],
                "duration": item['duration'],
                "type": item['type'],
                "block": item['block'],
                "relleno": selected_sheet,  # Agregar el relleno seleccionado
            })
            item_counter += 1
            current_time += timedelta(seconds=item['duration_seconds'])
        
        block_index += 1

    # Bloque especial final
    time_remaining = (end_datetime - current_time).total_seconds()
    if time_remaining > 0:
        last_program = playlist[-1]['name'] if playlist and playlist[-1]['type'] == 'Program' else None
        selected_program = next((p for p in user_programs if p['name'] != last_program and p['duration_seconds'] <= time_remaining), None)
        
        block_special = []
        if selected_program:
            block_special.append({
                "item": item_counter,
                "start_time": current_time.strftime("%H:%M:%S"),
                "name": selected_program['name'],
                "duration": format_duration(selected_program['duration_seconds']),
                "duration_seconds": selected_program['duration_seconds'],
                "type": "Program",
                "block": "Especial",
                "relleno": selected_sheet,  # Agregar el relleno seleccionado
            })
            item_counter += 1
            current_time += timedelta(seconds=selected_program['duration_seconds'])
            time_remaining -= selected_program['duration_seconds']

        if time_remaining >= 60:
            block_special.append({
                "item": item_counter,
                "start_time": current_time.strftime("%H:%M:%S"),
                "name": tanda_text,  # Usar el texto de tanda personalizado
                "duration": "00:01:00",
                "duration_seconds": 60,
                "type": "Tanda",
                "block": "Especial",
                "relleno": selected_sheet,  # Agregar el relleno seleccionado
            })
            item_counter += 1
            current_time += timedelta(seconds=60)
            time_remaining -= 60

        if time_remaining > 0:
            combination = find_optimal_combination(time_remaining, promos + fillers)
            if combination:
                for content in combination:
                    content_type = 'Promo' if content in promos else 'Filler'
                    block_special.append({
                        "item": item_counter,
                        "start_time": current_time.strftime("%H:%M:%S"),
                        "name": content['name'],
                        "duration": format_duration(content['duration_seconds']),
                        "duration_seconds": content['duration_seconds'],
                        "type": content_type,
                        "block": "Especial",
                        "relleno": selected_sheet,  # Agregar el relleno seleccionado
                    })
                    item_counter += 1
                    current_time += timedelta(seconds=content['duration_seconds'])
                    time_remaining -= content['duration_seconds']

        playlist.extend(block_special)

    return playlist

def find_optimal_combination(time_available, content_pool, max_tandas=3):
    best_combination = []
    best_score = -1
    
    for r in range(1, 4):  # Probar combinaciones de 1 a 3 elementos
        for combo in itertools.combinations(content_pool, r):
            total_time = sum(c['duration'] for c in combo)
            tanda_count = sum(1 for c in combo if c['duration'] == 60)
            
            if total_time > time_available:
                continue
            if tanda_count > max_tandas:
                continue
                
            score = total_time * 10 - tanda_count * 1000
            if score > best_score:
                best_score = score
                best_combination = combo
                
    return best_combination if best_score > -1 else None

# Función para convertir duración en formato HH:MM:SS a segundos
def parse_duration(duration_str):
    if isinstance(duration_str, (int, float)):  # Si ya es un número, lo devolvemos directamente
        return duration_str
    try:
        parts = list(map(int, duration_str.split(':')))  # Convertir a lista de enteros
        if len(parts) == 2:  # Formato MM:SS
            return parts[0] * 60 + parts[1]
        elif len(parts) == 3:  # Formato HH:MM:SS
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        else:
            raise ValueError(f"Formato de duración inválido: {duration_str}")
    except Exception as e:
        raise ValueError(f"Error al parsear la duración: {e}")

# Función para calcular el tiempo hasta el siguiente bloque
def calculate_time_to_next_block(current_time):
    valid_start_minutes = [0, 15, 30, 45]
    current_hour, current_minute = current_time.hour, current_time.minute
    next_valid_minutes = [m for m in valid_start_minutes if m > current_minute]
    
    if next_valid_minutes:
        next_minute = next_valid_minutes[0]
    else:
        next_minute = valid_start_minutes[0]
        current_hour += 1  # Pasamos a la siguiente hora si no hay minutos válidos en la actual
    
    next_block_time = current_time.replace(hour=current_hour % 24, minute=next_minute, second=0, microsecond=0)
    return next_block_time

# Interfaz de Streamlit
def main():
    # Verificar el login y la selección de modos
    check_login()
    
    # Inicializar estados
    if 'playlist' not in st.session_state:
        st.session_state.playlist = None
    if 'sheet_title' not in st.session_state:
        st.session_state.sheet_title = f"Playlist_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'programs' not in st.session_state:
        st.session_state.programs = []

    # ------------------------------------------------------
    # Selector de modo en la barra lateral
    # ------------------------------------------------------
    with st.sidebar:
        st.header("🎛️ Modo de Interfaz")
        new_mode = st.radio(
            "Selecciona el modo:",
            ["Modo Simple", "Modo Completo"],
            index=0 if st.session_state.mode == "Modo Simple" else 1
        )
        if new_mode != st.session_state.mode:
            st.session_state.mode = new_mode
            st.rerun()  # Recargar la aplicación para aplicar el nuevo modo

    # ------------------------------------------------------
    # Modo Simple (Para móviles)
    # ------------------------------------------------------
    if st.session_state.mode == "Modo Simple":
        st.title("🎧 Modo Simple")
        st.markdown("---")

        # Selector de hoja de rellenos
        sheets = list_sheets()
        selected_sheet = st.selectbox(
            "📂 Seleccionar hoja de rellenos:", 
            sheets if sheets else ["No disponible"],
            disabled=not sheets
        )

        # Botón para generar la playlist
        # Modo Simple
        # Modo Simple
        if st.button("✨ Generar Playlist", type="primary", use_container_width=True):
            # Cargar datos antes de generar la playlist
            with st.spinner("🔍 Cargando programas, promos y rellenos..."):
                promos = load_promos_from_google_sheet()
                day_programs = load_programs_from_google_sheet("dia")  # Cargar programas diurnos
                fillers = load_fillers_from_google_sheet(selected_sheet) if sheets else []

                # Verificar si hay datos suficientes
                if not day_programs or not promos or not fillers:
                    st.session_state.messages.append({"type": "warning", "content": "Faltan datos para generar la playlist"})
                else:
                    # Usar horarios predeterminados en modo simple
                    start_time = datetime.strptime("05:59:00", "%H:%M:%S").time()
                    end_time = datetime.strptime("23:59:00", "%H:%M:%S").time()

                    # Generar playlist
                    playlist = generate_playlist(start_time, end_time, promos, fillers, day_programs, selected_sheet)  # Agregar selected_sheet
                    st.session_state.playlist = playlist
                    st.session_state.messages.append({"type": "success", "content": "Playlist generada correctamente"})

                    # Exportar automáticamente a Google Sheets
                    export_to_google_sheets(st.session_state.playlist, st.session_state.sheet_title, selected_sheet)  # Agregar selected_sheet
                    st.session_state.messages.append({"type": "success", "content": "Playlist exportada a Google Sheets"})
        # Mostrar mensajes de notificación
        if st.session_state.messages:
            st.markdown("### 📢 Notificaciones")
            for msg in st.session_state.messages[-3:]:  # Mostrar últimos 3 mensajes
                if msg["type"] == "success":
                    st.success(msg["content"], icon="✅")
                elif msg["type"] == "error":
                    st.error(msg["content"], icon="❌")
                elif msg["type"] == "warning":
                    st.warning(msg["content"], icon="⚠️")

    # ------------------------------------------------------
    # Modo Completo (Para escritorio)
    # ------------------------------------------------------
    else:
        st.title("🎧 Modo Completo")
        st.markdown("---")

        # Crear 3 columnas
        col1, col2, col3 = st.columns([1, 2, 1])

        # ------------------------------------------------------
        # Columna 1: Configuración y controles principales
        # ------------------------------------------------------
        with col1:
            st.header("⚙️ Configuración")
            
            # Selector de hoja de rellenos
            sheets = list_sheets()
            selected_sheet = st.selectbox(
                "📂 Seleccionar hoja de rellenos:", 
                sheets if sheets else ["No disponible"],
                disabled=not sheets
            )
            
            st.markdown("---")
            
            # Configuración de horarios
            st.subheader("⏰ Horarios")
            use_night_schedule = st.toggle("🌙 Usar horario nocturno", value=False)
            
            st.markdown("**Horario diurno**")
            day_start_time = st.time_input("Hora de inicio (diurno)", value=datetime.strptime("05:59:00", "%H:%M:%S").time())
            day_end_time = st.time_input("Hora de fin (diurno)", value=datetime.strptime("21:00:00", "%H:%M:%S").time())
            
            if use_night_schedule:
                st.markdown("**Horario nocturno**")
                night_start_time = st.time_input("Hora de inicio (nocturno)", value=datetime.strptime("21:00:00", "%H:%M:%S").time())
                night_end_time = st.time_input("Hora de fin (nocturno)", value=datetime.strptime("06:00:00", "%H:%M:%S").time())
            
            st.markdown("---")
            
            # Botón para generar la playlist
            # Modo Completo
            if st.button("✨ Generar Playlist", type="primary", use_container_width=True):
                # Cargar datos antes de generar la playlist
                with st.spinner("🔍 Cargando programas, promos y rellenos..."):
                    promos = load_promos_from_google_sheet()
                    day_programs = load_programs_from_google_sheet("dia")  # Cargar programas diurnos
                    night_programs = load_programs_from_google_sheet("noche") if use_night_schedule else []  # Cargar programas nocturnos
                    fillers = load_fillers_from_google_sheet(selected_sheet) if sheets else []

                    # Verificar si hay datos suficientes
                    if not day_programs or not promos or not fillers:
                        st.session_state.messages.append({"type": "warning", "content": "Faltan datos para generar la playlist"})
                    else:
                        # Generar playlist diurna
                        day_playlist = generate_playlist(day_start_time, day_end_time, promos, fillers, day_programs, selected_sheet)  # Agregar selected_sheet
                        
                        # Generar playlist nocturna (si está activado)
                        night_playlist = []
                        if use_night_schedule:
                            night_playlist = generate_playlist(night_start_time, night_end_time, promos, fillers, night_programs, selected_sheet, include_block_zero=False)  # Agregar selected_sheet
                        
                        # Combinar playlists
                        st.session_state.playlist = day_playlist + night_playlist
                        st.session_state.messages.append({"type": "success", "content": "Playlist generada correctamente"})
        # ------------------------------------------------------
        # Columna 2: Vista previa de la playlist
        # ------------------------------------------------------
        
        with col2:
            st.header("📜 Vista Previa de la Playlist")
            
            if st.session_state.playlist:
                # Convertir la playlist en un DataFrame
                playlist_df = pd.DataFrame(st.session_state.playlist)
                
                # Definir colores para cada tipo de contenido
                type_colors = {
                    'Program': 'background-color: #FFFFFF; color: #000000;',  # Blanco
                    'Tanda': 'background-color: #00FF00; color: #000000;',    # Verde
                    'Promo': 'background-color: #46bdc6; color: #000000;',   # Turquesa
                    'Filler': 'background-color: #808080; color: #FFFFFF;',  # Gris
                    'Tanda Parcial': 'background-color: #FFFF00; color: #000000;',  # Amarillo
                }
                
                # Función para aplicar colores
                def apply_colors(row, selected_sheet):
                    # Obtener los colores del relleno seleccionado
                    relleno_info = relleno_config.get(selected_sheet, {})
                    type_colors = relleno_info.get("type_colors", {})
                    
                    # Obtener el color según el tipo de contenido
                    color = type_colors.get(row['type'], '')  # Si no hay color, se usa una cadena vacía
                    return [f'background-color: {color};'] * len(row)  # Aplicar el color de fondo a todas las celdas de la fila
                
                # Aplicar colores al DataFrame
                styled_playlist = playlist_df.style.apply(lambda row: apply_colors(row, selected_sheet), axis=1)
                
                # Mostrar el DataFrame con colores
                st.dataframe(
                    styled_playlist,
                    column_config={
                        "item": "Ítem",
                        "start_time": {"label": "Hora Inicio", "help": "Hora de inicio del bloque"},
                        "name": "Contenido",
                        "duration": "Duración",
                        "type": {"label": "Tipo", "help": "Tipo de contenido (Programa, Tanda, etc.)"},
                        "block": "Bloque"
                    },
                    use_container_width=True,
                    hide_index=True,
                    height=600  # Altura fija para la tabla
                )
            else:
                st.info("No hay playlist generada. Configura los parámetros y haz clic en 'Generar Playlist'.")

        # ------------------------------------------------------
        # Columna 3: Exportación y detalles adicionales
        # ------------------------------------------------------
        with col3:
            st.header("📤 Exportar Playlist")
            
            # Nombre de la hoja
            new_sheet_name = st.text_input(
                "📝 Nombre para la hoja:",
                value=st.session_state.sheet_title,
                help="Nombre que tendrá la hoja en Google Sheets"
            )
            st.session_state.sheet_title = new_sheet_name
            
            # Botones de exportación
            # Modo Completo
            if st.button("💾 Exportar a Google Sheets", use_container_width=True):
                if st.session_state.playlist:
                    export_to_google_sheets(st.session_state.playlist, st.session_state.sheet_title, selected_sheet)  # Agregar selected_sheet
                else:
                    st.session_state.messages.append({"type": "error", "content": "No hay playlist para exportar"})
            
            
            st.markdown("---")
            
            # Mensajes de notificación
            st.header("📢 Notificaciones")
            messages_container = st.container(height=200)
            with messages_container:
                for msg in st.session_state.messages[-3:]:  # Mostrar últimos 3 mensajes
                    if msg["type"] == "success":
                        st.success(msg["content"], icon="✅")
                    elif msg["type"] == "error":
                        st.error(msg["content"], icon="❌")
                    elif msg["type"] == "warning":
                        st.warning(msg["content"], icon="⚠️")

if __name__ == "__main__":
    main()
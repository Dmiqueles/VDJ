import streamlit as st
import gspread
from datetime import datetime, timedelta
from oauth2client.service_account import ServiceAccountCredentials
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
import random
import pandas as pd


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
def load_programs_from_google_sheet():
    client = authenticate_google_sheets()
    if not client:
        return []
    try:
        spreadsheet_id = '1Ka9YhP860lZlibXudUkr7an7zGs-spO54KBmidpNr1A'
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.sheet1
        data = worksheet.get_all_records()
        programs = [{'name': row['Name'], 'duration': row['Duration']} for row in data]
        st.session_state.messages.append({"type": "success", "content": "Programas cargados correctamente"})
        return programs
    except Exception as e:
        st.session_state.messages.append({"type": "error", "content": f"Error al cargar programas: {e}"})
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

# Función para exportar a Excel
def export_to_excel(playlist):
    try:
        wb = Workbook()
        ws = wb.active
        ws.title = "Playlist"
        headers = ['Item', 'Hora de Inicio', 'Nombre', 'Duración', 'Tipo']
        ws.append(headers)
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
        for col in ws.iter_cols(min_row=1, max_row=1, min_col=1, max_col=len(headers)):
            for cell in col:
                cell.font = header_font
                cell.fill = header_fill
        for i, block in enumerate(playlist, start=1):
            ws.append([block['item'], block['start_time'], block['name'], block['duration'], block['type']])
        for column in ws.columns:
            max_length = max(len(str(cell.value)) for cell in column)
            ws.column_dimensions[column[0].column_letter].width = max_length + 2
        filename = f"playlist_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"
        wb.save(filename)
        st.session_state.messages.append({"type": "success", "content": f"Playlist exportada correctamente a: {filename}"})
    except Exception as e:
        st.session_state.messages.append({"type": "error", "content": f"Error al exportar a Excel: {e}"})

# Función para exportar a Google Sheets con colores
def export_to_google_sheets(playlist, sheet_title):
    try:
        client = authenticate_google_sheets()
        if not client:
            return
        spreadsheet_id = '1SeKSZLR7IWrVVj9ny5hezcS-Nro06Amp9S29W6pMovU'  # Reemplaza con tu ID
        spreadsheet = client.open_by_key(spreadsheet_id)

        # Crear una nueva hoja dentro del Google Sheet
        worksheet = spreadsheet.add_worksheet(title=sheet_title, rows="100", cols="5")

        # Escribir los encabezados en la primera fila
        headers = ['Item', 'Hora de Inicio', 'Nombre', 'Duración', 'Tipo']
        worksheet.update(values=[headers], range_name='A1:E1')

        # Definir colores para cada tipo
        type_colors = {
            'Program': {'red': 1.0, 'green': 1.0, 'blue': 1.0},  # Blanco
            'Tanda': {'red': 0.0, 'green': 1.0, 'blue': 0.0},    # Verde
            'Promo': {'red': 0.27, 'green': 0.74, 'blue': 0.78}, # Turquesa (#46bdc6)
            'Filler': {'red': 0.5, 'green': 0.5, 'blue': 0.5},   # Gris
        }

        # Crear las filas de datos
        rows = []
        formats = []
        for i, block in enumerate(playlist, start=2):  # Comenzar desde la fila 2
            rows.append([
                block['item'],  # Número de ítem
                block['start_time'],
                block['name'],
                block['duration'],
                block['type']
            ])
            # Aplicar formato de color según el tipo
            row_range = f'A{i}:E{i}'
            formats.append({
                "range": row_range,
                "format": {
                    "backgroundColor": type_colors.get(block['type'], {'red': 1, 'green': 1, 'blue': 1}),
                    "textFormat": {"bold": block['type'] in ['Program', 'Tanda']}
                }
            })

        # Escribir las filas en una sola llamada
        worksheet.update(values=rows, range_name=f'A2:E{len(rows) + 1}')

        # Aplicar los formatos en un solo lote
        worksheet.batch_format(formats)

        # Aplicar formato a los encabezados
        worksheet.format('A1:E1', {
            'backgroundColor': {'red': 0.0, 'green': 0.5, 'blue': 0.8},  # Azul claro
            'textFormat': {'bold': True, 'foregroundColor': {'red': 1.0, 'green': 1.0, 'blue': 1.0}}  # Blanco
        })



        st.session_state.messages.append({"type": "success", "content": f"Playlist exportada correctamente a Google Sheets: {spreadsheet.url} -> {sheet_title}"})
    except Exception as e:
        st.session_state.messages.append({"type": "error", "content": f"Error al exportar a Google Sheets: {e}"})

def find_exact_combination(target_duration, content_list):
    # Filtrar contenido más largo que el tiempo disponible
    valid_content = [c for c in content_list if c['duration'] <= target_duration]
    
    # Usar programación dinámica para encontrar combinaciones exactas
    dp = {0: []}
    for content in sorted(valid_content, key=lambda x: -x['duration']):
        current_duration = content['duration']
        for s in list(dp.keys()):
            new_sum = s + current_duration
            if new_sum > target_duration:
                continue
            if new_sum not in dp or len(dp[new_sum]) > len(dp[s]) + 1:
                dp[new_sum] = dp[s] + [content]
            if new_sum == target_duration:
                return dp[new_sum]
    return dp.get(target_duration, None)

def generate_playlist(start_time, end_time, promos, fillers, user_programs):
    # Verificar si hay al menos 2 promos disponibles
    if len(promos) < 2:
        st.warning("⚠️ Advertencia: No hay suficientes promos disponibles. Se intentará compensar con rellenos.")
    
    current_time = start_time
    playlist = []
    block_counter = 0  # Iniciar con bloque 0
    user_program_index = 0
    item_counter = 1
    tanda_count = 0  # Contador de tandas por bloque
    max_tandas_per_block = 2  # Límite de tandas por bloque
    promo_count = 0  # Contador de promos en la playlist
    
    total_time = (end_time - start_time).total_seconds()
    elapsed_time = 0
    progress_bar = st.progress(0)
    status_text = st.empty()

    # 1. Añadir una tanda de 60 segundos como primer ítem (bloque 0)
    tanda_duration = 60
    playlist.append({
        "item": item_counter,
        "start_time": current_time.strftime("%H:%M:%S"),
        "name": "Tanda 60 segundos",
        "duration": str(timedelta(seconds=tanda_duration)),
        "type": "Tanda",
        "block": block_counter  # Bloque 0
    })
    item_counter += 1
    current_time += timedelta(seconds=tanda_duration)
    elapsed_time += tanda_duration
    tanda_count += 1
    progress_bar.progress(min(elapsed_time / total_time, 1.0))

    # 2. Incrementar el bloque después del primer ítem
    block_counter += 1

    # 3. Continuar con el resto de la lógica
    while current_time < end_time:
        # Añadir programa al inicio de cada bloque
        if user_program_index < len(user_programs):
            program = user_programs[user_program_index]
            program_duration = parse_duration(program["duration"])
            playlist.append({
                "item": item_counter,
                "start_time": current_time.strftime("%H:%M:%S"),
                "name": program["name"],
                "duration": program["duration"],
                "type": "Program",
                "block": block_counter
            })
            item_counter += 1
            current_time += timedelta(seconds=program_duration)
            elapsed_time += program_duration
            user_program_index += 1
            progress_bar.progress(min(elapsed_time / total_time, 1.0))

            # Añadir tanda de 60 segundos después de cada programa (si cabe y no se ha alcanzado el límite)
            if tanda_count < max_tandas_per_block and (end_time - current_time).total_seconds() >= tanda_duration:
                playlist.append({
                    "item": item_counter,
                    "start_time": current_time.strftime("%H:%M:%S"),
                    "name": "Tanda 60 segundos",
                    "duration": str(timedelta(seconds=tanda_duration)),
                    "type": "Tanda",
                    "block": block_counter
                })
                item_counter += 1
                current_time += timedelta(seconds=tanda_duration)
                elapsed_time += tanda_duration
                tanda_count += 1
                progress_bar.progress(min(elapsed_time / total_time, 1.0))
        else:
            break

        # Llenar el tiempo restante del bloque con promos/rellenos o tandas parciales
        next_block_time = calculate_time_to_next_block(current_time)
        time_until_next_block = (next_block_time - current_time).total_seconds()

        if time_until_next_block > 0:
            # Priorizar promos si no se han alcanzado las 2 promos mínimas
            if promo_count < 2 and promos:
                # Intentar usar promos primero
                selected_content = select_content(time_until_next_block, promos)
                if selected_content:
                    for content in selected_content:
                        playlist.append({
                            "item": item_counter,
                            "start_time": current_time.strftime("%H:%M:%S"),
                            "name": content['name'],
                            "duration": str(timedelta(seconds=content['duration'])),
                            "type": "Promo",
                            "block": block_counter
                        })
                        item_counter += 1
                        current_time += timedelta(seconds=content['duration'])
                        elapsed_time += content['duration']
                        promo_count += 1
                    remaining_time = time_until_next_block - sum(c['duration'] for c in selected_content)
                else:
                    remaining_time = time_until_next_block
            else:
                # Usar promos y rellenos
                available_content = promos + fillers
                selected_content = select_content(time_until_next_block, available_content)
                if selected_content:
                    for content in selected_content:
                        playlist.append({
                            "item": item_counter,
                            "start_time": current_time.strftime("%H:%M:%S"),
                            "name": content['name'],
                            "duration": str(timedelta(seconds=content['duration'])),
                            "type": "Promo" if content in promos else "Filler",
                            "block": block_counter
                        })
                        item_counter += 1
                        current_time += timedelta(seconds=content['duration'])
                        elapsed_time += content['duration']
                        if content in promos:
                            promo_count += 1
                    remaining_time = time_until_next_block - sum(c['duration'] for c in selected_content)
                else:
                    remaining_time = time_until_next_block

            # Si todavía queda tiempo, usar tanda parcial (última opción)
            if remaining_time > 0:
                tanda_duration = min(30, remaining_time)  # Máximo 30 segundos
                playlist.append({
                    "item": item_counter,
                    "start_time": current_time.strftime("%H:%M:%S"),
                    "name": f"Tanda Parcial de {tanda_duration}s",
                    "duration": str(timedelta(seconds=tanda_duration)),
                    "type": "Tanda",
                    "block": block_counter
                })
                item_counter += 1
                current_time += timedelta(seconds=tanda_duration)
                elapsed_time += tanda_duration

        # Reiniciar el contador de tandas al final de cada bloque
        tanda_count = 0
        block_counter += 1

    # Verificar si se alcanzó el mínimo de 2 promos
    if promo_count < 2:
        st.warning("⚠️ Advertencia: No se pudieron incluir al menos 2 promos en la playlist.")

    progress_bar.progress(1.0)
    status_text.text("Playlist generada exitosamente 🎉")
    return playlist

# Función para convertir duración en formato HH:MM:SS a segundos
def parse_duration(duration_str):
    h, m, s = map(int, duration_str.split(':'))
    return h * 3600 + m * 60 + s

# Función para calcular el tiempo hasta el siguiente bloque
def calculate_time_to_next_block(current_time):
    valid_start_minutes = [0, 10, 15, 20, 30, 40, 45, 50]
    current_hour, current_minute = current_time.hour, current_time.minute
    next_valid_minutes = [m for m in valid_start_minutes if m > current_minute]
    
    if next_valid_minutes:
        next_minute = next_valid_minutes[0]
    else:
        next_minute = valid_start_minutes[0]
        current_hour += 1  # Pasamos a la siguiente hora si no hay minutos válidos en la actual
    
    next_block_time = current_time.replace(hour=current_hour % 24, minute=next_minute, second=0, microsecond=0)
    return next_block_time


# Función para seleccionar contenido
def select_content(duration_seconds, content_list):
    selected = []
    remaining_seconds = duration_seconds
    
    sorted_content = sorted(content_list, key=lambda x: x['duration'], reverse=True)
    
    for content in sorted_content:
        if content['duration'] <= remaining_seconds:
            selected.append(content)
            remaining_seconds -= content['duration']
        if remaining_seconds <= 0:
            break
    
    return selected

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
        if st.button("✨ Generar Playlist", type="primary", use_container_width=True):
            # Cargar datos antes de generar la playlist
            with st.spinner("🔍 Cargando programas, promos y rellenos..."):
                promos = load_promos_from_google_sheet()
                user_programs = load_programs_from_google_sheet()
                fillers = load_fillers_from_google_sheet(selected_sheet) if sheets else []

                # Verificar si hay datos suficientes
                if not user_programs or not promos or not fillers:
                    st.session_state.messages.append({"type": "warning", "content": "Faltan datos para generar la playlist"})
                else:
                    # Usar horarios predeterminados en modo simple
                    start_time = datetime.strptime("05:59:00", "%H:%M:%S").time()
                    end_time = datetime.strptime("23:59:00", "%H:%M:%S").time()
                    start_time_dt = datetime.combine(datetime.today(), start_time)
                    end_time_dt = datetime.combine(datetime.today(), end_time)

                    # Generar playlist
                    playlist = generate_playlist(start_time_dt, end_time_dt, promos, fillers, user_programs)
                    st.session_state.playlist = playlist
                    st.session_state.messages.append({"type": "success", "content": "Playlist generada correctamente"})

                    # Exportar automáticamente a Google Sheets
                    export_to_google_sheets(st.session_state.playlist, st.session_state.sheet_title)
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
            start_time = st.time_input("Hora de inicio", value=datetime.strptime("05:59:00", "%H:%M:%S").time())
            end_time = st.time_input("Hora de fin", value=datetime.strptime("23:59:00", "%H:%M:%S").time())
            
            st.markdown("---")
            
            # Botón para generar la playlist
            if st.button("✨ Generar Playlist", type="primary", use_container_width=True):
                # Cargar datos antes de generar la playlist
                with st.spinner("🔍 Cargando programas, promos y rellenos..."):
                    promos = load_promos_from_google_sheet()
                    user_programs = load_programs_from_google_sheet()
                    fillers = load_fillers_from_google_sheet(selected_sheet) if sheets else []

                    # Verificar si hay datos suficientes
                    if not user_programs or not promos or not fillers:
                        st.session_state.messages.append({"type": "warning", "content": "Faltan datos para generar la playlist"})
                    else:
                        start_time_dt = datetime.combine(datetime.today(), start_time)
                        end_time_dt = datetime.combine(datetime.today(), end_time)
                        playlist = generate_playlist(start_time_dt, end_time_dt, promos, fillers, user_programs)
                        st.session_state.playlist = playlist
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
                    'Promo': 'background-color: #46bdc6; color: #000000;',    # Turquesa
                    'Filler': 'background-color: #808080; color: #FFFFFF;',   # Gris
                }
                
                # Función para aplicar colores
                def apply_colors(row):
                    color = type_colors.get(row['type'], '')  # Obtener el color según el tipo
                    return [color] * len(row)  # Aplicar el color a todas las celdas de la fila
                
                # Aplicar colores al DataFrame
                styled_playlist = playlist_df.style.apply(apply_colors, axis=1)
                
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
            if st.button("💾 Exportar a Google Sheets", use_container_width=True):
                if st.session_state.playlist:
                    export_to_google_sheets(st.session_state.playlist, st.session_state.sheet_title)
                else:
                    st.session_state.messages.append({"type": "error", "content": "No hay playlist para exportar"})
            
            if st.button("📥 Exportar a Excel", use_container_width=True):
                if st.session_state.playlist:
                    export_to_excel(st.session_state.playlist)
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
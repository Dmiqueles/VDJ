import streamlit as st
import gspread
import logging
import os
import json
from datetime import datetime, date, timedelta, time
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import random
from itertools import combinations
from functools import lru_cache

# ----------------------------------------------
# Configuración de logging
# ----------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("playlist_generator")

# ----------------------------------------------
# Configuración centralizada
# ----------------------------------------------
CONFIG = {
    "sheet_ids": {
        "programs": "1Ka9YhP860lZlibXudUkr7an7zGs-spO54KBmidpNr1A",
        "promos": "17AtkM82WEWczbzLvHSq-XYQbiAImTNkmSguDlDg_46g",
        "fillers": "1MjcPISQEPUvYAHqVtW7nvweqfXhaS_cAbREjeG3uK-I",
        "export": "1SeKSZLR7IWrVVj9ny5hezcS-Nro06Amp9S29W6pMovU"
    },
    "default_times": {
        "day_start": "05:59:00",
        "day_end": "21:00:00",
        "night_start": "21:00:00",
        "night_end": "06:00:00"
    },
    "block_intervals": {
        "default": 15,
        "min": 15,
        "max": 60
    },
    "tanda_duration": 60,  # segundos
    "valid_minutes": [0, 15, 30, 45],  # Cambiado para incluir minuto 00
    "type_colors": {
        "Program": {"red": 1.0, "green": 1.0, "blue": 1.0},  # Blanco
        "Tanda": {"red": 0.0, "green": 1.0, "blue": 0.0},    # Verde
        "Promo": {"red": 0.27, "green": 0.74, "blue": 0.78}, # Turquesa (#46bdc6)
        "Filler": {"red": 0.5, "green": 0.5, "blue": 0.5},   # Gris
        "Tanda Parcial": {"red": 1.0, "green": 1.0, "blue": 0.0},  # Amarillo (#FFFF00)
    },
    "header_color": {"red": 0.0, "green": 0.5, "blue": 0.8}  # Azul claro
}

# ----------------------------------------------
# Configuración inicial de la página
# ----------------------------------------------
def setup_page():
    """Configura la página inicial de Streamlit."""
    st.set_page_config(
        page_title="Generador de Playlists",
        page_icon="🎧",
        layout="wide",
        initial_sidebar_state="expanded"
    )

# ----------------------------------------------
# Clase para manejo de mensajes
# ----------------------------------------------
class MessageManager:
    """Clase para gestionar mensajes y notificaciones de la aplicación."""
    
    @staticmethod
    def initialize():
        """Inicializa el sistema de mensajes en la sesión."""
        if 'messages' not in st.session_state:
            st.session_state.messages = []
    
    @staticmethod
    def add_message(msg_type, content):
        """
        Añade un mensaje al sistema.
        
        Args:
            msg_type (str): Tipo de mensaje ('success', 'error', 'warning', 'info')
            content (str): Contenido del mensaje
        """
        if 'messages' not in st.session_state:
            MessageManager.initialize()
        
        st.session_state.messages.append({"type": msg_type, "content": content})
        
        # También registrar en el log
        if msg_type == "error":
            logger.error(content)
        elif msg_type == "warning":
            logger.warning(content)
        else:
            logger.info(content)
    
    @staticmethod
    def display_messages(limit=3):
        """
        Muestra los mensajes más recientes en la interfaz.
        
        Args:
            limit (int): Número de mensajes a mostrar
        """
        if 'messages' not in st.session_state:
            return
            
        for msg in st.session_state.messages[-limit:]:
            if msg["type"] == "success":
                st.success(msg["content"], icon="✅")
            elif msg["type"] == "error":
                st.error(msg["content"], icon="❌")
            elif msg["type"] == "warning":
                st.warning(msg["content"], icon="⚠️")
            elif msg["type"] == "info":
                st.info(msg["content"], icon="ℹ️")

# ----------------------------------------------
# Funciones de autenticación
# ----------------------------------------------
def authenticate_google_sheets():
    """
    Autentica con Google Sheets API.
    
    Returns:
        gspread.Client: Cliente autenticado o None si falla la autenticación
    
    Raises:
        KeyError: Si faltan credenciales en st.secrets
        ConnectionError: Si hay problemas de conexión con Google API
    """
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # Obtener credenciales desde st.secrets
        credentials_dict = st.secrets["google_sheets"]
        
        # Crear credenciales desde el diccionario
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
        client = gspread.authorize(credentials)
        
        return client
    except KeyError as e:
        error_msg = f"Error de configuración: Falta la clave '{e}' en st.secrets"
        MessageManager.add_message("error", error_msg)
        return None
    except ConnectionError as e:
        error_msg = f"Error de conexión con Google API: {e}. Verifique su conexión a internet."
        MessageManager.add_message("error", error_msg)
        return None
    except Exception as e:
        error_msg = f"Error inesperado al autenticar: {e}"
        MessageManager.add_message("error", error_msg)
        logger.exception("Excepción durante la autenticación")
        return None

# ----------------------------------------------
# Funciones de carga de datos
# ----------------------------------------------
@lru_cache(maxsize=8)
def load_data_from_sheet(sheet_id, sheet_name=None, process_func=None):
    """
    Función genérica para cargar datos desde una hoja de Google Sheets.
    
    Args:
        sheet_id (str): ID de la hoja de cálculo
        sheet_name (str, optional): Nombre de la hoja específica
        process_func (callable, optional): Función para procesar los datos
    
    Returns:
        list: Lista de datos procesados o vacía si hay error
    """
    client = authenticate_google_sheets()
    if not client:
        return []
    
    try:
        spreadsheet = client.open_by_key(sheet_id)
        worksheet = sheet_name and spreadsheet.worksheet(sheet_name) or spreadsheet.sheet1
        data = worksheet.get_all_records()
        
        if process_func:
            return process_func(data)
        return data
    except gspread.exceptions.SpreadsheetNotFound:
        error_msg = f"No se encontró la hoja de cálculo con ID: {sheet_id}"
        MessageManager.add_message("error", error_msg)
        return []
    except gspread.exceptions.WorksheetNotFound:
        error_msg = f"No se encontró la hoja '{sheet_name}' en la hoja de cálculo"
        MessageManager.add_message("error", error_msg)
        return []
    except gspread.exceptions.APIError as e:
        error_msg = f"Error de API de Google Sheets: {e}"
        MessageManager.add_message("error", error_msg)
        return []
    except Exception as e:
        error_msg = f"Error al cargar datos: {e}"
        MessageManager.add_message("error", error_msg)
        logger.exception("Excepción durante la carga de datos")
        return []

def process_program_data(data):
    """
    Procesa los datos de programas desde la hoja de cálculo.
    
    Args:
        data (list): Datos crudos de la hoja
    
    Returns:
        list: Lista de programas procesados
    """
    programs = []
    for row in data:
        try:
            # Validar que existan las claves necesarias
            if 'Name' not in row or 'Duration' not in row:
                raise ValueError(f"Faltan campos obligatorios en la fila: {row}")
                
            # Convertir duración HH:MM:SS a segundos
            duration_seconds = parse_duration(row['Duration'])
            
            programs.append({
                'name': row['Name'], 
                'duration_seconds': duration_seconds,
                'duration_formatted': format_duration(duration_seconds),  # Duración formateada para mostrar
                'manual_start_time': None  # Campo para almacenar la hora de inicio manual
            })
            
        except ValueError as e:
            error_msg = f"Duración inválida en programa {row.get('Name', 'Desconocido')}: {row.get('Duration', 'Sin duración')} - {str(e)}"
            MessageManager.add_message("error", error_msg)
    
    if programs:
        MessageManager.add_message("success", f"Programas cargados: {len(programs)}")
        
    return programs

def process_promo_data(data):
    """
    Procesa los datos de promos desde la hoja de cálculo.
    
    Args:
        data (list): Datos crudos de la hoja
    
    Returns:
        list: Lista de promos procesadas
    """
    promos = []
    for row in data:
        try:
            # Validar que existan las claves necesarias
            if 'Name' not in row or 'Duration' not in row:
                raise ValueError(f"Faltan campos obligatorios en la fila: {row}")
                
            # Convertir duración HH:MM:SS a segundos
            duration_seconds = parse_duration(row['Duration'])
            
            promos.append({
                'name': row['Name'], 
                'duration_seconds': duration_seconds,
                'type': 'Promo'
            })
            
        except ValueError as e:
            error_msg = f"Error al procesar la duración de la promo '{row.get('Name', 'Desconocida')}'. Formato inválido: {row.get('Duration', 'Sin duración')} - {str(e)}"
            MessageManager.add_message("error", error_msg)
    
    if promos:
        MessageManager.add_message("success", f"Promos cargadas: {len(promos)}")
        
    return promos

def process_filler_data(data):
    """
    Procesa los datos de rellenos desde la hoja de cálculo.
    
    Args:
        data (list): Datos crudos de la hoja
    
    Returns:
        list: Lista de rellenos procesados
    """
    fillers = []
    for row in data:
        try:
            # Validar que existan las claves necesarias
            if 'Name' not in row or 'Duration' not in row:
                raise ValueError(f"Faltan campos obligatorios en la fila: {row}")
                
            # Convertir duración HH:MM:SS a segundos
            duration_seconds = parse_duration(row['Duration'])
            
            fillers.append({
                'name': row['Name'], 
                'duration_seconds': duration_seconds,
                'type': 'Filler'
            })
            
        except ValueError as e:
            error_msg = f"Error al procesar la duración del relleno '{row.get('Name', 'Desconocido')}'. Formato inválido: {row.get('Duration', 'Sin duración')} - {str(e)}"
            MessageManager.add_message("error", error_msg)
    
    if fillers:
        MessageManager.add_message("success", f"Rellenos cargados: {len(fillers)}")
        
    return fillers

def load_programs_from_google_sheet(sheet_name):
    """
    Carga programas desde Google Sheets.
    
    Args:
        sheet_name (str): Nombre de la hoja
    
    Returns:
        list: Lista de programas
    """
    return load_data_from_sheet(
        CONFIG["sheet_ids"]["programs"], 
        sheet_name, 
        process_program_data
    )

def load_promos_from_google_sheet():
    """
    Carga promos desde Google Sheets.
    
    Returns:
        list: Lista de promos
    """
    return load_data_from_sheet(
        CONFIG["sheet_ids"]["promos"], 
        None, 
        process_promo_data
    )

def load_fillers_from_google_sheet(sheet_name):
    """
    Carga rellenos desde Google Sheets.
    
    Args:
        sheet_name (str): Nombre de la hoja
    
    Returns:
        list: Lista de rellenos
    """
    return load_data_from_sheet(
        CONFIG["sheet_ids"]["fillers"], 
        sheet_name, 
        process_filler_data
    )

def list_sheets():
    """
    Lista todas las hojas disponibles en la hoja de cálculo de rellenos.
    
    Returns:
        list: Lista de nombres de hojas
    """
    client = authenticate_google_sheets()
    if not client:
        return []
    
    try:
        spreadsheet_id = CONFIG["sheet_ids"]["fillers"]
        spreadsheet = client.open_by_key(spreadsheet_id)
        sheets = [sheet.title for sheet in spreadsheet.worksheets()]
        return sheets
    except gspread.exceptions.SpreadsheetNotFound:
        error_msg = f"No se encontró la hoja de cálculo de rellenos"
        MessageManager.add_message("error", error_msg)
        return []
    except Exception as e:
        error_msg = f"Error al listar las hojas: {e}"
        MessageManager.add_message("error", error_msg)
        logger.exception("Excepción al listar hojas")
        return []

# ----------------------------------------------
# Funciones auxiliares
# ----------------------------------------------
def format_duration(seconds):
    """
    Formatea una duración en segundos a formato HH:MM:SS.
    
    Args:
        seconds (int): Duración en segundos
    
    Returns:
        str: Duración formateada
    """
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return "00:00:00"
    
    hours = int(seconds // 3600)
    minutes = int((seconds // 60) % 60)
    secs = int(seconds % 60)
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def parse_duration(duration_str):
    """
    Convierte una duración en formato HH:MM:SS a segundos.
    
    Args:
        duration_str (str): Duración en formato HH:MM:SS
    
    Returns:
        int: Duración en segundos
    
    Raises:
        ValueError: Si el formato es inválido
    """
    if isinstance(duration_str, (int, float)):  # Si ya es un número, lo devolvemos directamente
        return int(duration_str)
    
    try:
        parts = list(map(int, duration_str.split(':')))  # Convertir a lista de enteros
        
        if len(parts) == 2:  # Formato MM:SS
            return parts[0] * 60 + parts[1]
        elif len(parts) == 3:  # Formato HH:MM:SS
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        else:
            raise ValueError(f"Formato de duración inválido: {duration_str}. Debe ser HH:MM:SS o MM:SS")
    except Exception as e:
        raise ValueError(f"Error al parsear la duración: {e}")

def calculate_next_interval(current_time):
    """
    Calcula el siguiente intervalo válido.
    
    Args:
        current_time (datetime): Tiempo actual
    
    Returns:
        datetime: Siguiente intervalo válido
    """
    valid_minutes = CONFIG["valid_minutes"]
    current_minute = current_time.minute

    # Encontrar el siguiente minuto válido
    next_minute = next((m for m in valid_minutes if m > current_minute), valid_minutes[0])
    
    # Si el siguiente minuto válido es menor o igual al actual, avanzar una hora
    if next_minute <= current_minute:
        current_time += timedelta(hours=1)

    return current_time.replace(minute=next_minute, second=0, microsecond=0)

def calculate_end_time(start_time_str, duration_seconds):
    """
    Calcula la hora de fin basada en la hora de inicio y la duración.
    
    Args:
        start_time_str (str): Hora de inicio en formato HH:MM:SS
        duration_seconds (int): Duración en segundos
    
    Returns:
        str: Hora de fin en formato HH:MM:SS
    """
    start_time = datetime.strptime(start_time_str, "%H:%M:%S")
    end_time = start_time + timedelta(seconds=duration_seconds)
    return end_time.strftime("%H:%M:%S")

def is_time_in_range(time_str, start_time, end_time, is_night_range=False):
    """
    Verifica si una hora está dentro de un rango específico.
    
    Args:
        time_str (str): Hora a verificar en formato HH:MM:SS
        start_time (time): Hora de inicio del rango
        end_time (time): Hora de fin del rango
        is_night_range (bool): Si el rango es nocturno (cruza a un nuevo día)
    
    Returns:
        bool: True si la hora está dentro del rango, False en caso contrario
    """
    check_time = datetime.strptime(time_str, "%H:%M:%S").time()
    
    if is_night_range:
        # Para rangos nocturnos (ej. 21:00 - 06:00)
        if start_time <= end_time:
            return start_time <= check_time <= end_time
        else:
            return check_time >= start_time or check_time <= end_time
    else:
        # Para rangos diurnos (ej. 06:00 - 21:00)
        return start_time <= check_time <= end_time

def validate_schedules(day_programs, night_programs, day_start_time, night_start_time=None):
    """Valida todos los horarios manuales para detectar solapamientos, considerando cruce de días."""
    all_slots = []
    today = date.today()
    
    # Procesar programas diurnos
    for prog in day_programs:
        if not prog.get('manual_start_time'):
            continue
            
        start_time = datetime.strptime(prog['manual_start_time'], "%H:%M:%S").time()
        start_dt = datetime.combine(today, start_time)
        
        # Si el programa comienza antes del inicio del horario diurno, asumir que es del día siguiente
        if start_time < day_start_time:
            start_dt += timedelta(days=1)
            
        end_dt = start_dt + timedelta(seconds=prog['duration_seconds'])
        all_slots.append({
            'name': prog['name'],
            'start': start_dt,
            'end': end_dt,
            'type': 'day'
        })
    
    # Procesar programas nocturnos
    if night_start_time:
        for prog in night_programs:
            if not prog.get('manual_start_time'):
                continue
                
            start_time = datetime.strptime(prog['manual_start_time'], "%H:%M:%S").time()
            start_dt = datetime.combine(today, start_time)
            
            # Ajustar para horario nocturno (si el programa comienza antes del inicio nocturno, es del día siguiente)
            if start_time < night_start_time:
                start_dt += timedelta(days=1)
                
            end_dt = start_dt + timedelta(seconds=prog['duration_seconds'])
            all_slots.append({
                'name': prog['name'],
                'start': start_dt,
                'end': end_dt,
                'type': 'night'
            })
    
    # Verificar solapamientos considerando el cruce de días
    overlaps = []
    for i in range(len(all_slots)):
        for j in range(i+1, len(all_slots)):
            slot1 = all_slots[i]
            slot2 = all_slots[j]
            
            # Verificar si los intervalos se solapan
            if slot1['start'] < slot2['end'] and slot2['start'] < slot1['end']:
                overlaps.append((
                    f"{slot1['name']} ({slot1['type']})",
                    f"{slot2['name']} ({slot2['type']})"
                ))
    
    return (len(overlaps) == 0, overlaps)

# ----------------------------------------------
# Clase PlaylistGenerator
# ----------------------------------------------
class PlaylistGenerator:
    """Clase para generar playlists."""
    
    def __init__(self, start_time, promos=None, fillers=None, user_programs=None, 
                include_block_zero=True, is_night_schedule=False, reference_date=None,
                force_start_datetime=None, use_manual_times=False,
                duration_hours=None, end_time=None):
        """
        Inicializa el generador de playlists con soporte para 24+ horas.
        
        Args:
            start_time (time): Hora de inicio local (ej. time(6,0))
            promos (list): Lista de promos disponibles
            fillers (list): Lista de fillers disponibles
            user_programs (list): Lista de programas a programar
            include_block_zero (bool): Si incluir bloque inicial de tanda
            is_night_schedule (bool): Si es horario nocturno (legacy)
            reference_date (date): Fecha de referencia para la playlist
            force_start_datetime (datetime): Fuerza un datetime específico
            use_manual_times (bool): Usar horarios manuales de los programas
            duration_hours (int): Duración total en horas (alternativa a end_time)
            end_time (time): Hora de finalización local (alternativa a duration_hours)
            
        Nota:
            - Usar duration_hours O end_time, no ambos
            - Si se usa force_start_datetime, ignora reference_date
        """
        # Inicializar listas si no se proporcionan
        self.promos = promos or []
        self.fillers = fillers or []
        self.user_programs = user_programs.copy() if user_programs else []
        
        # Configuración de comportamiento
        self.include_block_zero = include_block_zero
        self.is_night_schedule = is_night_schedule
        self.use_manual_times = use_manual_times
        
        # Manejo de fechas y tiempos
        self.reference_date = reference_date or date.today()
        
        # Configuración de tiempo de ejecución
        if force_start_datetime:
            # Modo forzado (toma precedencia sobre todo)
            self.start_datetime = force_start_datetime
            if duration_hours:
                self.end_datetime = self.start_datetime + timedelta(hours=duration_hours)
            elif end_time:
                end_date = self.start_datetime.date()
                if end_time < self.start_datetime.time():
                    end_date += timedelta(days=1)
                self.end_datetime = datetime.combine(end_date, end_time)
            else:
                raise ValueError("Se requiere duration_hours o end_time con force_start_datetime")
        else:
            # Modo normal (usa reference_date + start_time)
            self.start_datetime = datetime.combine(self.reference_date, start_time)
            
            if duration_hours:
                # Modo duración fija (24+ horas)
                self.end_datetime = self.start_datetime + timedelta(hours=duration_hours)
            elif end_time:
                # Modo horario específico (compatibilidad hacia atrás)
                end_date = self.reference_date
                if end_time < start_time:
                    end_date += timedelta(days=1)
                self.end_datetime = datetime.combine(end_date, end_time)
            else:
                raise ValueError("Se requiere duration_hours o end_time")
        
        # Validación de parámetros
        if self.end_datetime <= self.start_datetime:
            raise ValueError("El tiempo final debe ser después del tiempo inicial")
        
        # Variables de estado interno
        self.current_time = self.start_datetime
        self.playlist = []
        self.item_counter = 1
        self.initial_blocks = []
        
        # Logging informativo
        logger.info(f"PlaylistGenerator inicializado:")
        logger.info(f" - Inicio: {self.start_datetime}")
        logger.info(f" - Fin:    {self.end_datetime}")
        logger.info(f" - Duración total: {(self.end_datetime - self.start_datetime).total_seconds()/3600:.2f} horas")
        logger.info(f" - Programas: {len(self.user_programs)}")
        logger.info(f" - Promos: {len(self.promos)}, Fillers: {len(self.fillers)}")
        logger.info(f" - Modo: {'Manual' if use_manual_times else 'Automático'}")
        
    def generate(self):
        """
        Genera la playlist completa.
        
        Returns:
            list: Playlist generada
        """
        # Si estamos usando horarios manuales, generar la playlist basada en esos horarios
        if self.use_manual_times:
            return self._generate_with_manual_times()
        
        # Generar bloque 0 si es necesario
        if self.include_block_zero:
            self._add_block_zero()
        
        # Generar bloques iniciales
        self._generate_initial_blocks()
        
        # Repetición cíclica de bloques
        self._repeat_blocks_until_end()
        
        # Bloque especial final
        self._add_final_block()
        
        # Ordenar la playlist por el campo 'item'
        self.playlist.sort(key=lambda x: x['item'])
        
        return self.playlist
    
    def _generate_with_manual_times(self):
        """Genera playlist usando horarios manuales con manejo mejorado de horarios nocturnos."""
        # Filtrar programas con horario asignado
        valid_programs = [p.copy() for p in self.user_programs if p.get('manual_start_time')]
        
        if not valid_programs:
            MessageManager.add_message("warning", "No hay programas con horarios asignados manualmente")
            return []
        
        # Convertir a objetos datetime y ajustar fechas para horario nocturno
        for prog in valid_programs:
            start_time = datetime.strptime(prog['manual_start_time'], "%H:%M:%S").time()
            start_dt = datetime.combine(self.reference_date, start_time)
            
            # Ajustar fecha si es horario nocturno y cruza medianoche
            if self.is_night_schedule and start_time < self.start_time:
                start_dt += timedelta(days=1)
            
            prog['_start_datetime'] = start_dt
            prog['_end_datetime'] = start_dt + timedelta(seconds=prog['duration_seconds'])
        
        # Ordenar por datetime de inicio
        valid_programs.sort(key=lambda x: x['_start_datetime'])
        
        playlist = []
        block_counter = 1
        
        for i, program in enumerate(valid_programs):
            # Añadir programa
            playlist.append({
                "item": self.item_counter,
                "start_time": program['_start_datetime'].strftime("%H:%M:%S"),
                "name": program['name'],
                "duration": format_duration(program['duration_seconds']),
                "duration_seconds": program['duration_seconds'],
                "type": "Program",
                "block": block_counter,
                "is_copied": False,
                "schedule_type": "night" if self.is_night_schedule else "day"
            })
            self.item_counter += 1
            
            # Añadir tanda después del programa
            tanda_start = program['_end_datetime']
            playlist.append({
                "item": self.item_counter,
                "start_time": tanda_start.strftime("%H:%M:%S"),
                "name": "Tanda 60s",
                "duration": format_duration(CONFIG["tanda_duration"]),
                "duration_seconds": CONFIG["tanda_duration"],
                "type": "Tanda",
                "block": block_counter,
                "is_copied": False,
                "schedule_type": "night" if self.is_night_schedule else "day"
            })
            self.item_counter += 1
            tanda_end = tanda_start + timedelta(seconds=CONFIG["tanda_duration"])
            
            # Manejar espacio hasta el siguiente programa
            if i < len(valid_programs) - 1:
                next_program_start = valid_programs[i+1]['_start_datetime']
                time_available = (next_program_start - tanda_end).total_seconds()
                
                if time_available > 0:
                    content_manager = ContentManager(self.promos, self.fillers)
                    fillers = content_manager.find_optimal_combination(time_available)
                    
                    current_time = tanda_end
                    for item in fillers:
                        playlist.append({
                            "item": self.item_counter,
                            "start_time": current_time.strftime("%H:%M:%S"),
                            "name": item['name'],
                            "duration": format_duration(item['duration_seconds']),
                            "duration_seconds": item['duration_seconds'],
                            "type": item['type'],
                            "block": block_counter,
                            "is_copied": False,
                            "schedule_type": "night" if self.is_night_schedule else "day"
                        })
                        self.item_counter += 1
                        current_time += timedelta(seconds=item['duration_seconds'])
            
            block_counter += 1
        
        return playlist
    

    def _add_block_zero(self):
        """Añade el bloque 0 (tanda inicial) a la playlist."""
        self.playlist.append({
            "item": self.item_counter,
            "start_time": self.current_time.strftime("%H:%M:%S"),
            "name": "Tanda 60s (Bloque 0)",
            "duration": format_duration(CONFIG["tanda_duration"]),
            "duration_seconds": CONFIG["tanda_duration"],
            "type": "Tanda",
            "block": 0,
            "is_copied": False,
            "schedule_type": "night" if self.is_night_schedule else "day"
        })
        self.item_counter += 1
        self.current_time += timedelta(seconds=CONFIG["tanda_duration"])
    
    def _generate_initial_blocks(self):
        """Genera los bloques iniciales con programas, tandas y rellenos."""
        while self.user_programs:
            block = []
            
            # Programa principal (siempre el primer elemento del bloque)
            self._add_program_to_block(block)
            
            # Tanda obligatoria (siempre el segundo elemento del bloque)
            self._add_tanda_to_block(block)
            
            # Calcular tiempo restante hasta el próximo múltiplo de 15 minutos
            next_15_minute_mark = self._calculate_next_15_minute_mark()
            remaining_time_to_next_15 = (next_15_minute_mark - self.current_time).total_seconds()
            
            # Rellenar el tiempo restante con promos y rellenos
            if remaining_time_to_next_15 > 0:
                self._fill_remaining_time(block, remaining_time_to_next_15)
            
            # Agregar bloque a la lista de bloques iniciales
            self.initial_blocks.append(block)
            
            # Agregar bloque a la playlist
            self.playlist.extend(block)
    
    def _add_program_to_block(self, block):
        """
        Añade un programa al bloque actual.
        
        Args:
            block (list): Bloque actual
        """
        program = self.user_programs.pop(0)
        program_duration = program['duration_seconds']
        
        block.append({
            "item": self.item_counter,
            "start_time": self.current_time.strftime("%H:%M:%S"),
            "name": program['name'],
            "duration": format_duration(program_duration),
            "duration_seconds": program_duration,
            "type": "Program",
            "block": len(self.initial_blocks) + 1,
            "is_copied": False,
            "schedule_type": "night" if self.is_night_schedule else "day"
        })
        
        self.item_counter += 1
        self.current_time += timedelta(seconds=program_duration)
    
    def _add_tanda_to_block(self, block):
        """
        Añade una tanda publicitaria al bloque actual.
        
        Args:
            block (list): Bloque actual
        """
        block.append({
            "item": self.item_counter,
            "start_time": self.current_time.strftime("%H:%M:%S"),
            "name": "Tanda 60s",
            "duration": format_duration(CONFIG["tanda_duration"]),
            "duration_seconds": CONFIG["tanda_duration"],
            "type": "Tanda",
            "block": len(self.initial_blocks) + 1,
            "is_copied": False,
            "schedule_type": "night" if self.is_night_schedule else "day"
        })
        
        self.item_counter += 1
        self.current_time += timedelta(seconds=CONFIG["tanda_duration"])
    
    def _calculate_next_15_minute_mark(self):
        """
        Calcula el próximo múltiplo de 15 minutos.
        
        Returns:
            datetime: Próximo múltiplo de 15 minutos
        """
        next_15_minute_mark = self.current_time + timedelta(minutes=(15 - self.current_time.minute % 15))
        return next_15_minute_mark.replace(second=0, microsecond=0)
    
    def _fill_remaining_time(self, block, time_remaining):
        """
        Rellena el tiempo restante con promos y fillers de manera obligatoria.
        """
        content_manager = ContentManager(self.promos, self.fillers)
        optimal_combination = content_manager.find_optimal_combination(time_remaining)
        
        if optimal_combination:
            for item in optimal_combination:
                block.append({
                    "item": self.item_counter,
                    "start_time": self.current_time.strftime("%H:%M:%S"),
                    "name": item['name'],
                    "duration": format_duration(item['duration_seconds']),
                    "duration_seconds": item['duration_seconds'],
                    "type": item['type'],
                    "block": len(self.initial_blocks) + 1,
                    "is_copied": False,
                    "schedule_type": "night" if self.is_night_schedule else "day"
                })
                
                self.item_counter += 1
                self.current_time += timedelta(seconds=item['duration_seconds'])
        else:
            self.current_time = self._advance_to_next_valid_interval()

    def _advance_to_next_valid_interval(self):
        """Avanza al siguiente intervalo válido si no se puede llenar el tiempo."""
        next_interval = self.current_time + timedelta(minutes=15 - self.current_time.minute % 15)
        return next_interval.replace(second=0, microsecond=0)
    
    def _repeat_blocks_until_end(self):
        """Repite los bloques iniciales hasta completar el horario."""
        block_index = 0
        last_block_items = set()  # Mantener un registro de los nombres de promos y fillers del último bloque
        
        while self.current_time < self.end_datetime:
            current_block = self.initial_blocks[block_index % len(self.initial_blocks)]
            block_duration = sum(item['duration_seconds'] for item in current_block)
            
            # Verificar si el siguiente bloque completo cabe en el tiempo restante
            if self.current_time + timedelta(seconds=block_duration) > self.end_datetime:
                break
            
            # Procesar el bloque actual
            self._process_repeated_block(current_block, last_block_items, block_index)
            
            block_index += 1
    
    def _process_repeated_block(self, current_block, last_block_items, block_index):
        """
        Procesa un bloque repetido, evitando repetir promos y fillers.
        
        Args:
            current_block (list): Bloque actual
            last_block_items (set): Conjunto de nombres de items del último bloque
            block_index (int): Índice del bloque actual
        """
        new_block_items = set()  # Mantener un registro de los nombres de promos y fillers del bloque actual
        block_has_promo = False  # Verificar si el bloque tiene al menos un promo
        block_has_filler = False  # Verificar si el bloque tiene al menos un filler
        
        # Procesar cada item del bloque
        for item in current_block:
            # Evitar repetir promos y fillers del último bloque
            if item['type'] in ['Promo', 'Filler'] and item['name'] in last_block_items:
                continue
            
            # Crear copia del item y añadirlo a la playlist
            self._add_copied_item_to_playlist(item, block_index)
            
            # Registrar el item en el bloque actual
            if item['type'] in ['Promo', 'Filler']:
                new_block_items.add(item['name'])
            if item['type'] == 'Promo':
                block_has_promo = True
            if item['type'] == 'Filler':
                block_has_filler = True
        
        # Asegurar que el bloque tiene al menos un promo y un filler
        if not block_has_promo:
            self._add_promo_to_block(new_block_items, last_block_items, block_index)
        
        if not block_has_filler and self.fillers:
            self._add_filler_to_block(new_block_items, last_block_items, block_index)
        
        # Actualizar el registro del último bloque
        last_block_items.clear()
        last_block_items.update(new_block_items)
    
    def _add_copied_item_to_playlist(self, item, block_index):
        """
        Añade una copia de un item a la playlist.
        
        Args:
            item (dict): Item original
            block_index (int): Índice del bloque actual
        """
        item_copy = item.copy()
        item_copy["item"] = self.item_counter
        item_copy["start_time"] = self.current_time.strftime("%H:%M:%S"),
        item_copy["is_copied"] = True
        item_copy["block"] = len(self.initial_blocks) + block_index + 1
        item_copy["schedule_type"] = "night" if self.is_night_schedule else "day"
        
        # Asegurarse de que start_time sea un string, no una tupla
        if isinstance(item_copy["start_time"], tuple):
            item_copy["start_time"] = item_copy["start_time"][0]
        
        self.playlist.append(item_copy)
        self.item_counter += 1
        self.current_time += timedelta(seconds=item['duration_seconds'])
    
    def _add_promo_to_block(self, new_block_items, last_block_items, block_index):
        """
        Añade una promo al bloque actual si no tiene ninguna.
        
        Args:
            new_block_items (set): Conjunto de nombres de items del bloque actual
            last_block_items (set): Conjunto de nombres de items del último bloque
            block_index (int): Índice del bloque actual
        """
        for promo in self.promos:
            if promo['name'] not in new_block_items and promo['name'] not in last_block_items:
                promo_copy = promo.copy()
                promo_copy["item"] = self.item_counter
                promo_copy["start_time"] = self.current_time.strftime("%H:%M:%S")
                promo_copy["is_copied"] = True
                promo_copy["block"] = len(self.initial_blocks) + block_index + 1
                promo_copy["schedule_type"] = "night" if self.is_night_schedule else "day"
                
                self.playlist.append(promo_copy)
                self.item_counter += 1
                self.current_time += timedelta(seconds=promo['duration_seconds'])
                new_block_items.add(promo['name'])
                break
    
    def _add_filler_to_block(self, new_block_items, last_block_items, block_index):
        """
        Añade un filler al bloque actual si no tiene ninguno.
        
        Args:
            new_block_items (set): Conjunto de nombres de items del bloque actual
            last_block_items (set): Conjunto de nombres de items del último bloque
            block_index (int): Índice del bloque actual
        """
        for filler in self.fillers:
            if filler['name'] not in new_block_items and filler['name'] not in last_block_items:
                filler_copy = filler.copy()
                filler_copy["item"] = self.item_counter
                filler_copy["start_time"] = self.current_time.strftime("%H:%M:%S")
                filler_copy["is_copied"] = True
                filler_copy["block"] = len(self.initial_blocks) + block_index + 1
                filler_copy["schedule_type"] = "night" if self.is_night_schedule else "day"
                
                self.playlist.append(filler_copy)
                self.item_counter += 1
                self.current_time += timedelta(seconds=filler['duration_seconds'])
                new_block_items.add(filler['name'])
                break
    
    def _add_final_block(self):
        """Añade un bloque especial final para completar el tiempo restante."""
        time_remaining = (self.end_datetime - self.current_time).total_seconds()
        
        if time_remaining > 0:
            content_manager = ContentManager(self.promos, self.fillers)
            optimal_combination = content_manager.find_optimal_combination(time_remaining)
            
            if optimal_combination:
                for item in optimal_combination:
                    self.playlist.append({
                        "item": self.item_counter,
                        "start_time": self.current_time.strftime("%H:%M:%S"),
                        "name": item['name'],
                        "duration": format_duration(item['duration_seconds']),
                        "duration_seconds": item['duration_seconds'],
                        "type": item['type'],
                        "block": len(self.initial_blocks) + 1,
                        "is_copied": False,
                        "schedule_type": "night" if self.is_night_schedule else "day"
                    })
                    
                    self.item_counter += 1
                    self.current_time += timedelta(seconds=item['duration_seconds'])

# ----------------------------------------------
# Clase ContentManager
# ----------------------------------------------
class ContentManager:
    """Clase para gestionar el contenido (promos y fillers) de manera determinista."""
    
    def __init__(self, promos, fillers):
        self.promos = sorted(promos, key=lambda x: -x['duration_seconds'])  # Orden descendente
        self.fillers = sorted(fillers, key=lambda x: -x['duration_seconds'])  # Orden descendente

    def find_optimal_combination(self, time_available):
        """
        Encuentra una combinación determinista de promos y fillers.
        Prioriza incluir al menos 1 promo y 1 filler cuando sea posible.
        """
        time_available = int(time_available)
        mandatory_combination = []
        
        # Intentar incluir al menos 1 promo y 1 filler si hay tiempo suficiente
        if self.promos and self.fillers:
            shortest_promo = min(self.promos, key=lambda x: x['duration_seconds'])
            shortest_filler = min(self.fillers, key=lambda x: x['duration_seconds'])
            min_required = shortest_promo['duration_seconds'] + shortest_filler['duration_seconds']
            
            if min_required <= time_available:
                # Buscar la mejor combinación que incluya al menos 1 de cada tipo
                best_combination = self._find_combination_with_both_types(time_available)
                if best_combination:
                    return best_combination

        # Si no se puede incluir ambos, buscar combinación óptima
        return self._find_best_single_type_combination(time_available)

    def _find_combination_with_both_types(self, target_time):
        """Busca combinaciones que incluyan al menos 1 promo y 1 filler."""
        valid_combinations = []
        
        # Probar todas las combinaciones posibles de 1 promo + 1 filler
        for promo in self.promos:
            for filler in self.fillers:
                total = promo['duration_seconds'] + filler['duration_seconds']
                remaining = target_time - total
                
                if remaining < 0:
                    continue
                
                combination = [promo, filler]
                
                # Buscar elementos adicionales para completar el tiempo
                additional_items = self._find_additional_items(remaining)
                combination.extend(additional_items)
                
                valid_combinations.append(combination)
        
        if not valid_combinations:
            return None
            
        # Seleccionar la combinación que más tiempo utilice
        return max(valid_combinations, key=lambda x: sum(i['duration_seconds'] for i in x))

    def _find_additional_items(self, remaining_time):
        """Encuentra elementos adicionales para completar el tiempo restante."""
        combined = self.promos + self.fillers
        combined.sort(key=lambda x: -x['duration_seconds'])
        
        additional = []
        current_duration = 0
        
        for item in combined:
            if current_duration + item['duration_seconds'] <= remaining_time:
                additional.append(item)
                current_duration += item['duration_seconds']
                
        return additional

    def _find_best_single_type_combination(self, target_time):
        """Encuentra la mejor combinación de un solo tipo cuando no caben ambos."""
        best_combination = []
        max_duration = 0
        
        # Probar combinaciones solo de promos
        promo_comb = self._greedy_combination(self.promos, target_time)
        promo_duration = sum(i['duration_seconds'] for i in promo_comb)
        
        # Probar combinaciones solo de fillers
        filler_comb = self._greedy_combination(self.fillers, target_time)
        filler_duration = sum(i['duration_seconds'] for i in filler_comb)
        
        # Seleccionar la mejor combinación
        if promo_duration > filler_duration and promo_duration > 0:
            return promo_comb
        elif filler_duration > 0:
            return filler_comb
        
        return None

    def _greedy_combination(self, items, target_time):
        """Algoritmo greedy determinista para llenar el tiempo."""
        combination = []
        current_duration = 0
        
        for item in items:
            if current_duration + item['duration_seconds'] <= target_time:
                combination.append(item)
                current_duration += item['duration_seconds']
                
        return combination
# ----------------------------------------------
# Funciones de exportacióna
# ----------------------------------------------


def export_to_google_sheets(playlist, sheet_title):
    """
    Exporta la playlist a Google Sheets.
    
    Args:
        playlist (list): Playlist a exportar
        sheet_title (str): Título de la hoja
    
    Returns:
        bool: True si la exportación fue exitosa, False en caso contrario
    """
    try:
        client = authenticate_google_sheets()
        if not client:
            return False
        
        spreadsheet_id = CONFIG["sheet_ids"]["export"]
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        # Validar que el título de la hoja no exista ya
        existing_sheets = [sheet.title for sheet in spreadsheet.worksheets()]
        if sheet_title in existing_sheets:
            # Añadir timestamp para hacerlo único
            timestamp = datetime.now().strftime('%H%M%S')
            sheet_title = f"{sheet_title}_{timestamp}"
        
        # Crear una nueva hoja dentro del Google Sheet
        worksheet = spreadsheet.add_worksheet(title=sheet_title, rows="100", cols="5")

        # Escribir los encabezados en la primera fila
        headers = ['Item', 'Hora de Inicio', 'Nombre', 'Duración', 'Tipo']
        worksheet.update(values=[headers], range_name='A1:E1')

        # Definir colores para cada tipo
        type_colors = CONFIG["type_colors"]

        # Crear las filas de datos
        rows = []
        formats = []
        for i, block in enumerate(playlist, start=2):  # Comenzar desde la fila 2
            # Asegurar que todos los campos requeridos existen
            item = block.get('item', '')
            start_time = block.get('start_time', '')
            name = block.get('name', '')
            
            # Manejar el campo 'duration' cuidadosamente
            duration = block.get('duration', '')
            if not duration and 'duration_seconds' in block:
                duration = format_duration(block['duration_seconds'])
                
            type_ = block.get('type', '')
            
            rows.append([
                item,
                start_time,
                name,
                duration,
                type_
            ])
            
            # Aplicar formato de color según el tipo
            row_range = f'A{i}:E{i}'
            formats.append({
                "range": row_range,
                "format": {
                    "backgroundColor": type_colors.get(type_),  # Usar el color correspondiente
                    "textFormat": {"bold": type_ in ['Program', 'Tanda']}
                }
            })

        # Escribir las filas en una sola llamada
        worksheet.update(values=rows, range_name=f'A2:E{len(rows) + 1}')

        # Aplicar los formatos en un solo lote
        worksheet.batch_format(formats)

        # Aplicar formato a los encabezados
        worksheet.format('A1:E1', {
            'backgroundColor': CONFIG["header_color"],
            'textFormat': {'bold': True, 'foregroundColor': {'red': 1.0, 'green': 1.0, 'blue': 1.0}}  # Blanco
        })

        MessageManager.add_message("success", f"Playlist exportada correctamente a Google Sheets: {spreadsheet.url} -> {sheet_title}")
        return True
    except gspread.exceptions.SpreadsheetNotFound:
        MessageManager.add_message("error", f"No se encontró la hoja de cálculo para exportación")
        return False
    except gspread.exceptions.APIError as e:
        MessageManager.add_message("error", f"Error de API de Google Sheets al exportar: {e}")
        return False
    except Exception as e:
        MessageManager.add_message("error", f"Error al exportar a Google Sheets: {e}")
        logger.exception("Excepción durante la exportación")
        return False
# ----------------------------------------------
# Interfaz de usuario con Streamlit
# ----------------------------------------------
def main():
    """Función principal que define la interfaz de usuario."""
    # Configurar la página
    setup_page()
    
    # Inicializar el gestor de mensajes
    MessageManager.initialize()
    
    # Inicializar estados
    if 'mode' not in st.session_state:
        st.session_state.mode = "Modo Completo"
    
    if 'playlist' not in st.session_state:
        st.session_state.playlist = None
    
    if 'sheet_title' not in st.session_state:
        st.session_state.sheet_title = f"Playlist_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
    
    if 'day_programs' not in st.session_state:
        st.session_state.day_programs = None
    
    if 'night_programs' not in st.session_state:
        st.session_state.night_programs = None
    
    if 'use_manual_times' not in st.session_state:
        st.session_state.use_manual_times = False
    
    if 'use_24h_schedule' not in st.session_state:
        st.session_state.use_24h_schedule = True
    
    if 'use_night_schedule' not in st.session_state:
        st.session_state.use_night_schedule = False
    
    if 'start_time' not in st.session_state:
        st.session_state.start_time = datetime.strptime("06:00:00", "%H:%M:%S").time()
    
    if 'duration_hours' not in st.session_state:
        st.session_state.duration_hours = 24
    
    if 'day_start_time' not in st.session_state:
        st.session_state.day_start_time = datetime.strptime(CONFIG["default_times"]["day_start"], "%H:%M:%S").time()
    
    if 'day_end_time' not in st.session_state:
        st.session_state.day_end_time = datetime.strptime(CONFIG["default_times"]["day_end"], "%H:%M:%S").time()
    
    if 'night_start_time' not in st.session_state:
        st.session_state.night_start_time = datetime.strptime(CONFIG["default_times"]["night_start"], "%H:%M:%S").time()
    
    if 'night_end_time' not in st.session_state:
        st.session_state.night_end_time = datetime.strptime(CONFIG["default_times"]["night_end"], "%H:%M:%S").time()

    # ------------------------------------------------------
    # Título
    # ------------------------------------------------------
    st.title("🎧 Generador de Playlists")
    st.markdown("Configura los parámetros, genera tu playlist y expórtala rápidamente.")
    
    # ------------------------------------------------------
    # Organización en columnas
    # ------------------------------------------------------
    col1, col2, col3 = st.columns([1, 1, 1])
    
    # ------------------------------------------------------
    # Columna 1: Configuración principal
    # ------------------------------------------------------
    with col1:
        st.header("⚙️ Configuración")
        
        # Selector de hoja de rellenos
        sheets = list_sheets()
        selected_sheet = st.selectbox(
            "📂 Hoja de rellenos:",
            sheets if sheets else ["No disponible"],
            disabled=not sheets
        )
        
        # Configuración de fechas
        st.subheader("📅 Fecha de referencia")
        reference_date = st.date_input(
            "Fecha para la playlist:",
            value=date.today(),
            help="Fecha de referencia para la generación de la playlist"
        )
        
        # Configuración de horarios
        st.subheader("⏰ Configuración de Horarios")
        st.session_state.use_24h_schedule = st.checkbox(
            "📅 Playlist de 24 horas", 
            value=st.session_state.use_24h_schedule,
            help="Genera una playlist continua de 24 horas"
        )
        
        if st.session_state.use_24h_schedule:
            st.session_state.start_time = st.time_input(
                "🕒 Hora de inicio", 
                value=st.session_state.start_time,
                help="Hora de inicio de la programación"
            )
            st.session_state.duration_hours = st.slider(
                "⏳ Duración (horas)", 
                1, 24, st.session_state.duration_hours,
                help="Duración total de la playlist en horas"
            )
        else:
            st.session_state.use_night_schedule = st.checkbox(
                "🌙 Horario nocturno", 
                value=st.session_state.use_night_schedule,
                help="Incluir programación nocturna diferenciada"
            )
            
            st.session_state.day_start_time = st.time_input(
                "☀️ Inicio (diurno)", 
                value=st.session_state.day_start_time,
                help="Hora de inicio del horario diurno"
            )
            
            st.session_state.day_end_time = st.time_input(
                "🌇 Fin (diurno)", 
                value=st.session_state.day_end_time,
                help="Hora de fin del horario diurno"
            )
            
            if st.session_state.use_night_schedule:
                st.session_state.night_start_time = st.time_input(
                    "🌃 Inicio (nocturno)", 
                    value=st.session_state.night_start_time,
                    help="Hora de inicio del horario nocturno"
                )
                
                st.session_state.night_end_time = st.time_input(
                    "🌌 Fin (nocturno)", 
                    value=st.session_state.night_end_time,
                    help="Hora de fin del horario nocturno"
                )
        
        # Opción para asignar horarios manualmente
        st.subheader("🕒 Asignación de horarios")
        st.session_state.use_manual_times = st.checkbox(
            "⏱️ Asignar horarios manualmente a los programas", 
            value=st.session_state.use_manual_times,
            help="Permite asignar una hora de inicio específica a cada programa"
        )
        
        # Botón para cargar programas
        if st.button("📥 Cargar programas", use_container_width=True):
            with st.spinner("🔍 Cargando datos..."):
                # Cargar programas diurnos siempre
                st.session_state.day_programs = load_programs_from_google_sheet("dia")
                
                # Cargar programas nocturnos solo si el modo nocturno está activado
                if not st.session_state.use_24h_schedule and st.session_state.use_night_schedule:
                    st.session_state.night_programs = load_programs_from_google_sheet("noche")
                else:
                    st.session_state.night_programs = []
                
                # Mensajes de feedback
                if not st.session_state.day_programs:
                    MessageManager.add_message("warning", "No se pudieron cargar los programas diurnos")
                else:
                    MessageManager.add_message("success", f"✅ Programas diurnos cargados: {len(st.session_state.day_programs)}")
                
                if not st.session_state.use_24h_schedule and st.session_state.use_night_schedule:
                    if not st.session_state.night_programs:
                        MessageManager.add_message("warning", "No se pudieron cargar los programas nocturnos")
                    else:
                        MessageManager.add_message("success", f"✅ Programas nocturnos cargados: {len(st.session_state.night_programs)}")
    
    # ------------------------------------------------------
    # Columna 2: Asignación manual de horarios (si está activada)
    # ------------------------------------------------------
    with col2:
        if st.session_state.use_manual_times and (st.session_state.day_programs or st.session_state.night_programs):
            st.header("🕒 Asignación manual de horarios")
            
            # Programas diurnos
            if st.session_state.day_programs:
                st.markdown("### 🌞 Programas diurnos")
                st.markdown("---")
                
                for i, program in enumerate(st.session_state.day_programs):
                    program_container = st.container()
                    
                    with program_container:
                        col_name, col_time, col_duration, col_end = st.columns([3, 1.5, 1, 1.5])
                        
                        with col_name:
                            st.markdown(f"**{program['name']}**")
                        
                        with col_time:
                            time_key = f"day_time_{i}"
                            current_time = program.get('manual_start_time')
                            if current_time:
                                current_time = datetime.strptime(current_time, "%H:%M:%S").time()
                            else:
                                base_time = datetime.combine(date.today(), st.session_state.start_time if st.session_state.use_24h_schedule else st.session_state.day_start_time)
                                increment = timedelta(hours=1) * i
                                current_time = (base_time + increment).replace(minute=0, second=0).time()
                            
                            selected_time = st.time_input("Inicio", value=current_time, key=time_key)
                            st.session_state.day_programs[i]['manual_start_time'] = selected_time.strftime("%H:%M:%S")
                        
                        with col_duration:
                            st.markdown(f"**⏱️ Duración:**  \n{program['duration_formatted']}")
                        
                        with col_end:
                            end_time = calculate_end_time(
                                st.session_state.day_programs[i]['manual_start_time'],
                                program['duration_seconds']
                            )
                            st.markdown(f"**🕘 Fin:**  \n{end_time}")
                    
                    if i < len(st.session_state.day_programs) - 1:
                        st.markdown("---")
            
            # Programas nocturnos
            if not st.session_state.use_24h_schedule and st.session_state.use_night_schedule and st.session_state.night_programs:
                st.markdown("### 🌙 Programas nocturnos")
                st.markdown("---")
                
                for i, program in enumerate(st.session_state.night_programs):
                    program_container = st.container()
                    
                    with program_container:
                        col_name, col_time, col_duration, col_end = st.columns([3, 1.5, 1, 1.5])
                        
                        with col_name:
                            st.markdown(f"**{program['name']}**")
                        
                        with col_time:
                            time_key = f"night_time_{i}"
                            current_time = program.get('manual_start_time')
                            if current_time:
                                current_time = datetime.strptime(current_time, "%H:%M:%S").time()
                            else:
                                base_time = datetime.combine(date.today(), st.session_state.night_start_time)
                                increment = timedelta(hours=1) * i
                                current_time = (base_time + increment).replace(minute=0, second=0).time()
                            
                            selected_time = st.time_input("Inicio", value=current_time, key=time_key)
                            st.session_state.night_programs[i]['manual_start_time'] = selected_time.strftime("%H:%M:%S")
                        
                        with col_duration:
                            st.markdown(f"**⏱️ Duración:**  \n{program['duration_formatted']}")
                        
                        with col_end:
                            end_time = calculate_end_time(
                                st.session_state.night_programs[i]['manual_start_time'],
                                program['duration_seconds']
                            )
                            st.markdown(f"**🕘 Fin:**  \n{end_time}")
                    
                    if i < len(st.session_state.night_programs) - 1:
                        st.markdown("---")
            
            # Validar horarios asignados
            if st.button("✅ Validar horarios", use_container_width=True):
                day_progs = []
                if st.session_state.day_programs:
                    day_progs = [p for p in st.session_state.day_programs if p.get('manual_start_time')]
                
                night_progs = []
                if not st.session_state.use_24h_schedule and st.session_state.use_night_schedule and st.session_state.night_programs:
                    night_progs = [p for p in st.session_state.night_programs if p.get('manual_start_time')]
                
                is_valid, overlaps = validate_schedules(
                    day_progs,
                    night_progs,
                    st.session_state.day_start_time if not st.session_state.use_24h_schedule else st.session_state.start_time,
                    st.session_state.night_start_time if not st.session_state.use_24h_schedule and st.session_state.use_night_schedule else None
                )
                
                if not is_valid:
                    st.error("❌ Conflictos de horario detectados:")
                    cols = st.columns(2)
                    for i, (prog1, prog2) in enumerate(overlaps):
                        cols[i%2].warning(f"⏰ {prog1} ↔ {prog2}")
                else:
                    st.success("✅ Horarios válidos (sin conflictos)")
        else:
            st.header("✨ Generar Playlist")
            
            block_interval = st.slider(
                "⏱️ Intervalo entre bloques (min)", 
                CONFIG["block_intervals"]["min"], 
                CONFIG["block_intervals"]["max"], 
                CONFIG["block_intervals"]["default"], 
                key="block_interval"
            )
            
            max_partial = st.number_input(
                "⏳ Duración máxima tanda parcial (s)", 
                10, 60, 30, 
                key="max_partial"
            )
    
    # ------------------------------------------------------
    # Columna 3: Generación y exportación
    # ------------------------------------------------------
    with col3:
        st.header("🚀 Generar y Exportar")
        
        if st.button("🎵 Generar Playlist", type="primary", use_container_width=True):
            with st.spinner("🔍 Generando playlist..."):
                # Cargar datos
                promos = load_promos_from_google_sheet()
                fillers = load_fillers_from_google_sheet(selected_sheet) if sheets else []
                
                if not st.session_state.day_programs or not promos or not fillers:
                    MessageManager.add_message("warning", "⚠️ Faltan datos para generar la playlist")
                else:
                    # Generar playlist diurna
                    day_generator = PlaylistGenerator(
                        st.session_state.day_start_time,
                        end_time=st.session_state.day_end_time,
                        promos=promos,
                        fillers=fillers,
                        user_programs=st.session_state.day_programs,
                        reference_date=reference_date,
                        use_manual_times=st.session_state.use_manual_times
                    )
                    day_playlist = day_generator.generate()
                    
                    # Generar playlist nocturna (si aplica)
                    night_playlist = []
                    if (not st.session_state.use_24h_schedule and 
                        st.session_state.use_night_schedule and 
                        st.session_state.night_programs):
                        
                        night_generator = PlaylistGenerator(
                            st.session_state.night_start_time,
                            end_time=st.session_state.night_end_time,
                            promos=promos,
                            fillers=fillers,
                            user_programs=st.session_state.night_programs,
                            reference_date=reference_date,
                            use_manual_times=st.session_state.use_manual_times,
                            is_night_schedule=True
                        )
                        night_playlist = night_generator.generate()
                    
                    # Combinar playlists
                    st.session_state.playlist = day_playlist + night_playlist
                    
                    # Renumerar items
                    for i, item in enumerate(st.session_state.playlist, start=1):
                        item['item'] = i
                    
                    # Mensaje de confirmación
                    if st.session_state.playlist:
                        day_count = len(day_playlist)
                        night_count = len(night_playlist)
                        MessageManager.add_message("success", 
                            f"✅ Playlist generada con {len(st.session_state.playlist)} elementos\n"
                            f"  - Diurnos: {day_count} items\n"
                            f"  - Nocturnos: {night_count} items")
                    else:
                        MessageManager.add_message("error", "❌ No se pudo generar la playlist")
        
        st.markdown("---")
        
        st.header("📤 Exportar Playlist")
        
        new_sheet_name = st.text_input(
            "📝 Nombre de la hoja:",
            value=st.session_state.sheet_title,
            help="Nombre que tendrá la hoja en Google Sheets"
        )
        st.session_state.sheet_title = new_sheet_name
        
        if st.button("📊 Exportar a Google Sheets", use_container_width=True):
            if st.session_state.playlist:
                with st.spinner("⏳ Exportando..."):
                    if export_to_google_sheets(st.session_state.playlist, st.session_state.sheet_title):
                        MessageManager.add_message("success", "✅ Playlist exportada correctamente")
                    else:
                        MessageManager.add_message("error", "❌ Error al exportar la playlist")
            else:
                MessageManager.add_message("error", "❌ No hay playlist para exportar")
        
        st.header("📢 Notificaciones")
        MessageManager.display_messages(3)
    
    # ------------------------------------------------------
    # Vista previa de la playlist
    # ------------------------------------------------------
    st.markdown("---")
    st.header("📜 Vista Previa de la Playlist")
    
    if st.session_state.playlist:
        playlist_df = pd.DataFrame(st.session_state.playlist)
        
        # Aplicar estilos
        def color_row(row):
            colors = {
                'Program': 'background-color: white; color: black;',
                'Tanda': 'background-color: #00FF00; color: black;',
                'Promo': 'background-color: #46BDC6; color: black;',
                'Filler': 'background-color: #808080; color: white;',
                'Tanda Parcial': 'background-color: #FFFF00; color: black;'
            }
            return [colors.get(row['type'], '')] * len(row)
        
        styled_df = playlist_df.style.apply(color_row, axis=1)
        
        st.dataframe(
            styled_df,
            column_config={
                "item": "Ítem",
                "start_time": "Hora Inicio",
                "name": "Contenido",
                "duration": "Duración",
                "type": "Tipo",
                "block": "Bloque",
                "is_copied": "Es Copia",
                "schedule_type": "Horario"
            },
            use_container_width=True,
            height=600
        )
        
        # Estadísticas
        st.subheader("📊 Estadísticas")
        cols = st.columns(3)
        with cols[0]:
            st.metric("Total elementos", len(st.session_state.playlist))
        with cols[1]:
            total_seconds = sum(item['duration_seconds'] for item in st.session_state.playlist)
            st.metric("Duración total", format_duration(total_seconds))
        with cols[2]:
            st.metric("Bloques", playlist_df['block'].nunique())
        
        # Debug: Mostrar conteo de programas nocturnos
        if st.checkbox("Mostrar detalles de depuración"):
            st.write("Programas nocturnos cargados:", len(st.session_state.night_programs) if st.session_state.night_programs else "No hay programas nocturnos")
            st.write("Items nocturnos generados:", len([i for i in st.session_state.playlist if i.get('schedule_type') == 'night']))
    else:
        st.info("ℹ️ No hay playlist generada. Configura los parámetros y haz clic en 'Generar Playlist'.")

if __name__ == "__main__":
    main()
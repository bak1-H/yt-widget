from playback import PlaybackState
from repeat import RepeatMode
from settings import CloseAction, GlassStyle
from theme import ThemeName

APP_TITLE = "YT Widget"
MPV_NOT_FOUND = "No se encontró mpv. Instálalo con: winget install shinchiro.mpv"
NOTHING_PLAYING = "Nada en reproducción"
NOTHING_PLAYING_YET = "No hay ninguna canción en reproducción"
NOTHING_TO_PLAY = "No hay nada para reproducir"
STATE_MESSAGES = {
    PlaybackState.IDLE: "Busca una canción o pega un link de YouTube",
    PlaybackState.LOADING: "Cargando…",
    PlaybackState.FAILED: "No se pudo reproducir, prueba con otra",
}
MPV_DID_NOT_START = "mpv no se pudo iniciar"
MPV_CONNECTION_LOST = "Se perdió la conexión con mpv"
MPV_CONNECTION_CLOSED = "mpv cerró la conexión"
PLAYER_STOPPED = "El reproductor se detuvo, reiniciando"
PLAYER_RESTARTED = "El reproductor se detuvo y se reinició"
PLAYER_RESTARTED_QUEUE_RESTORED = "El reproductor se reinició y se restauró la cola"
PLAYER_RESTARTED_QUEUE_LOST = "El reproductor se reinició y no se pudo restaurar la cola"
RESTART_FAILED = "No se pudo reiniciar el reproductor, reintentando"

SEARCH_PLACEHOLDER = "Busca una canción o pega un link"
PLAY_NOW_TOOLTIP = "Reproducir ahora"
ENQUEUE_TOOLTIP = "Agregar a la cola"
PREVIOUS_TOOLTIP = "Anterior"
PLAY_PAUSE_TOOLTIP = "Reproducir / pausar"
PLAY_LABEL = "Reproducir"
PAUSE_LABEL = "Pausa"
NEXT_TOOLTIP = "Siguiente"
PANEL_TOOLTIP = "Cola, recientes, playlists y ajustes"
VOLUME_TOOLTIP = "Volumen"
REPEAT_TOOLTIPS = {
    RepeatMode.OFF: "Repetir: no (clic para repetir la cola)",
    RepeatMode.QUEUE: "Repetir: cola (clic para repetir la canción)",
    RepeatMode.SONG: "Repetir: canción (clic para no repetir)",
}
DOWNLOADED_TOOLTIP = "Guardada en el disco, suena sin internet"
SONG_OPTIONS = "Opciones de la canción"
CLOSE_TOOLTIPS = {CloseAction.HIDE: "Ocultar en la bandeja", CloseAction.QUIT: "Cerrar el widget"}

QUEUE_TAB = "En cola"
HISTORY_TAB = "Recientes"
PLAYLISTS_TAB = "Playlists"
SETTINGS_TAB = "Ajustes"
QUEUE_EMPTY = "No hay nada en cola. Usa + para agregar canciones"
HISTORY_EMPTY = "Las canciones que reproduzcas aparecerán aquí"
PLAYLIST_EMPTY = "Vacía. Usa ⋯ en una canción para agregarla aquí"
PLAYLIST_HINT = "Usa ⋯ o clic derecho para más opciones"

PLAY_NOW = "Reproducir ahora"
PLAY_NEXT = "Reproducir después"
ADD_TO_QUEUE = "Agregar a la cola"
ADD_TO_PLAYLIST = "Agregar a playlist"
NEW_PLAYLIST_ITEM = "Nueva playlist…"
REMOVE_FROM_LIST = "Quitar de esta lista"
UNDO = "Deshacer"
DISMISS = "Descartar"
CANCEL = "Cancelar"
ADD_THERE = "Agregar ahí"
SONG_NOT_IN_LIST = "Esa canción ya no está en la lista"
NOTHING_TO_ADD = "Esa canción ya no está esperando una playlist"
UNDO_FAILED = "No se pudo deshacer"
NEW_PLAYLIST_HINT = "Escribe el nombre: la canción se agregará a la nueva playlist"
PLAYS_NEXT = "Se reproducirá después de esta canción"
ADDED_TO_QUEUE = "Agregada a la cola"

NEW_PLAYLIST_PLACEHOLDER = "Nombre de la nueva playlist"
NEW_PLAYLIST_TOOLTIP = "Nueva playlist"
PLAY_PLAYLIST = "Reproducir playlist"
DELETE_PLAYLIST = "Eliminar playlist"
NO_PLAYLIST = "Crea una playlist con el botón +"
CREATE_FIRST = "Primero crea una playlist"
ADD_SONGS_FIRST = "Primero agrega canciones"
NAME_REQUIRED = "Escribe un nombre primero"
SAVE_FAILED = "No se pudieron guardar tus playlists"
HISTORY_SAVE_FAILED = "No se pudo guardar tu historial"
HISTORY_CLEARED = "Historial borrado"
SETTINGS_SAVE_FAILED = "No se pudieron guardar los ajustes"
PLAYLISTS_DAMAGED_NO_BACKUP = "Algunos datos de tus playlists estaban dañados y no se pudo crear una copia"

AUTOSTART = "Iniciar con Windows"
AUTOSTART_FAILED = "No se pudo cambiar el inicio con Windows"
WINDOW_POSITION = "Posición de la ventana"
POSITION_TOPMOST = "Encima de todo"
POSITION_NORMAL = "Normal"
POSITION_DESKTOP = "En el escritorio"
THEME = "Tema"
THEME_LABELS = {
    ThemeName.GLASS: "Vidrio",
    ThemeName.NIGHT: "Nocturno",
    ThemeName.VINYL: "Vinilo",
    ThemeName.FROST: "Escarcha clara",
}
GLASS = "Efecto vidrio"
SHOW_THUMBNAIL = "Mostrar portada"
SHOW_THUMBNAIL_TOOLTIP = "Muestra la portada de YouTube de la canción que suena"
GLASS_STYLE = "Estilo del vidrio"
GLASS_STYLE_LABELS = {GlassStyle.BLUR: "Desenfocado", GlassStyle.CLEAR: "Transparente"}
GLASS_OPACITY = "Opacidad del vidrio"
STARTUP_VOLUME = "Volumen al abrir"
CLOSE_ACTION = "Al tocar ✕"
CLOSE_HIDE = "Ocultar en la bandeja"
CLOSE_QUIT = "Cerrar el widget"
PREFETCH = "Canciones a precargar"
AUTOPLAY = "Reproducción automática"
AUTOPLAY_TOOLTIP = "Agrega canciones recomendadas por YouTube cuando queda una canción o menos en la cola. Solo funciona con «Repetir: no»"
AUTOPLAY_NEEDS_NO_REPEAT = "Solo funciona con «Repetir: no»"
GLASS_REQUIRED = "(requiere el efecto vidrio)"
AUTOPLAY_UNAVAILABLE = "No se pudieron obtener canciones recomendadas"
SUGGESTED = "Sugerida"
SUGGESTED_TOOLTIP = "Agregada por la reproducción automática"
CACHE_ENABLED = "Guardar canciones en el disco"
CACHE_FOLDER = "Carpeta"
CACHE_CHANGE_FOLDER = "Cambiar…"
CACHE_CHANGE_FOLDER_TOOLTIP = "Elige otra carpeta para las canciones guardadas"
CACHE_PICK_FOLDER = "Elige la carpeta de canciones guardadas"
CACHE_LIMIT = "Espacio máximo"
CACHE_QUALITY = "Calidad"
CACHE_QUALITY_MAX = "Máxima"
CACHE_QUALITY_MEDIUM = "Media"
CACHE_CLEAR = "Vaciar"
CACHE_CLEAR_TOOLTIP = "Borra las canciones guardadas en el disco"
CACHE_CLEARING = "Borrando canciones guardadas…"
CACHE_CLEARED = "Canciones guardadas borradas"
CACHE_CLEARED_KEEPING_PLAYING = "Canciones borradas, salvo la que suena ahora"
CACHE_MOVING = "Moviendo canciones guardadas…"
CACHE_MOVED = "Canciones guardadas movidas"
CACHE_MOVED_KEEPING_PLAYING = "Canciones movidas, salvo la que suena ahora"
CACHE_BUSY = "Espera a que termine la operación en curso"
CACHE_CLEAR_FAILED = "No se pudieron borrar algunas canciones guardadas"
CACHE_MOVE_FAILED = "No se pudieron mover las canciones guardadas"
CACHE_DOWNLOAD_FAILED = "No se pudo guardar una canción en el disco"
LOW_DISK_SPACE = "poco espacio en el disco"
CACHE_UPDATE_FAILED = "No se pudo actualizar la carpeta de canciones guardadas"
CLEAR_HISTORY = "Borrar historial"
CLEAR_HISTORY_TOOLTIP = "Borra todas las canciones recientes"

TRAY_TOGGLE = "Mostrar / Ocultar"
TRAY_PLAY_PAUSE = "Reproducir / Pausar"
TRAY_NEXT = "Siguiente"
TRAY_QUIT = "Salir"


def prefetch_option(count: int) -> str:
    return "Desactivado" if count == 0 else str(count)


def paused(elapsed: str) -> str:
    return f"En pausa · {elapsed}"


def name_too_long(limit: int) -> str:
    return f"El nombre es demasiado largo (máximo {limit} caracteres)"


def already_exists(name: str) -> str:
    return f"'{name}' ya existe"


def no_longer_exists(name: str) -> str:
    return f"'{name}' ya no existe"


def created(name: str) -> str:
    return f"Playlist '{name}' creada"


def created_with_song(name: str) -> str:
    return f"Playlist '{name}' creada con la canción"


def playing_playlist(name: str) -> str:
    return f"Reproduciendo la playlist '{name}'"


def deleted(name: str) -> str:
    return f"Playlist '{name}' eliminada"


def restored(name: str) -> str:
    return f"Playlist '{name}' restaurada"


def added_to(name: str) -> str:
    return f"Agregada a {name}"


def removed_from(name: str) -> str:
    return f"Quitada de {name}"


def removed_track(title: str) -> str:
    return f"Se quitó '{title}'"


def removed_from_queue(title: str) -> str:
    return f"Se quitó '{title}' de la cola"


def removed_from_history(title: str) -> str:
    return f"Se quitó '{title}' de recientes"


def not_found(title: str) -> str:
    return f"No se encontró '{title}'"


def playlists_damaged(backup_name: str) -> str:
    return f"Algunos datos de tus playlists estaban dañados, hay una copia en {backup_name}"


def gigabytes(value: float) -> str:
    return f"{value:.1f}".removesuffix(".0").replace(".", ",") + " GB"


def size(byte_count: int) -> str:
    gb = byte_count / 1024**3
    if gb >= 1024:
        return f"{gb / 1024:.1f}".removesuffix(".0").replace(".", ",") + " TB"
    return gigabytes(gb) if gb >= 1 else f"{round(byte_count / 1024**2)} MB"


def cache_usage(bytes_used: int, limit_gb: float, songs: int) -> str:
    noun = "canción" if songs == 1 else "canciones"
    return f"{size(bytes_used)} de {gigabytes(limit_gb)} · {songs} {noun}"


def cache_usage_tooltip(bytes_used: int, limit_gb: float, percent: int) -> str:
    return f"{size(bytes_used)} de {gigabytes(limit_gb)} ({percent} %)"


def drive_free(free_bytes: int, drive: str, low_space: bool = False) -> str:
    text = f"Quedan {size(free_bytes)} libres en {drive}" if drive else f"Quedan {size(free_bytes)} libres"
    return f"{text} · {LOW_DISK_SPACE}" if low_space else text


def cache_move_question(songs: int) -> str:
    noun = "canción guardada" if songs == 1 else "canciones guardadas"
    lines = (
        f"La carpeta actual tiene {songs} {noun}.",
        "",
        "Sí: moverlas a la nueva carpeta.",
        "No: empezar con la nueva carpeta vacía (las actuales no se tocan).",
        "Cancelar: no cambiar de carpeta.",
    )
    return "\n".join(lines)


def cache_clear_question(songs: int) -> str:
    noun = "canción guardada" if songs == 1 else "canciones guardadas"
    return f"Se borrarán {songs} {noun} del disco. ¿Quieres continuar?"

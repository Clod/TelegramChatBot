# --- General ---
ERROR_GENERIC = "Ocurrió un error inesperado."
ERROR_PROCESSING_REQUEST = "Error al procesar su solicitud."
ERROR_TRY_AGAIN_LATER = "Por favor intente nuevamente más tarde."
OPERATION_CANCELED = "Operación cancelada."
ACTION_NOT_RECOGNIZED = "Acción no reconocida."
BOT_IS_RUNNING = '¡El bot está funcionando!'

# --- Configuration Loading ---
LOG_DOTENV_LOADED = "Archivo .env cargado (override=True)"
LOG_RAW_DEBUG_MODE = "Valor DEBUG_MODE del entorno: '{raw_value}'"
LOG_DEBUG_MODE_EVALUATED = "DEBUG_MODE evaluado como: {debug_mode}"
DEBUG_MODE_ON = "¡Modo depuración ACTIVADO!"
DEBUG_MODE_OFF = "Modo depuración DESACTIVADO."
ERROR_TOKEN_NOT_SET = "La variable de entorno TELEGRAM_BOT_TOKEN no está configurada"
WARN_BASE_URL_NOT_SET = "La variable BASE_URL no está configurada. Intentando inferir..."
WARN_INFERRED_BASE_URL = "BASE_URL inferida como {base_url}. Configure esto explícitamente en .env para producción."

# --- Database ---
LOG_DB_INIT_SUCCESS = "Base de datos inicializada exitosamente"
LOG_DB_SAVED_MESSAGE = "Mensaje guardado del usuario {user_id}: {text_preview}..."
LOG_DB_SAVED_MEDIA_MESSAGE = "Mensaje de {message_type} guardado del usuario {user_id}"
LOG_DB_SAVED_PROCESSED_TEXT = "Texto '{message_type}' guardado en user_messages para usuario {user_id}, mensaje original {original_message_id}"
ERROR_DB_SAVING_PROCESSED_TEXT = "Error guardando texto '{message_type}' para usuario {user_id}: {db_err}"
LOG_DB_DELETED_USER_DATA = "Datos eliminados para user_id {user_id}: {messages_deleted} mensajes, {interactions_deleted} interacciones"
ERROR_DB_DELETING_USER_DATA = "Error eliminando datos de usuario: {error}"
LOG_DB_RETRIEVED_HISTORY = "Recuperados {count} mensajes para usuario {user_id}, incluyendo datos procesados"
DB_STATUS_OK = 'ok'
DB_STATUS_MISSING = 'no encontrado'
DB_STATUS_ERROR = 'error'

# --- Telegram Bot ---
PHOTO_PROCESSING_USER_MSG = "Procesando tu imagen..."
PHOTO_DOWNLOAD_FAILED_USER_MSG = "Lo siento, no pude descargar tu imagen."
PHOTO_PROCESSING_FAILED_USER_MSG = "Lo siento, no pude procesar tu imagen. Error: {error_text}"
PHOTO_EXTRACTED_INFO_USER_MSG = "Información extraída:\n\n{result_text}"
PHOTO_PROCESSED_NEXT_ACTION_USER_MSG = "Imagen procesada. ¿Qué te gustaría hacer ahora?"
TEXT_UNKNOWN_COMMAND_USER_MSG = "Lo siento, no reconozco ese comando."
TEXT_HISTORY_HEADER = "📝 Tu historial de mensajes:\n\n"
TEXT_HISTORY_NO_PREVIOUS = "No se encontraron mensajes anteriores."
TEXT_RECEIVED_USER_MSG = "Mensaje recibido."
TEXT_RECEIVED_NO_HISTORY_USER_MSG = "Mensaje recibido. No se encontró historial."

# --- Buttons ---
BUTTON_ANALYZE_MESSAGES = "📊 Analizar mis mensajes"
BUTTON_RETRIEVE_FORM = "📄 Recuperar datos de formulario"
BUTTON_RETRIEVE_SHEET = "📈 Recuperar datos de hoja"
BUTTON_VIEW_DATA = "📊 Ver mis datos"
BUTTON_DELETE_DATA = "🗑️ Eliminar mis datos"
BUTTON_BACK_MAIN_MENU = "Volver al menú principal"
BUTTON_CONFIRM_DELETE = "✅ Sí, eliminar mis datos"
BUTTON_CANCEL_DELETE = "❌ No, conservar mis datos"

# --- Callbacks ---
CALLBACK_DELETE_CONFIRMATION_USER_MSG = "⚠️ ¿Seguro que quieres eliminar todos los datos? No se puede deshacer."
CALLBACK_DELETE_SUCCESS_USER_MSG = "✅ Datos eliminados ({msg_del} mensajes, {int_del} interacciones). Usa /start nuevamente."

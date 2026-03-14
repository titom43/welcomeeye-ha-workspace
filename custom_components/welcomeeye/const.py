from homeassistant.const import Platform

DOMAIN = "welcomeeye"
PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.SENSOR, Platform.LOCK, Platform.BINARY_SENSOR]

CONF_NAME = "name"
CONF_DEVICE_HOST = "device_host"
CONF_CGI_PORT = "cgi_port"
CONF_SCHEME = "scheme"
CONF_USERNAME = "username"
CONF_DEVICE_PASSWORD = "device_password"
CONF_DATA_ENCODE_KEY = "data_encode_key"
CONF_HS_DEVICE = "hs_device"
CONF_SECURITY = "security"
CONF_DOOR = "door"
CONF_LOCK_NUMBER = "lock_number"
CONF_OPEN_PASSWORD = "open_password"
CONF_VERIFY_SSL = "verify_ssl"

CONF_AUTH_BASE_URL = "auth_base_url"
CONF_ALARM_BASE_URL = "alarm_base_url"
CONF_AUTH_MODE = "auth_mode"
CONF_AUTH_ACCOUNT = "auth_account"
CONF_AUTH_PASSWORD = "auth_password"
CONF_AUTH_TYPE = "auth_type"
CONF_AUTH_CODE = "auth_code"
CONF_IP_REGION_ID = "ip_region_id"
CONF_POLL_INTERVAL_MIN = "poll_interval_min"

DEFAULT_NAME = "WelcomeEye"
DEFAULT_SCHEME = "https"
DEFAULT_CGI_PORT = 443
DEFAULT_SECURITY = "username"
DEFAULT_DOOR = 1
DEFAULT_LOCK_NUMBER = 1
DEFAULT_VERIFY_SSL = False
DEFAULT_AUTH_MODE = "user"
DEFAULT_AUTH_TYPE = 0
DEFAULT_IP_REGION_ID = 0

AUTH_MODES = ["user", "third", "deli", "free"]

DATA_RUNTIME = "runtime"
DATA_SERVICE_REGISTERED = "service_registered"
SIGNAL_EVENT = f"{DOMAIN}_event_{{entry_id}}"

SERVICE_OPEN_DOOR = "open_door"

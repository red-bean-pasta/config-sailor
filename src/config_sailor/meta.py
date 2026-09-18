

MODULE_NAME = __package__.split('.')[0]
APP_NAME = MODULE_NAME.replace("_", "-")
APP_ABBR = ''.join(part[0] for part in APP_NAME.split('-')).upper()

PRESERVED_PREFIX = "$"
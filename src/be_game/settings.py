import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# secrets
if 'POSTGRES_PASSWORD_FILE' in os.environ:
    with open(os.environ.get('POSTGRES_PASSWORD_FILE'), 'r', encoding='utf-8') as f:
        DB_PASSWORD = f.read()
else:
    DB_PASSWORD = 'please_use_env'
if 'DJANGO_SECRET_FILE' in os.environ:
    with open(os.environ.get('DJANGO_SECRET_FILE'), 'r', encoding='utf-8') as f:
        SECRET_KEY = f.read()
else:
    SECRET_KEY = 'please_use_env'
if 'JWT_SECRET_FILE' in os.environ:
    with open(os.environ.get('JWT_SECRET_FILE'), 'r', encoding='utf-8') as f:
        JWT_SECRET = f.read()
else:
    JWT_SECRET = 'please_use_env'
JWT_ALGORITHM = 'HS256'
JWT_EXP_DELTA_SECONDS = 3600

# debug and host settings
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost').split(',')

# Application definition

INSTALLED_APPS = [
    'daphne',
    'pong',
]

MIDDLEWARE = [
]

ROOT_URLCONF = 'be_game.urls'

TEMPLATES = [
]

# Channels
ASGI_APPLICATION = "be_game.asgi.application"
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer"
    }
}

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'be-chat'),
        'USER': os.environ.get('POSTGRES_USER', 'postgres'),
        'PASSWORD': DB_PASSWORD,
        'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

# Proxy settings
USE_X_FORWARDED_HOST = True

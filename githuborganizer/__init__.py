from celery import Celery
import os

SETTINGS = [
    'DEBUG',
    'GITHUB_PRIVATE_KEY',
    'GITHUB_APP_ID',
    'GITHUB_WEBHOOK_SECRET',
    'CELERY_BROKER',
    'PROCESS_INSTALLS_INTERVAL']

CONFIG = {}

for setting in SETTINGS:
    if setting in os.environ:
        CONFIG[setting] = os.environ[setting]


if 'CELERY_BROKER' in CONFIG:
    celery = Celery('gitorganizer', broker=CONFIG['CELERY_BROKER'])
else:
    celery = Celery('gitorganizer')

"""
Configuración de Celery para tareas asíncronas.
"""

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "clinicas",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Lima",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Auto-descubrir tareas en app/tasks/
celery_app.autodiscover_tasks(["app.tasks"])

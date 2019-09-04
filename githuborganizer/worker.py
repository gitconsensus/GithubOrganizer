from celery.schedules import crontab
from githuborganizer.tasks import github
from githuborganizer import celery
import os

@celery.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    print('Root Task - Schedule Installation Jobs')
    sender.add_periodic_task(
        float(os.environ.get('PROCESS_INSTALLS_INTERVAL', 30 * 60.0)),
        github.process_installs.s(),
        name='Root Task - Schedule Installation Jobs')

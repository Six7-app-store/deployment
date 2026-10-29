"""Simulated Celery workload, no real OpenStack access."""
import os
import time
from celery import Celery

app = Celery("test-worker", broker=os.environ["BROKER_URL"])
app.conf.update(task_acks_late=True, worker_prefetch_multiplier=1)


@app.task(name="experiment.long_task")
def long_task():
    time.sleep(35)

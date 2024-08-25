#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os

from celery import Celery
from celery.schedules import crontab
from django.conf import settings

from libs import tool
from main.settings import PROJECT

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

app = Celery(PROJECT)
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)


@app.task(exchange=f'{PROJECT}.fanout', routing_key=PROJECT, expires=360, priority=10)
def logrotate(target):
    tool.logrotate(target)
    return 'Success'


@app.on_after_finalize.connect
def schedule(sender, **kwargs):
    from apps.openstacks.tasks import sync_resource_flow

    task = sender.add_periodic_task

    task(crontab(minute=0, hour=0), logrotate.s('logs/'), name='Logrotate')

    task(
        crontab(minute='*/15'),
        sync_resource_flow.s(),
        name='Opesntacks資源刷新',
    )

    # TODO
    # task(
    #     crontab(minute='*/15', hour='7-22'),
    #     scan_other_tasks.scan_vcenter_hosts.s(),
    #     name='vCenter資訊刷新',
    # )

    # task(
    #     crontab(minute='*/30'),
    #     monitor.vm_monitor.s(),
    #     name='虛擬機監控資訊刷新',
    # )

    # task(
    #     crontab(minute=0, hour=9, day_of_week='1'),
    #     scan_saltstack.scan_telegraf.s(),
    #     name='虛擬機同步SlatStack',
    # )




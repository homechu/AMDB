#!/usr/bin/env python

import socket
import time

from contextlib import contextmanager
from datetime import datetime
from functools import wraps

from django.core.cache import cache

LOCK_EXPIRE = 60 * 10


@contextmanager
def task_lock(lock_id, oid):
    """Celery 或 進程使用"""

    timeout_at = time.monotonic() + LOCK_EXPIRE - 3
    status = cache.add(lock_id, oid, LOCK_EXPIRE)
    try:
        yield status
    finally:
        if time.monotonic() < timeout_at and status:
            cache.delete(lock_id)


def lock_wraps(func):
    @wraps(func)
    def run(*args, **kwargs):
        with task_lock(f'lock_wraps_{func.__name__}', datetime.now()) as ac:
            return func(*args, **kwargs) if ac else False

    return run

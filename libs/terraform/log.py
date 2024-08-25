from django.conf import settings

import logging
import datetime
import os

log_filename = datetime.datetime.now().strftime("terraform.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)-8s %(levelname)-8s %(message)s',
    datefmt='%Y/%m/%d %H:%M:%S',
    filename=os.path.join(settings.BASE_DIR, 'logs', log_filename)
)

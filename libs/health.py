from amqp.exceptions import AccessRefused
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.db.utils import OperationalError
from kombu import Connection
from redis import exceptions, from_url
from main.celery import app

class RabbitMQHealthCheck:
    """Health check for RabbitMQ."""

    @classmethod
    def check_status(self, rabbit_url: str) -> str:
        """Check RabbitMQ service by opening and closing a broker channel.

        Returns:
            str: 狀況説明
        """

        try:
            with Connection(rabbit_url) as conn:
                conn.connect()
        except ConnectionRefusedError as e:
            return False, f'Unable to connect to RabbitMQ: Connection was refused. {e}'

        except AccessRefused as e:
            return False, f'Unable to connect to RabbitMQ: Authentication error. {e}'

        except IOError as e:
            return False, f'IOError. {e}'

        except BaseException as e:
            return False, f'Unknown error. {e}'
        else:
            return True, 'Connection established. RabbitMQ is healthy.'


class RedisHealthCheck:
    """Health check for Redis."""

    @classmethod
    def check_status(self, redis_url: str) -> str:
        """Check Redis service by pinging the redis instance with a redis connection.

        Returns:
            str: 狀況説明
        """
        
        try:
            with from_url(redis_url) as conn:
                conn.ping()
        except ConnectionRefusedError as e:
            return False, f'Unable to connect to Redis: Connection was refused. {e}'

        except exceptions.TimeoutError as e:
            return False, f'Unable to connect to Redis: Timeout. {e}'

        except exceptions.ConnectionError as e:
            return False, f'Unable to connect to Redis: Connection Error. {e}'

        except BaseException as e:
            return False, f'Unknown error. {e}'
        else:
            return True, 'Connection established. Redis is healthy.'


class DatabaseHealthCheck:
    """Health check for Database."""

    @classmethod
    def check_status(app_configs, **kwargs):
        """check to see if connecting to the configured default database.

        Returns:
            str: 狀況説明
        """

        try:
            connection.ensure_connection()
        except OperationalError as e:
            return False, f'Could not connect to database: {e}'

        except ImproperlyConfigured as e:
            return False, f'Datbase misconfigured: {e}'
        else:
            if not connection.is_usable():
                return False, "Database connection is not usable"

        return True, 'Connection established. Database is healthy.'


class CeleryHealthCheck:
    """Health check for Celery.""" 
    
    @classmethod
    def check_status(app_configs, **kwargs):
        """check to see if connecting to the configured default database.

        Returns:
            str: 狀況説明
        """
        
        stats = app.control.inspect().stats()
        if stats:
            return True, 'Celery Worker established. Worker is healthy.'
        else:
            return False, "Celery Worker is not usable"


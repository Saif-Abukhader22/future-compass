import threading

from starlette.requests import Request

storage = threading.local()


def set_request(request):
    storage.request = request


def get_request() -> Request:
    return getattr(storage, 'request', None)


def get_source_id() -> str:
    return getattr(storage, 'source_id', None)

from fastapi import Response


def get_uniform_reject() -> Response:
    return Response(status_code=404)
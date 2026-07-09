"""
Custom Channels middleware that authenticates WebSocket connections using
the same JWT access tokens issued by SimpleJWT for REST calls.

Browsers can't easily attach an Authorization header to a WebSocket
handshake, so the frontend instead connects with `?token=<access_token>`
in the URL. This middleware reads that, validates it, and attaches the
resulting user to `scope["user"]` — exactly like Django's AuthMiddleware
does for regular HTTP requests.
"""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

from users.models import User


@database_sync_to_async
def get_user_from_token(token_str):
    try:
        validated = AccessToken(token_str)
        user_id = validated["user_id"]
        return User.objects.get(id=user_id)
    except (InvalidToken, TokenError, User.DoesNotExist, KeyError):
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token = params.get("token", [None])[0]

        scope["user"] = await get_user_from_token(token) if token else AnonymousUser()
        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(inner)
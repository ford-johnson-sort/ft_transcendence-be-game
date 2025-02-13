# game/views.py
import jwt
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import GameRoom

@require_POST
def new_game(request):
    token = request.COOKIES.get("ford-johnson-sort")
    if not token:
        return JsonResponse({"result": False, "error": "Missing token"})

    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        current_username = payload.get("username")
        if not current_username:
            return JsonResponse({"result": False, "error": "Invalid token payload"})
    except jwt.PyJWTError:
        return JsonResponse({"result": False, "error": "Invalid token"})

    user1 = request.POST.get("user1")
    user2 = request.POST.get("user2")
    if not user1 or not user2:
        return JsonResponse({"result": False, "error": "Missing user parameters"})
    if user1 == user2:
        return JsonResponse({"result": False, "error": "Duplicate user parameters"})

    # Ensure that the authenticated user is one of the game participants.
    if current_username not in (user1, user2):
        return JsonResponse({
            "result": False,
            "error": "Authenticated user must be one of the game participants"
        })

    # Sort the usernames for consistent ordering, then get or create the GameRoom.
    users = sorted([user1, user2])
    chat_room, created = GameRoom.objects.get_or_create(
        user1=users[0],
        user2=users[1]
    )

    return JsonResponse({
        "result": True,
        "username": current_username,
        "room_uuid": str(chat_room.id)
    })

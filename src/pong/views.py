# game/views.py
import random

import jwt
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q

from .models import GameRoom


@require_POST
def new_game(request):
    # check if user has authenticated
    token = request.COOKIES.get("ford-johnson-sort")
    if not token:
        return JsonResponse({"result": False, "error": "authentication error"})
    try:
        payload = jwt.decode(token, settings.JWT_SECRET,
                             algorithms=[settings.JWT_ALGORITHM])
        current_username = payload.get("username")
        if not current_username:
            raise jwt.PyJWTError
    except jwt.PyJWTError:
        return JsonResponse({"result": False, "error": "authentication error"})

    # check if user has pending game
    g: GameRoom | None = GameRoom.objects.exclude(
        game_status__in=[GameRoom.GameStatus.P1_WIN,
                         GameRoom.GameStatus.P2_WIN]
    ).filter(
        Q(user1=current_username) | Q(user2=current_username)
    ).first()
    if g is not None:
        return JsonResponse({
            'result': False,
            'error': 'You have pending game'
        })

    game_room: GameRoom = GameRoom.objects.filter(
        game_status=GameRoom.GameStatus.WAITING
    ).order_by('pk').first()
    if game_room is None:
        if random.randint(0, 1) == 1:
            game_room = GameRoom(user1=current_username)
        else:
            game_room = GameRoom(user2=current_username)
    else:
        if game_room.user1 is None:
            game_room.user1=current_username
        else:
            game_room.user2=current_username
    game_room.save()

    return JsonResponse({
        "result": True,
        "username": current_username,
        "room_uuid": str(game_room.uuid)
    })

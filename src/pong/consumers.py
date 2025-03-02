# chat/consumers.py
import json
import asyncio

import redis
from django.conf import settings
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async

from .models import GameRoom


GameStatus = GameRoom.GameStatus


class PongGameConsumer(AsyncWebsocketConsumer):
    """Game Consumer for managing game"""
    room_uuid: str
    username: str
    game_room: GameRoom

    async def connect(self):
        """
        Channels library interface for accepting a connection.

        This method sets the following attributes:

        - self.room_uuid (str): The current room's UUID, used as the channel layer ID.
        - self.username (str): The user's nickname.
        - self.game_room (GameRoom): The game room database instance.
        """
        self.room_uuid = self.scope["url_route"]["kwargs"].get("room_uuid")
        self.username = self.scope["url_route"]["kwargs"].get("user")
        if not self.room_uuid or not self.username:
            await self.close()
            return

        # Try to fetch the room from the DB.
        self.game_room: GameRoom = await self.get_game_room(self.room_uuid)
        if not self.game_room:
            # No such room exists; abort connection.
            await self.close()
            return

        # Ensure that the provided username is one of the room's participants.
        if self.username not in (self.game_room.user1, self.game_room.user2):
            await self.close()
            return

        # Join the channel layer group.
        await self.channel_layer.group_add(self.room_uuid, self.channel_name)
        await self.accept()

        # Start game
        await self.pong_wait()
        return

    async def receive(self, text_data=None, bytes_data=None):
        """
        Channels library interface for receiving a message from the user.

        This method handles receiving the paddle movement and passes it to the other player.
        """

        if self.game_room.game_status != GameStatus.RUNNING:
            # error case...
            if self.game_room.game_status in (GameStatus.WAITING, GameStatus.CREATED):
                await self.send(text_data=json.dumps({
                    "type": "wait",
                    "data": None
                }))
            return

        data = json.loads(text_data)
        if 'type' not in data or data['type'] != 'move_paddle':
            # Not expected message
            return
        await self.channel_layer.group_send(
            self.room_uuid,
            {
                "type": "pong.game.move",
                "message": data,
                "username": self.username,
            },
        )
        return

    async def disconnect(self, code):
        """Channels library interface for handling disconnect."""
        # save status, if game was running
        if self.game_room.game_status == GameStatus.RUNNING:
            if self.username == self.game_room.user1:
                winner = self.game_room.user2
            else:
                winner = self.game_room.user1

            await self.channel_layer.group_send(
                self.room_uuid,
                {
                    "type": "pong.end",
                    "winner": winner,
                    "score": await self.get_score(),
                    "reason": "ABANDON"
                },
            )
            await self.save_game_result(GameStatus.P2_WIN if self.p1 else GameStatus.P2_WIN)

        # Remove from group.
        await self.channel_layer.group_discard(self.room_uuid, self.channel_name)

    @database_sync_to_async
    def get_game_room(self, room_uuid) -> GameRoom:
        try:
            room: GameRoom = GameRoom.objects.get(uuid=room_uuid)
            return room
        except GameRoom.DoesNotExist:
            return None

    @database_sync_to_async
    def save_game_result(self, p1_win):
        if p1_win:
            self.game_room.game_status = GameStatus.P1_WIN
        else:
            self.game_room.game_status = GameStatus.P2_WIN
        self.game_room.save()

    @database_sync_to_async
    def pong_wait_db(self) -> GameStatus:
        r = redis.Redis(host=settings.REDIS_HOST)
        join_key = f"game:{self.room_uuid}:join"
        if r.get(join_key) is None:
            r.set(join_key, 1)
        else:
            r.delete(join_key)
            self.game_room.game_status = GameStatus.RUNNING
            self.game_room.save()
        r.close()
        return self.game_room.game_status

    @database_sync_to_async
    def get_score(self):
        # TODO get score from redis
        return (0, 1)

    async def pong_wait(self):
        # check game status and start if needed
        if await self.pong_wait_db() == GameStatus.RUNNING:
            # start worker
            await self.channel_layer.send(
                "pong-serverlogic",
                {
                    "type": "game.logic",
                    "uuid": self.room_uuid
                }
            )
            return
        else:
            await self.send(text_data=json.dumps({
                "type": "wait",
                "data": None
            }))
            return

    async def pong_move(self, event):
        if event['username'] == self.username:
            return
        await self.send(text_data=json.dumps(
            event
        ))

    async def pong_end(self, event):
        await self.send(text_data=json.dumps({
            "type": "end_game",
            "data": {
                "win": event['winner'] == self.username,
                "score": event['score'],
                "reason": event['reason']
            }
        }))
        await self.cleanup()

    async def cleanup(self):
        await self.disconnect()
        await self.channel_layer.group_discard(self.room_uuid, self.channel_name)
        await self.cleanup_db()

    @database_sync_to_async
    def cleanup_db(self):
        r = redis.Redis(host=settings.REDIS_HOST)
        join_key = f"game:{self.room_uuid}:join"
        if r.get(join_key) is not None:
            r.delete(join_key)
        score_key = f"game:{self.room_uuid}:score:p1"
        if r.get(score_key) is not None:
            r.delete(score_key)
        score_key = f"game:{self.room_uuid}:score:p2"
        if r.get(score_key) is not None:
            r.delete(score_key)
        r.close()


class PongServerLogicConsumer(AsyncWebsocketConsumer):
    room_uuid: str
    running: bool

    async def game_logic(self, event):
        self.room_uuid = event['uuid']
        self.running = True
        await self.channel_layer.group_add(self.room_uuid, 'game.pong')

        # # send ``
        # await self.channel_layer.group_send(
        #     self.room_uuid,
        #     {
        #         "type": "pong.game.start",
        #     },
        # )
        while self.running:
            await self.channel_layer.group_send(
                self.room_uuid,
                {
                    "type": "pong.move",
                    "username": 'server',
                    "data": {
                        'a': 0.0,
                        'b': 0.0,
                        'c': 0.0,
                        'd': 0.0,
                    }
                },
            )
            await asyncio.sleep(0.1)

    async def pong_end(self, event):
        self.running = False
        await self.channel_layer.group_discard(self.room_uuid, 'game.pong')

    async def pong_move(self, event):
        import sys
        print(f"SERVERLOGIC: {event}", file=sys.stderr)

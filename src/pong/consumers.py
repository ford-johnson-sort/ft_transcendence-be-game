# chat/consumers.py
import json

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from .models import GameRoom


GameStatus = GameRoom.GameStatus


class PongGameConsumer(AsyncWebsocketConsumer):
    """Game Consumer for managing game"""
    room_uuid: str
    username: str
    game_room: GameRoom
    p1: bool

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
        await self.channel_layer.group_add('game.pong', self.room_uuid)
        await self.accept()

        if self.game_room.game_status == GameStatus.RUNNING:
            await self.channel_layer.group_send(
                self.room_uuid,
                {
                    "type": "pong.start",
                },
            )
        else:
            await self.send(text_data=json.dumps({
                "type": "wait",
                "message": "Please wait for other player to join"
            }))
            # TODO create PongServerLogicConsumer instance for server-side pong

    async def receive(self, text_data=None, bytes_data=None):
        """
        Channels library interface for receiving a message from the user.

        This method handles receiving the paddle movement and passes it to the other player.
        """
        if self.game_room.game_status == GameStatus.WAITING:
            await self.send(text_data=json.dumps({
                "type": "wait",
                "message": "Please wait for other player to join"
            }))
            return
        if self.game_room.game_status != GameStatus.RUNNING:
            await self.close()
            return

        data = json.loads(text_data)
        if data['type'] != 'pong.move':
            # Not expected message
            return
        await self.channel_layer.group_send(
            self.room_uuid,
            {
                "type": "pong.move",
                "message": data,
                "username": self.username,
            },
        )
        return

    async def disconnect(self, code):
        """Channels library interface for handling disconnect."""
        await self.channel_layer.group_send(
            self.room_uuid,
            {
                "type": "pong.end",
                "winner": not self.p1
            },
        )

        # Remove from group.
        await self.save_game_result(GameStatus.P2_WIN if self.p1 else GameStatus.P2_WIN)
        await self.channel_layer.group_discard('game.pong', self.room_uuid)

    @database_sync_to_async
    def get_game_room(self, room_uuid) -> GameRoom:
        try:
            room: GameRoom = GameRoom.objects.get(id=room_uuid)
            users = (room.user1, room.user2)
            self.p1 = self.username == users[0]
            if room.game_status == GameStatus.CREATED:
                room.game_status = GameStatus.WAITING
            elif room.game_status == GameStatus.WAITING:
                room.game_status = GameStatus.RUNNING
            room.save()
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

    async def game_start(self, event):
        # pylint: disable=W0613
        await self.send(text_data=json.dumps({
            "type": "start",
            "p1": self.p1
        }))

    async def game_move(self, event):
        if event['username'] == self.username:
            return
        await self.send(text_data=json.dumps(
            event['message']
        ))

    async def game_end(self, event):
        await self.send(text_data=json.dumps({
            "type": "end",
            "winner": self.p1 == event['winner']
        }))

# chat/consumers.py
import json

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from .models import GameRoom


class PongGameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_uuid = self.scope["url_route"]["kwargs"].get("room_uuid")
        self.username = self.scope["url_route"]["kwargs"].get("user")
        if not self.room_uuid or not self.username:
            await self.close()
            return

        # Try to fetch the room from the DB.
        self.game_room = await self.get_game_room(self.room_uuid)
        if not self.game_room:
            # No such room exists; abort connection.
            await self.close()
            return

        # Ensure that the provided username is one of the room's participants.
        if self.username not in (self.game_room.user1, self.game_room.user2):
            await self.close()
            return

        self.room_group_name = f"chat_{self.room_uuid}"

        # Join the channel layer group.
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        if self.game_room.user1_online and self.game_room.user2_online:
          await self.channel_layer.group_send(
              self.room_group_name,
              {
                  "type": "game_start",
              },
          )
        else:
            await self.send(text_data=json.dumps({
                "type": "wait",
                "message": "Please wait for other player to join"
            }))

    @database_sync_to_async
    def get_game_room(self, room_uuid):
        try:
            room = GameRoom.objects.get(id=room_uuid)
            users = (room.user1, room.user2)
            self.p1 = self.username == users[0]
            if self.p1:
                room.user1_online = True
            else:
                room.user2_online = True
            room.save()
            return room
        except GameRoom.DoesNotExist:
            return None
    @database_sync_to_async
    def delete_game_room(self, room_uuid):
        try:
            room = GameRoom.objects.get(id=room_uuid)
            room.delete()
        except GameRoom.DoesNotExist:
            return

    async def disconnect(self, close_code):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "game_end",
                "winner": not self.p1
            },
        )

        # Remove from group.
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        await self.delete_game_room(self.room_uuid)

    async def receive(self, text_data):
        data = json.loads(text_data)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "game_move",
                "message": data,
                "username": self.username,
            },
        )

    async def game_start(self, event):
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

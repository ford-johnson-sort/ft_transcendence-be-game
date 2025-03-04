# chat/consumers.py
import json
import asyncio
from datetime import datetime

import redis
from django.conf import settings
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.consumer import AsyncConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async

from .models import GameRoom
from .pong import PongSettings, PongGame


GameStatus = GameRoom.GameStatus


class PongGameConsumer(AsyncWebsocketConsumer):
    """Game Consumer for managing game"""
    # informations
    room_uuid: str
    username: str
    game_room: GameRoom
    score: tuple[int]
    p1: bool

    # websocket interfaces

    async def connect(self):
        """
        Channels library interface for accepting a connection.

        This method sets the following attributes:

        - self.room_uuid (str): The current room's UUID, used as the channel layer ID.
        - self.username (str): The user's nickname.
        - self.game_room (GameRoom): The game room database instance.
        - self.game_room (tuple[int]): Temporary score storage. Initialized to (0, 0)
        """
        # initialize
        self.room_uuid = self.scope["url_route"]["kwargs"].get("room_uuid")
        self.username = self.scope["url_route"]["kwargs"].get("user")
        if not self.room_uuid or not self.username:
            # error: required paramaeter is not set
            await self.close()
            return

        # fetch user
        self.game_room: GameRoom = await self.connect_getroom(self.room_uuid)
        if self.game_room is None:
            # error: no room, or user has already joined
            await self.close()
            return

        # Ensure that the provided username is one of the room's participants.
        if self.username not in (self.game_room.user1, self.game_room.user2):
            # error: not one of the users
            await self.close()
            return

        # good to go. accept connection and register in Channels
        await self.channel_layer.group_add(self.room_uuid, self.channel_name)
        await self.accept()

        # Start game
        self.score = (0, 0)
        await self.pong_wait()
        return

    @database_sync_to_async
    def connect_getroom(self, room_uuid) -> GameRoom:
        """
        Helper function for connect. Fetches GameRoom instance from database.
        Blocks request if same user has already joined.
        """
        try:
            r = redis.Redis(host=settings.REDIS_HOST)
            join_key = f"game:{self.room_uuid}:join"
            if r.get(join_key) == self.username.encode():
                r.close()
                return None

            r.close()

            room: GameRoom = GameRoom.objects.get(uuid=room_uuid)
            return room
        except GameRoom.DoesNotExist:
            return None

    async def receive(self, text_data=None, _=None):
        """
        Channels library interface for receiving a message from the user.

        This method handles receiving the paddle movement and passes it to the other player.
        All movements must be processed by server, so pong.move.paddle.controller is called.
        """
        if self.game_room.game_status != GameStatus.RUNNING:
            # error case...
            if self.game_room.game_status in (GameStatus.WAITING, GameStatus.CREATED):
                await self.send(text_data=json.dumps({
                    "type": "WAIT",
                    "data": None
                }))
            return

        try:
            data = json.loads(text_data)
        except json.decoder.JSONDecodeError:
            # malformed request
            return
        if 'type' not in data or data['type'] != 'MOVE_PADDLE':
            # Not expected message
            return
        # call controller
        await self.channel_layer.group_send(
            self.room_uuid,
            {
                "type": "pong.move.paddle.controller",
                "username": self.username,
                "movement": data['data']['movement']
            },
        )
        return

    async def disconnect(self, _):
        """Channels library interface for handling disconnect."""
        # save status, if game was running
        if self.game_room:
            if self.game_room.game_status == GameStatus.RUNNING:
                if self.p1:
                    winner = self.game_room.user2
                else:
                    winner = self.game_room.user1

                await self.channel_layer.group_send(
                    self.room_uuid,
                    {
                        "type": "pong.end.game",
                        "winner": winner,
                        "score": self.score,
                        "reason": "ABANDON"
                    },
                )
                await self.disconnect_savegame(winner)

        # clean dangling informations
        await self.cleanup()
        return

    @database_sync_to_async
    def disconnect_savegame(self, winner: str) -> None:
        """Helper function for disconnect. save game reuslt to database"""
        # save game result to database
        if winner == self.game_room.user1:
            self.game_room.game_status = GameStatus.P1_WIN
        else:
            self.game_room.game_status = GameStatus.P2_WIN
        self.game_room.save()

    # channel event hanlers

    async def pong_wait(self) -> None:
        """Sends `WAIT` event. Start worker if both player is joined."""
        # always send wait message
        await self.send(text_data=json.dumps({
            "type": "WAIT",
            "data": None
        }))
        # check game status and start if needed
        if await self.pong_wait_getcache() == GameStatus.RUNNING:
            # start worker
            await self.channel_layer.send(
                "pong-serverlogic",
                {
                    "type": "game.worker.main",
                    "uuid": self.room_uuid,
                    "users": (self.game_room.user1, self.game_room.user2)
                }
            )
        return

    @database_sync_to_async
    def pong_wait_getcache(self) -> GameStatus:
        """Helper function for pong_wait. Set GameStatus if other player has joined."""
        r = redis.Redis(host=settings.REDIS_HOST)
        join_key = f"game:{self.room_uuid}:join"
        if r.get(join_key) is None:
            r.set(join_key, self.username)
        else:
            r.delete(join_key)
            # change status to running
            self.game_room.game_status = GameStatus.RUNNING
            self.game_room.save()
        r.close()
        return self.game_room.game_status

    async def pong_ready(self, event):
        """Handler for `READY` event. Updates game_room for sync and send command."""
        await sync_to_async(self.game_room.refresh_from_db)()
        self.p1 = self.username == self.game_room.user1

        if self.p1:
            opponent = self.game_room.user2
        else:
            opponent = self.game_room.user1
        await self.send(text_data=json.dumps({
            'type': 'READY',
            'data': {
                'username': self.username,
                'opponent': opponent,
                'delay': event['delay']
            }
        }))
        return

    async def pong_move_paddle(self, event):
        """Handler for `MOVE_PADDLE` event. Inverts opponent movement, sends command."""
        if event['username'] == self.username:
            return
        movement = dict({
            'LEFT_START': 'RIGHT_START',
            'LEFT_END': 'RIGHT_END',
            'RIGHT_START': 'LEFT_START',
            'RIGHT_END': 'LEFT_END',
        }).get(event['movement'])
        if movement is None:
            # illegal movement
            return

        await self.send(text_data=json.dumps({
            'type': 'MOVE_PADDLE',
            'data': {
                'movement': movement,
                'position': event['position']
            }
        }))
        return

    async def pong_move_ball(self, event):
        """Handler for `MOVE_BALL` event. Sends command."""
        await self.send(text_data=json.dumps({
            'type': 'MOVE_BALL',
            'data': {
                'velocity': event['velocity'],
                'position': event['position']
            }
        }))
        return

    async def pong_end_round(self, event):
        """Handler for `END_ROUND` event. Sends command."""
        if self.p1:
            self.score = event['score']
        else:
            self.score = event['score'][::-1]
        await self.send(text_data=json.dumps({
            "type": "END_ROUND",
            "data": {
                "win": event['winner'] == self.username,
                "score": self.score,
            }
        }))
        return

    async def pong_end_game(self, event):
        """Handler for `END_ROUND` event. Sends command, clean connection."""
        await self.send(text_data=json.dumps({
            "type": "END_GAME",
            "data": {
                "win": event['winner'] == self.username,
                "score": event['score'],
                "reason": event['reason']
            }
        }))
        await self.cleanup()
        await self.close()
        return

    # helper funtions

    async def cleanup(self) -> None:
        """Remove this consumer from channel layer, remove cache"""
        if self.room_uuid:
            await self.channel_layer.group_discard(self.room_uuid, self.channel_name)
        await self.cleanup_cache()
        return

    @database_sync_to_async
    def cleanup_cache(self) -> None:
        """Helper function for cleanup. Remove data from database"""
        r = redis.Redis(host=settings.REDIS_HOST)
        join_key = f"game:{self.room_uuid}:join"
        if r.get(join_key) is not None:
            r.delete(join_key)
        r.close()

    # controller interface for Channels message

    async def pong_move_paddle_controller(self, _):
        """dummy interface"""
        return


class PongServerLogicConsumer(AsyncConsumer):
    """Logic Consumer for server-side pong"""
    # channel information
    room_uuid: str
    running: bool
    users: tuple[str]

    # game
    game: PongGame
    score: tuple[int]

    # constants
    DELAY = 3.0
    FPS = 1000.0 / 60.0
    WINS = 5

    # main worker loop

    async def game_worker_main(self, event):
        """Entrypoint for PSLC. Spawns worker with event loop"""
        self.room_uuid = event['uuid']
        self.users = event['users']
        self.running = True
        self.score = (0, 0)

        await self.channel_layer.group_add(self.room_uuid, self.channel_name)
        asyncio.create_task(self.game_worker())
        return

    async def game_worker(self):
        """Main function for worker."""
        while self.running:
            await self.game_init()
            await self.game_round()
            await self.game_result()
            del self.game
            self.game = None
        return

    # simulators

    async def game_init(self) -> None:
        """Creates PongGame with default settings."""
        game_settings = PongSettings(
            field_width_=120,
            field_depth_=170 - 10,
            paddle_width_=18,
            ball_speed_=1.8
        )
        self.game = PongGame(game_settings)
        return

    async def game_round(self) -> None:
        """Simulates pong game and publish event if needed."""
        # start round
        await self.util_send_start()
        await asyncio.sleep(self.DELAY)
        await self.util_send_ball_move(
            velocity=(self.game.ball.velocity.x,
                      self.game.ball.velocity.z),
            position=(self.game.ball.position.x,
                      self.game.ball.position.z)
        )
        lastframe = datetime.now()

        # loop until game ends
        while True:
            delta = ((datetime.now() - lastframe).total_seconds()
                     * 1000.0) / self.FPS

            collision = self.game.frame(delta)
            if self.game.isend():
                break
            if collision:
                await self.util_send_ball_move(
                    velocity=(self.game.ball.velocity.x,
                              self.game.ball.velocity.z),
                    position=(self.game.ball.position.x,
                              self.game.ball.position.z)
                )

            lastframe = datetime.now()
            await asyncio.sleep(max(self.FPS - delta * self.FPS, 0) / 1000)

    async def game_result(self):
        """After round ends, sends END_ROUND message. sends END_GAME if needed."""
        # send END_ROUND message
        if self.game.win == 1:
            self.score = (self.score[0] + 1, self.score[1])
            winner = self.users[0]
        else:
            self.score = (self.score[0], self.score[1] + 1)
            winner = self.users[1]
        await self.util_send_end_round(winner)

        # check finished game
        if self.score[0] >= self.WINS:
            await self.util_send_end_game(self.users[0])
            self.running = False
            return
        if self.score[1] >= self.WINS:
            await self.util_send_end_game(self.users[1])
            self.running = False
            return

    # helper functions

    async def util_send_start(self) -> None:
        """Calls READY message handles."""
        await self.channel_layer.group_send(
            self.room_uuid,
            {
                "type": "pong.ready",
                'delay': self.DELAY
            },
        )

    async def util_send_ball_move(self, velocity: tuple[float], position: tuple[float]) -> None:
        """Calls MOVE_BALL message handles."""
        await self.channel_layer.group_send(
            self.room_uuid,
            {
                "type": "pong.move.ball",
                'velocity': velocity,
                'position': position
            },
        )
        return

    async def util_send_end_round(self, winner: str) -> None:
        """Calls END_ROUND message handles."""
        await self.channel_layer.group_send(
            self.room_uuid,
            {
                "type": "pong.end.round",
                'winner': winner,
                'score': self.score
            },
        )

    async def util_send_end_game(self, winner: str) -> None:
        """Calls END_GAME message handles."""
        await self.channel_layer.group_send(
            self.room_uuid,
            {
                "type": "pong.end.game",
                "winner": winner,
                "score": self.score,
                "reason": "SCORE"
            },
        )

    # channel event hanle interfaces for Channels message

    async def pong_ready(self, _):
        """dummy interface for channel message"""
        return

    async def pong_move_paddle(self, _):
        """dummy interface for channel message"""
        return

    async def pong_move_ball(self, _):
        """dummy interface for channel message"""
        return

    async def pong_end_round(self, _):
        """dummy interface for channel message"""
        return

    async def pong_end_game(self, _):
        """If client disconnects, end worker"""
        self.running = False
        await self.channel_layer.group_discard(self.room_uuid, 'game.pong')

    # controllers

    async def pong_move_paddle_controller(self, event):
        """Update player information, and calls MOVE_PADDLE handlers."""
        if event['username'] == self.users[0]:
            self.game.player1.move(event['movement'])
            position = self.game.player1.position
        else:
            movement = dict({
                'LEFT_START': 'RIGHT_START',
                'LEFT_END': 'RIGHT_END',
                'RIGHT_START': 'LEFT_START',
                'RIGHT_END': 'LEFT_END',
            }).get(event['movement'])
            self.game.player2.move(movement)
            position = self.game.player2.position

        await self.channel_layer.group_send(
            self.room_uuid,
            {
                'type': 'pong.move.paddle',
                'movement': event['movement'],
                'username': event['username'],
                'position': (position.x, position.z)
            })

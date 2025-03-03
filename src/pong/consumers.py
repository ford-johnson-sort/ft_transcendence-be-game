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
        if self.game_room is None:
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
        await self.channel_layer.group_send(
            self.room_uuid,
            {
                "type": "pong.move.paddle.controller",
                "username": self.username,
                "movement": data['data']['movement']
            },
        )
        return

    async def disconnect(self, code):
        """Channels library interface for handling disconnect."""
        # save status, if game was running
        if self.game_room:
            if self.game_room.game_status == GameStatus.RUNNING:
                if self.username == self.game_room.user1:
                    winner = self.game_room.user2
                else:
                    winner = self.game_room.user1

                await self.channel_layer.group_send(
                    self.room_uuid,
                    {
                        "type": "pong.end.game",
                        "winner": winner,
                        "score": await self.get_score(),
                        "reason": "ABANDON"
                    },
                )
                await self.save_game_result(winner)
            await self.cleanup()

        # Remove from group.
        await self.channel_layer.group_discard(self.room_uuid, self.channel_name)

    @database_sync_to_async
    def get_game_room(self, room_uuid) -> GameRoom:
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

    @database_sync_to_async
    def save_game_result(self, winner: str):
        # save game result to database
        if winner == self.game_room.user1:
            self.game_room.game_status = GameStatus.P1_WIN
        else:
            self.game_room.game_status = GameStatus.P2_WIN
        self.game_room.save()

    @database_sync_to_async
    def pong_wait_db(self) -> GameStatus:
        r = redis.Redis(host=settings.REDIS_HOST)
        join_key = f"game:{self.room_uuid}:join"
        if r.get(join_key) is None:
            r.set(join_key, self.username)
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

    # DEBUG
    async def debug(self, event):
        await self.send(text_data=event['message'])

    async def pong_wait(self):
        # always send wait message
        await self.send(text_data=json.dumps({
            "type": "WAIT",
            "data": None
        }))
        # check game status and start if needed
        if await self.pong_wait_db() == GameStatus.RUNNING:
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

    async def pong_ready(self, event):
        if self.game_room.user1 == self.username:
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

    async def pong_move_paddle_controller(self, _):
        """dummy interface"""
        return

    async def pong_move_paddle(self, event):
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

    async def pong_move_ball(self, event):
        await self.send(text_data=json.dumps({
            'type': 'MOVE_BALL',
            'data': {
                'velocity': event['velocity'],
                'position': event['position']
            }
        }))

    async def pong_end_round(self, event):
        await self.send(text_data=json.dumps({
            "type": "END_ROUND",
            "data": {
                "win": event['winner'] == self.username,
                "score": event['score'],
            }
        }))

    async def pong_end_game(self, event):
        await self.send(text_data=json.dumps({
            "type": "END_GAME",
            "data": {
                "win": event['winner'] == self.username,
                "score": event['score'],
                "reason": event['reason']
            }
        }))
        await self.cleanup()
        await self.disconnect(None)

    async def cleanup(self):
        await self.channel_layer.group_discard(self.room_uuid, self.channel_name)
        await self.cleanup_cache()

    @database_sync_to_async
    def cleanup_cache(self):
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


class PongServerLogicConsumer(AsyncConsumer):
    room_uuid: str
    running: bool
    users: tuple[str]

    # game
    game: PongGame
    score: tuple[int]

    # consts
    DELAY = 3.0
    FPS = 1000.0 / 60.0
    WINS = 5

    """main worker loop"""

    async def game_worker_main(self, event):
        self.room_uuid = event['uuid']
        self.users = event['users']
        self.running = True
        self.score = (0, 0)

        await self.channel_layer.group_add(self.room_uuid, self.channel_name)
        asyncio.create_task(self.game_worker())

    async def game_worker(self):
        while self.running:
            await self.game_init()
            await self.game_round()
            await self.game_result()
            del self.game
            self.game = None

    """simulators"""

    async def game_init(self) -> None:
        game_settings = PongSettings(
            FIELD_WIDTH=120,
            FIELD_DEPTH=170,
            PADDLE_WIDTH=18,
            BALL_SPEEDZ=1.8
        )
        self.game = PongGame(game_settings)
        return

    async def game_round(self) -> None:
        # start roun
        await self.util_send_start()
        await asyncio.sleep(self.DELAY)

        lastframe = datetime.now()
        while True:
            delta = ((datetime.now() - lastframe).microseconds /
                     1000.0) / self.FPS
            collision = self.game.frame(delta)
            if self.game.win is not None:
                break
            if collision:
                await self.util_send_ball_move(
                    velocity=(self.game.ball.velocity.x,
                              self.game.ball.velocity.z),
                    position=(self.game.ball.position.x,
                              self.game.ball.position.z)
                )

            lastframe = datetime.now()
            await asyncio.sleep(min(self.FPS - delta, 0))

    async def game_result(self):
        # send END_ROUND message
        if self.game.win:
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
        elif self.score[1] >= self.WINS:
            await self.util_send_end_game(self.users[1])
            self.running = False

    """helper functions"""

    async def util_send_start(self) -> None:
        await self.channel_layer.group_send(
            self.room_uuid,
            {
                "type": "pong.ready",
                'delay': self.DELAY
            },
        )

    async def util_send_ball_move(self, velocity: tuple[float], position: tuple[float]) -> None:
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
        await self.channel_layer.group_send(
            self.room_uuid,
            {
                "type": "pong.end.round",
                'winner': winner,
                'score': self.score
            },
        )

    async def util_send_end_game(self, winner: str) -> None:
        await self.channel_layer.group_send(
            self.room_uuid,
            {
                "type": "pong.end.game",
                "winner": winner,
                "score": self.score,
                "reason": "SCORE"
            },
        )

    """channel event hanlers"""

    async def pong_ready(self, _):
        """dummy interface for channel message"""
        return

    async def pong_move_ball(self, _):
        """dummy interface for channel message"""
        return

    async def pong_end_round(self, _):
        """dummy interface for channel message"""
        return

    async def debug(self, _):
        """dummy interface for channel message"""
        return

    async def pong_end_game(self, event):
        # pylint: disable=W0613
        self.running = False
        await self.channel_layer.group_discard(self.room_uuid, 'game.pong')

    async def pong_move_paddle_controller(self, event):
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

        # debug
        await self.channel_layer.group_send(
            self.room_uuid,
            {
                'type': 'pong.move.paddle',
                'movement': event['movement'],
                'username': event['username'],
                'position': (position.x, position.z)
            })

    async def pong_move_paddle(self, _):
        """dummy interface for channel message"""
        return

from dataclasses import dataclass
import random


def set_range(val: float, lowerbound: float, upperbound: float) -> float:
    return max(lowerbound, min(val, upperbound))


@dataclass
class PongVector:
    x: float = 0.0
    z: float = 0.0


@dataclass
class PongSettings:
    FIELD_WIDTH: int
    FIELD_DEPTH: int
    PADDLE_WIDTH: int
    BALL_SPEEDZ: float


class PongPlayer:
    position: PongVector
    moveleft: bool
    moveright: bool
    # constants
    FIELD_WIDTH: int
    FIELD_DEPTH: int
    PADDLE_WIDTH: int
    PADDLE_OFFSET: int

    def __init__(self, position: PongVector, setting: PongSettings) -> None:
        self.position = position
        self.moveleft = False
        self.moveright = False
        self.FIELD_WIDTH = setting.FIELD_WIDTH
        self.FIELD_DEPTH = setting.FIELD_DEPTH
        self.PADDLE_WIDTH = setting.PADDLE_WIDTH
        self.PADDLE_OFFSET = (setting.FIELD_WIDTH - setting.PADDLE_WIDTH) // 2

    def frame(self, delta: float) -> None:
        # apply movement
        if self.moveleft:
            self.position.x -= 1.5 * delta
        elif self.moveright:
            self.position.x += 1.5 * delta
        # set limit on movement
        self.position.x = set_range(
            self.position.x, -self.PADDLE_OFFSET, self.PADDLE_OFFSET)

    def move(self, action: str) -> None:
        if action == 'LEFT_START':
            self.moveleft = True
            self.moveright = False
        elif action == 'LEFT_END':
            self.moveleft = False
        elif action == 'RIGHT_START':
            self.moveleft = False
            self.moveright = True
        elif action == 'RIGHT_END':
            self.moveright = False


class PongBall:
    position: PongVector
    velocity: PongVector
    # constants
    SPEEDZ: float
    FIELD_WIDTH_HALVES: int
    FIELD_DEPTH_HALVES: int
    PADDLE_WIDTH_HALVES: int

    def __init__(self, velocity: PongVector, setting: PongSettings) -> None:
        self.position = PongVector(0.0, 0.0)
        self.velocity = velocity
        self.SPEEDZ = setting.BALL_SPEEDZ
        self.FIELD_DEPTH_HALVES = setting.FIELD_DEPTH // 2
        self.FIELD_WIDTH_HALVES = setting.FIELD_WIDTH // 2
        self.PADDLE_WIDTH_HALVES = setting.PADDLE_WIDTH // 2

    def frame(self, delta: float, p1: PongPlayer, p2: PongPlayer) -> bool:
        collision = False
        # apply movement
        self.position.x += self.velocity.x * delta
        self.position.z += self.velocity.z * delta

        # handle collision (wall)
        if self.position.x >= self.FIELD_WIDTH_HALVES:
            collision = True
            self.position.x = self.FIELD_WIDTH_HALVES - 1
            self.velocity.x *= -1
        elif self.position.x <= -self.FIELD_WIDTH_HALVES:
            collision = True
            self.position.x = -self.FIELD_WIDTH_HALVES + 1
            self.velocity.x *= -1

        # handle collision (player)
        if self.position.z >= self.FIELD_DEPTH_HALVES:
            collision |= self._check_player_x(p1)
            self.position.z = self.FIELD_DEPTH_HALVES
        elif self.position.z <= -self.FIELD_DEPTH_HALVES:
            collision |= self._check_player_x(p2)
            self.position.z = -self.FIELD_DEPTH_HALVES

        return collision

    def _check_player_x(self, player: PongPlayer):
        range_x = set_range(
            self.position.x,
            player.position.x - self.PADDLE_WIDTH_HALVES,
            player.position.x + self.PADDLE_WIDTH_HALVES
        )
        if range_x != self.position.x:
            return False
        self.velocity.z *= -1
        self.velocity.x = (
            self.position.x - player.position.x
        ) / (self.PADDLE_WIDTH_HALVES + 0.1) * self.SPEEDZ
        return True


class PongGame:
    player1: PongPlayer
    player2: PongPlayer
    ball: PongBall
    win: bool | None

    # constants
    FIELD_WIDTH: int
    FIELD_DEPTH: int
    PADDLE_WIDTH: int
    BALL_SPEEDZ: float

    def __init__(self, setting: PongSettings) -> None:
        self.FIELD_WIDTH = setting.FIELD_WIDTH
        self.FIELD_DEPTH = setting.FIELD_DEPTH
        self.PADDLE_WIDTH = setting.PADDLE_WIDTH
        self.player1 = PongPlayer(PongVector(
            0.0, self.FIELD_DEPTH / 2), setting)
        self.player2 = PongPlayer(PongVector(
            0.0, -self.FIELD_DEPTH / 2), setting)
        self.ball = PongBall(
            PongVector(
                0.0,
                setting.BALL_SPEEDZ if random.randint(
                    0, 1) == 0 else -setting.BALL_SPEEDZ
            ), setting
        )
        self.win = None

    def frame(self, delta: float) -> bool:
        # simulate next frame
        self.player1.frame(delta)
        self.player2.frame(delta)
        collision = self.ball.frame(delta, self.player1, self.player2)
        # speed up ball
        self.ball.velocity.z += 0.001 * delta * \
            (1 if self.ball.velocity.z > 0 else -1)
        # check game end
        # p1 lose
        if self.ball.position.z >= self.FIELD_DEPTH / 2 and not collision:
            self.win = 2
            return True
        # p2 lose
        if self.ball.position.z <= -self.FIELD_DEPTH / 2 and not collision:
            self.win = 1
            return True

        return collision
    
    def isend(self) -> bool:
        return self.win is not None

from dataclasses import dataclass
import random


def set_range(val: float, lowerbound: float, upperbound: float) -> float:
    """Fit val in [lowerbound, upperbound] range"""
    return max(lowerbound, min(val, upperbound))


@dataclass
class PongVector:
    """1x2 vector struct"""
    x: float = 0.0
    z: float = 0.0


@dataclass
class PongSettings:
    """pong settings"""
    field_width_: int
    field_depth_: int
    paddle_width_: int
    ball_speed_: float


@dataclass(init=False)
class PongPlayer:
    """pong player"""
    position: PongVector
    moveleft: bool
    moveright: bool
    # constants
    field_width_: int
    field_depth_: int
    paddle_width_: int
    paddle_offset_: int

    def __init__(self, position: PongVector, setting: PongSettings) -> None:
        self.position = position
        self.moveleft = False
        self.moveright = False
        self.field_width_ = setting.field_width_
        self.field_depth_ = setting.field_depth_
        self.paddle_width_ = setting.paddle_width_
        self.paddle_offset_ = (setting.field_width_ - setting.paddle_width_) // 2

    def frame(self, delta: float) -> None:
        """simulate frame movement"""
        # apply movement
        if self.moveleft:
            self.position.x -= 1.5 * delta
        elif self.moveright:
            self.position.x += 1.5 * delta
        # set limit on movement
        self.position.x = set_range(
            self.position.x, -self.paddle_offset_, self.paddle_offset_)

    def move(self, action: str) -> None:
        """sends movement flag"""
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


@dataclass(init=False)
class PongBall:
    """pong ball"""
    position: PongVector
    velocity: PongVector
    # constants
    speed_: float
    field_width_halves_: int
    field_depth_halves_: int
    paddle_width_halves_: int

    def __init__(self, velocity: PongVector, setting: PongSettings) -> None:
        self.position = PongVector(0.0, 0.0)
        self.velocity = velocity
        self.speed_ = setting.ball_speed_
        self.field_depth_halves_ = setting.field_depth_ // 2
        self.field_width_halves_ = setting.field_width_ // 2
        self.paddle_width_halves_ = setting.paddle_width_ // 2

    def frame(self, delta: float, p1: PongPlayer, p2: PongPlayer) -> bool:
        """calcualte frame movement"""
        collision = False
        # apply movement
        self.position.x += self.velocity.x * delta
        self.position.z += self.velocity.z * delta

        # handle collision (wall)
        if self.position.x >= self.field_width_halves_:
            collision = True
            self.position.x = self.field_width_halves_ - 1
            self.velocity.x *= -1
        elif self.position.x <= -self.field_width_halves_:
            collision = True
            self.position.x = -self.field_width_halves_ + 1
            self.velocity.x *= -1

        # handle collision (player)
        if self.position.z >= self.field_depth_halves_:
            collision |= self._check_player_x(p1)
            self.position.z = self.field_depth_halves_
        elif self.position.z <= -self.field_depth_halves_:
            collision |= self._check_player_x(p2)
            self.position.z = -self.field_depth_halves_

        return collision

    def _check_player_x(self, player: PongPlayer):
        """check player and ball collision, and set ball if collided"""
        range_x = set_range(
            self.position.x,
            player.position.x - self.paddle_width_halves_,
            player.position.x + self.paddle_width_halves_
        )
        if range_x != self.position.x:
            return False
        self.velocity.z *= -1
        self.velocity.x = (
            self.position.x - player.position.x
        ) / (self.paddle_width_halves_ + 0.1) * self.speed_
        return True


class PongGame:
    """pong game"""
    player1: PongPlayer
    player2: PongPlayer
    ball: PongBall
    win: bool | None

    # constants
    field_width_: int
    field_depth_: int
    paddle_width_: int
    ball_speed_: float

    def __init__(self, setting: PongSettings) -> None:
        self.field_width_ = setting.field_width_
        self.field_depth_ = setting.field_depth_
        self.paddle_width_ = setting.paddle_width_
        self.player1 = PongPlayer(PongVector(
            0.0, self.field_depth_ / 2), setting)
        self.player2 = PongPlayer(PongVector(
            0.0, -self.field_depth_ / 2), setting)
        self.ball = PongBall(
            PongVector(
                0.0,
                setting.ball_speed_ if random.randint(
                    0, 1) == 0 else -setting.ball_speed_
            ), setting
        )
        self.win = None

    def frame(self, delta: float) -> bool:
        """simulate frame. returns True if there was collision"""
        # simulate next frame
        self.player1.frame(delta)
        self.player2.frame(delta)
        collision = self.ball.frame(delta, self.player1, self.player2)
        # speed up ball
        self.ball.velocity.z += 0.001 * delta * \
            (1 if self.ball.velocity.z > 0 else -1)
        # check game end
        # p1 lose
        if self.ball.position.z >= self.field_depth_ / 2 and not collision:
            self.win = 2
            return True
        # p2 lose
        if self.ball.position.z <= -self.field_depth_ / 2 and not collision:
            self.win = 1
            return True

        return collision

    def isend(self) -> bool:
        """returns if game has handed"""
        return self.win is not None

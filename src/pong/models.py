# chat/models.py
import uuid

from django.utils.translation import gettext_lazy as _
from django.db import models


class GameRoom(models.Model):
    """match user table"""
    uuid = models.UUIDField(primary_key=False, default=uuid.uuid4, editable=False)
    user1 = models.CharField(max_length=150, default=None, null=True)
    user2 = models.CharField(max_length=150, default=None, null=True)

    class GameStatus(models.TextChoices):
        """enum for saving game status"""
        # pylint: disable=R0901
        WAITING = "WA", _("Waiting for other player")
        CREATED = "CR", _("Game created")
        RUNNING = "RU", _("Game Running")
        P1_WIN = "P1", _("P1 Won")
        P2_WIN = "P2", _("P2 Won")

    game_status = models.CharField(
        max_length=2,
        choices=GameStatus,
        default=GameStatus.WAITING,
    )

    def __str__(self):
        return f"GameRoom({self.uuid}): {self.user1} vs {self.user2}: {self.game_status}"

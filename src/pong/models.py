# chat/models.py
import uuid

from django.utils.translation import gettext_lazy as _
from django.db import models


class GameRoom(models.Model):
    """match user table"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user1 = models.CharField(max_length=150)
    user2 = models.CharField(max_length=150)

    class GameStatus(models.TextChoices):
        """enum for saving game status"""
        # pylint: disable=R0901
        CREATED = "CR", _("Game created")
        WAITING = "WA", _("Waiting for other player")
        RUNNING = "RU", _("Game Running")
        P1_WIN = "P1", _("P1 Won")
        P2_WIN = "P2", _("P2 Won")

    game_status = models.CharField(
        max_length=2,
        choices=GameStatus,
        default=GameStatus.CREATED,
    )

    def __str__(self):
        return f"GameRoom({self.id}): {self.user1} vs {self.user2}: {self.game_status}"

# chat/models.py
import uuid
from django.db import models

class GameRoom(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user1 = models.CharField(max_length=150)
    user1_online = models.BooleanField(default=False)
    user2 = models.CharField(max_length=150)
    user2_online = models.BooleanField(default=False)

    def __str__(self):
        return f"GameRoom({self.id}) between {self.user1} and {self.user2}"

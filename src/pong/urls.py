# chat/urls.py
from django.urls import path
from .views import new_game

urlpatterns = [
    path('new', new_game, name='new_game'),
]

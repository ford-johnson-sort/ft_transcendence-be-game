# mysite/urls.py
from django.urls import include, path

urlpatterns = [
    path("game/pong/", include("pong.urls")),
]

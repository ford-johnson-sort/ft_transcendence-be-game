python3 manage.py makemigrations pong
python3 manage.py migrate

daphne -b 0.0.0.0 -p 8000 be_game.asgi:application
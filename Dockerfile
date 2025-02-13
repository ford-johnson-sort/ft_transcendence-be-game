FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ./src .

CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "be_game.asgi:application"]

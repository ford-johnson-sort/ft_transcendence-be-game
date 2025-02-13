FROM python:3.13-slim

RUN apt update \
  && apt install -y dumb-init
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ./entrypoint.sh /tmp
RUN chmod +x /tmp/entrypoint.sh
COPY ./src .

ENTRYPOINT ["/usr/bin/dumb-init", "--", "/tmp/entrypoint.sh"]

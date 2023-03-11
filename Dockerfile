FROM python:3.8

COPY requirements.txt .

RUN pip3 install -r requirements.txt && \
    rm -f requirements.txt

COPY eruditus /eruditus
COPY .git/refs/heads/master /eruditus/.revision

WORKDIR /eruditus

RUN chown -R nobody:nogroup .

USER nobody

ENTRYPOINT ["python3", "-u", "eruditus.py"]

FROM python:3.10

COPY requirements.txt .

RUN pip3 install -r requirements.txt && \
    rm -f requirements.txt

COPY eruditus /eruditus
COPY .git/refs/heads/master /eruditus/.revision

WORKDIR /eruditus

RUN useradd -m user && \
    chown -R user:user .

USER user

ENTRYPOINT ["python3", "-u", "eruditus.py"]

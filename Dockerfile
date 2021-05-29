FROM python:3.7

RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip3 install -r requirements.txt && \
    rm -f requirements.txt

COPY eruditus /eruditus

WORKDIR /eruditus/

RUN touch /var/log/eruditus.log && \
    chown -R nobody:nogroup . /var/log/eruditus.log

USER nobody

ENTRYPOINT ["python3", "-u", "eruditus.py"]

FROM python:3.7

COPY requirements.txt .

RUN pip3 install -r requirements.txt && \
    rm -f requirements.txt

COPY eruditus /eruditus

WORKDIR /eruditus

RUN chown -R nobody:nogroup .

USER nobody

ENTRYPOINT ["python3", "-u", "eruditus.py"]

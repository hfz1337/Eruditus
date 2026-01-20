FROM python:3.14-bookworm

RUN wget https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb \
    -O packages-microsoft-prod.deb \
    && dpkg -i packages-microsoft-prod.deb \
    && rm packages-microsoft-prod.deb

RUN apt-get update && apt-get install -y dotnet-sdk-8.0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /eruditus

COPY pyproject.toml .

RUN pip3 install . && \
    rm -f pyproject.toml

COPY eruditus .
COPY .git/refs/heads/master .revision

RUN useradd -m user && \
    chown -R user:user .

COPY .ssh /home/user/.ssh/
COPY chat_exporter /usr/bin/
RUN chmod a+x /usr/bin/chat_exporter && \
    chown -R user:user /home/user

USER user

# Prevent caching the subsequent "git clone" layer.
# https://github.com/moby/moby/issues/1996#issuecomment-1152463036
ADD https://postman-echo.com/time/now /etc/builddate
RUN git clone https://github.com/hfz1337/DiscordChatExporter ~/DiscordChatExporter

# ARG CHATLOGS_REPO=git@github.com:username/repo

# RUN git clone --depth=1 $CHATLOGS_REPO ~/chatlogs
# RUN git config --global user.email "eruditus@localhost" && \
#     git config --global user.name "eruditus"

ENTRYPOINT ["python3", "-u", "eruditus.py"]

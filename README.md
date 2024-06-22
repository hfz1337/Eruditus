# Eruditus - CTF helper bot
<p align="center">
        <a href="https://discord.com/developers/docs/interactions/slash-commands"><img src="https://img.shields.io/badge/%2F-Discord%20Slash-blue" alt="Discord Slash Commands"></a>
        <a href="https://github.com/hfz1337/Eruditus/actions"><img src="https://img.shields.io/github/actions/workflow/status/hfz1337/Eruditus/pre-commit.yml?branch=master&logo=github" alt="GitHub Workflow Status"></a>
        <a href="https://github.com/pre-commit/pre-commit"> <img alt="pre-commit" src="https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white&style=flat-square"></a>
</p>
<br/>
<p align="center">
  <img src="https://i.imgur.com/K5mNt37.jpg" alt="Logo" width="200">
  <h3 align="center">Eruditus - CTF helper bot</h3>
</p>

## About
Eruditus is a Discord CTF helper bot built with Python, it was initially designed to be
used internally within the CyberErudites CTF team in order to make team work as efficient
as possible.  
The bot implements a bunch of useful features and uses **Discord's Slash commands** to
make its usage as intuitive as possible.

## Features
### Core functionalities
- Manage channels and their permissions
- Create Discord scheduled events for upocoming CTF competitions
- Track CTFs progress
- Track members' participation in challenges
- Announcements upon solving a challenge
- Flag submission from within the Discord guild

and more.

### Miscellaneous
- Provides a utility to lookup system calls from a specific architecture
- Provides a utility for basic encoding schemes
- Provides a utility for classic ciphers

### Supported platforms
As you already read this bot can interact with the CTF platforms, meaning that you can:
- Submit your flags within the bot
- Observe the leaderboard
- Automatically parse challenges from the platform
- Automatically create team accounts on the platform (or use already existing ones)
- And many more

Currently, Eruditus supports these platforms:
- CTFd
- rCTF

_You can check out our [abstract interfaces](eruditus/lib/platforms/abc.py) if you wish to add support for a new platform_

## Usage
Here's a list of the currently supported commands:
```
/help                                                (Show help about the bot usage)
/search                                              (Search for a topic in the CTF write-ups index)
/request                                             (Request a new feature from the developer)
/report                                              (Send a bug report to the developer)
/intro                                               (Show bot instructions for newcomers)

/ctf createctf                                       (Create a new CTF)
/ctf renamectf                                       (Rename a CTF)
/ctf archivectf                                      (Archive a CTF's channels)
/ctf exportchat                                      (Export CTF chat logs to a static site)
/ctf deletectf                                       (Delete a CTF as well as its channels)
/ctf setprivacy                                      (Toggle CTF privacy between public and private)
/ctf join                                            (Join a specific CTF channels)
/ctf leave                                           (Leave a CTF)
/ctf addcreds                                        (Add credentials for the current CTF)
/ctf showcreds                                       (Show credentials of the current CTF)
/ctf status                                          (Show CTF(s) status)
/ctf workon                                          (Access the private channel associated to the challenge)
/ctf unworkon                                        (Leave the challenge channel)
/ctf solve                                           (Mark a challenge as solved)
/ctf unsolve                                         (Mark a challenge as not solved)
/ctf createchallenge                                 (Create a new challenge)
/ctf renamechallenge                                 (Rename a challenge)
/ctf deletechallenge                                 (Delete a challenge)
/ctf pull                                            (Pull unsolved challenges from the platform)
/ctf submit                                          (Submit a flag to the platform)
/ctf remaining                                       (Show remaining time for the CTF)
/ctf register                                        (Register a team account in the platform)

/syscalls                                            (Show information for a specific syscall)

/ctftime upcoming                                    (Show upcoming CTF competitions)
/ctftime current                                     (Show ongoing CTF competitions)
/ctftime top                                         (Show leaderboard for a specific year)
/ctftime pull                                        (Create events starting in less than a week)
/ctftime setchannel                                  (Set the text channel where CTF reminders will be sent)

/cipher caesar                                       (Caesar cipher)
/cipher rot13                                        (Rot13 cipher)
/cipher atbash                                       (Atbash cipher)

/encoding base64                                     (Base64 encoding/decoding)
/encoding base32                                     (Base32 encoding/decoding)
/encoding binary                                     (Binary encoding/decoding)
/encoding hex                                        (Hex encoding/decoding)
/encoding url                                        (URL encoding/decoding)
```

## Installation

Before proceeding with the installation, you may want to setup a repository to host Discord chat logs for archived CTFs that you no longer want to have on your Discord guild. Follow these instructions if you wish to do so:
1. Create a private GitHub repository to host your chat logs.
2. Clone [this project](https://github.com/hfz1337/discord-oauth2-webapp) into your previously create GitHub repository.
3. Modify line 37 of the [Dockerfile](./Dockerfile) to point to your private GitHub repository that will host the chat logs.
4. Prepare an SSH key pair to access your private GitHub repository, and put the private key under [.ssh/privkey.pem](./.ssh). As for the public key, under your repository settings in the `Deploy keys` section, click on `Add deploy key` and paste your SSH public key (make sure to tick the `Allow write access` box).

The [sample GitHub repository](https://github.com/hfz1337/discord-oauth2-webapp) already has a workflow for publishing the website to Azure App Service, but you're free to host it somewhere else, or simply keep it in the GitHub repository. If you're willing to use Azure, make sure to add the necessary secrets and variables referenced inside the [workflow](https://github.com/hfz1337/discord-oauth2-webapp/blob/main/.github/workflows/publish.yml).

---

Follow the instructions below to deploy the bot:

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Create a new application.
3. Go to the **Bot** pane and add a bot for your application.
4. Enable **Server Members Intent** and **Message Content Intent** under
**Privileged Gateway Intents**.
5. Put your configuration to the `eruditus/.env` file by using the [.env.example](eruditus/.env.example) template.
6. Deploy the bot using `docker-compose up -d --build`.
7. Go to the **OAuth2 URL Generator** pane, tick `bot` and `applications.commands`
under the **Scopes** section, tick `Administrator` under the **Bot Permissions**
section and copy the generated link.
8. Invite your bot to the guild using the generated link.
9. Enjoy.

## Contribution Guidelines
Please consider reading our [Contribution Guidelines](.github/CONTRIBUTING.md) before
making a contribution.

## Contributors
- [@es3n1n](https://github.com/es3n1n)
- [@ouxs-19](https://github.com/ouxs-19)
- [@abdelmaoo](https://github.com/abdelmaoo)

## Credits
This work was inspired from these amazing projects:
- [OTA's Bishop Slack bot](https://github.com/OpenToAllCTF/OTA-Challenge-Bot)
- [NullCTF](https://github.com/NullPxl/NullCTF)

## License
Distributed under the MIT License. See [`LICENSE`](./LICENSE) for more information.

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

## Usage
Here's a list of the currently supported commands:
```
/help                                                (Show help about the bot usage)
/search                                              (Search for a topic in the CTF write-ups index)
/request                                             (Request a new feature from the developer)
/report                                              (Send a bug report to the developer)

/ctf createctf                                       (Create a new CTF)
/ctf renamectf                                       (Rename a CTF)
/ctf archivectf                                      (Archive a CTF's channels)
/ctf deletectf                                       (Delete a CTF as well as its channels)
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
/ctf pull                                            (Pull unsolved challenges from the CTFd platform)
/ctf takenote                                        (Copies the last message into the notes channel)
/ctf submit                                          (Submits a flag to CTFd)
/ctf remaining                                       (Show remaining time for the CTF)
/ctf register                                        (Register a CTFd account)

/syscalls                                            (Show information for a specific syscall)

/chatgpt                                             (Ask OpenAI's ChatGPT a question)

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

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Create a new application.
3. Go to the **Bot** pane and add a bot for your application.
4. Enable **Server Members Intent** and **Message Content Intent** under
**Privileged Gateway Intents**.
5. Put your Discord guild ID and bot token inside the [.env](eruditus/.env) file.
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
- [@ouxs-19](https://github.com/ouxs-19)
- [@abdelmaoo](https://github.com/abdelmaoo)

## Credits
This work was inspired from these amazing projects:
- [OTA's Bishop Slack bot](https://github.com/OpenToAllCTF/OTA-Challenge-Bot)
- [NullCTF](https://github.com/NullPxl/NullCTF)

## License
Distributed under the MIT License. See [`LICENSE`](./LICENSE) for more information.

# Eruditus - CTF helper bot
<p align="center">
        <a href="https://discord.com/developers/docs/interactions/slash-commands"><img src="https://img.shields.io/badge/%2F-Discord%20Slash-blue" alt="Discord Slash Commands"></a>
        <a href="https://github.com/hfz1337/Eruditus/actions"><img src="https://img.shields.io/github/workflow/status/hfz1337/Eruditus/pre-commit?label=master&logo=github" alt="GitHub Workflow Status"></a>
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
- Track CTFtime events and announce them on the server
- Track CTFs progress
- Track members' participation in challenges
- Announcements upon solving a challenge
- Automatic pulling of challenges from CTFd
- Automatic flag submission from within the Discord guild
- Highlighting important notes by moving them to a read-only channel

### Miscellaneous
- Provides a utility to lookup system calls from a specific architecture
- Provides a utility for basic encoding schemes
- Provides a utility for classic ciphers

## Usage
Here's a list of the currently supported commands:
```
/help                                                (Show help about the bot usage)
/request <feature>                                   (Request a new feature from the developer)
/report <bug>                                        (Send a bug report to the developer)
/config [<args>]...                                  (Display or alter configuration specific to the guild)

/ctf createctf <ctf_name>                            (Create a new CTF)
/ctf renamectf <ctf_name>                            (Rename a CTF)
/ctf archivectf <mode> [<ctf_name>]                  (Archive a CTF's channels)
/ctf deletectf [<ctf_name>]                          (Delete a CTF as well as its channels)
/ctf join <ctf_name>                                 (Join a specific CTF channels)
/ctf leave                                           (Leave a CTF)
/ctf addcreds <username> <password> <url>            (Add credentials for the current CTF)
/ctf showcreds                                       (Show credentials of the current CTF)
/ctf status [<ctf_name>]                             (Show CTF(s) status)
/ctf workon <challenge_name>                         (Access the private channel associated to the challenge)
/ctf unworkon [<challenge_name>]                     (Leave the challenge channel)
/ctf solve [<support_member>]...                     (Mark a challenge as solved)
/ctf unsolve                                         (Mark a challenge as not solved)
/ctf createchallenge <name> <category>               (Create a new challenge)
/ctf renamechallenge <new_name> <new_category>       (Rename a challenge)
/ctf deletechallenge [<challenge_name>]              (Delete a challenge)
/ctf pull [<ctfd_url>]                               (Pull unsolved challenges from the CTFd platform)
/ctf takenote <type> <note_format>                   (Copies the last message into the notes channel)
/ctf submit <flag> [<support_member>]...             (Submits a flag to CTFd)

/syscalls show <arch> <syscall name/syscall id>      (Show information for a specific syscall)

/ctftime upcoming [<limit>]                          (Show upcoming CTF competitions)
/ctftime current                                     (Show ongoing CTF competitions)
/ctftime top [<year>]                                (Show leaderboard for a specific year)

/cipher caesar <message> [<key>]                     (Caesar cipher)
/cipher rot13 <message>                              (Rot13 cipher)
/cipher atbash <message>                             (Atbash cipher)

/encoding base64 <encode/decode> <data>              (Base64 encoding/decoding)
/encoding base32 <encode/decode> <data>              (Base32 encoding/decoding)
/encoding binary <encode/decode> <data>              (Binary encoding/decoding)
/encoding hex <encode/decode> <data>                 (Hex encoding/decoding)
/encoding url <encode/decode> <data>                 (URL encoding/decoding)
```

## Installation
### Method 1 - Invite the already hosted bot
Invite the bot to your server using this [link](https://discord.com/api/oauth2/authorize?client_id=848180282174734378&permissions=8&scope=bot%20applications.commands).

### Method 2 - Host your own copy of the bot
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Create a new application.
3. Go to the **Bot** pane and add a bot for your application.
4. Copy the bot's token and paste it in the `docker-compose.yml` file like indicated.
5. Go to the **OAuth2** pane, tick `bot` and `applications.commands` under the **Scopes**
section, tick `Administrator` under the **Bot Permissions** section and copy the
generated link.
6. Deploy the bot by running `docker-compose up -d --build`.
7. Invite your bot to the guild using the link generated in **5**.
8. Enjoy.

## Contribution Guidelines
Please consider reading our [Contribution Guidelines](.github/CONTRIBUTING.md) before
making a contribution.

## Contributors
- [@ouxs-19](https://github.com/ouxs-19)

## Credits
This work was inspired from these amazing projects:
- [OTA's Bishop Slack bot](https://github.com/OpenToAllCTF/OTA-Challenge-Bot)
- [NullCTF](https://github.com/NullPxl/NullCTF)

## License
Distributed under the MIT License. See [`LICENSE`](./LICENSE) for more information.

# Eruditus - CTF helper bot
<br/>
<p align="center">
  <img src="https://i.imgur.com/K5mNt37.jpg" alt="Logo" width="200">
  <h3 align="center">Eruditus - CTF helper bot</h3>
</p>

## About
Eruditus is a Discord CTF helper bot built with Python, it was initially designed to be
used internally within the CyberErudites CTF team in order to make team work as efficient
as possible.

## Features
### Core functionalities
- Manage channels and their permissions
- Track CTFTime events and announce them on the server
- Track CTFs progress
- Track members' participation in challenges
- Announcements upon solving a challenge
- Automatic flag submission from within the Discord guild

### Miscellaneous
- Provides a utility to lookup system calls from a specific architecture
- Provides a utility for basic encoding schemes
- Provides a utility for classic ciphers

## Usage

```
!ctf createctf <ctf_name>                                       (Create a new CTF)
!ctf renamectf <ctf_name>                                       (Rename a CTF)
!ctf archivectf <mode> [<ctf_name>]                             (Archive a CTF's channels)
!ctf deletectf [<ctf_name>]                                     (Delete a CTF as well as its channels)
!ctf join <ctf_name>                                            (Join a specific CTF channels)
!ctf leave                                                      (Leave a CTF)
!ctf addcreds <username> <password> <url>                       (Add credentials for the current CTF)
!ctf showcreds                                                  (Show credentials of the current CTF)
!ctf status [<ctf_name>]                                        (Show CTF(s) status)
!ctf workon <challenge_name>                                    (Access the private channel associated to the challenge)
!ctf unworkon [<challenge_name>]                                (Leave the challenge channel)
!ctf solve [<support_member>]...                                (Mark a challenge as solved)
!ctf unsolve                                                    (Mark a challenge as not solved)
!ctf createchallenge <challenge_name> <challenge_category>      (Create a new challenge)
!ctf renamechallenge <new_name> <new_category>                  (Rename a challenge)
!ctf deletechallenge [<challenge_name>]                         (Delete a challenge)
!ctf pull [<ctfd_url>]                                          (Pull unsolved challenges from the CTFd platform)
!ctf takenote <type> <note_format>                              (Copies the last message into the notes channel)

!syscalls available                                             (Shows the available syscall architectures)
!syscalls show <arch> <syscall name/syscall id>                 (Show information for a specific syscall)

!ctftime upcoming [<limit>]                                     (Show upcoming CTF competitions)
!ctftime current                                                (Show ongoing CTF competitions)
!ctftime top [<year>]                                           (Show leaderboard for a specific year)

!cipher caesar <message> [<key>]                                (Caesar cipher)
!cipher rot13 <message>                                         (Rot13 cipher)
!cipher atbash <message>                                        (Atbash cipher)

!encoding base64 <encode/decode> <data>                         (Base64 encoding/decoding)
!encoding base32 <encode/decode> <data>                         (Base32 encoding/decoding)
!encoding binary <encode/decode> <data>                         (Binary encoding/decoding)
!encoding hex <encode/decode> <data>                            (Hex encoding/decoding)
!encoding url <encode/decode> <data>                            (URL encoding/decoding)

/submit <flag> [<support_member>]...                            (Submits a flag to CTFd)
```

## Installation (brief explanation)
This is a self hosted bot, just set your bot token and guild ID in the docker-compose.yml
file and run `docker-compose up -d --build`.  
In order to use the flag submission Slash command, the usual `bot` scope in the Discord
developer portal is not sufficient, you must also grant the `applications.commands` scope.

## Contribution Guidelines
More information on how to contribute to this project will be provided soon.

## Contributors
- [@ouxs-19](https://github.com/ouxs-19)

## Credits
This work was inspired from these amazing projects:
- [OTA's Bishop Slack bot](https://github.com/OpenToAllCTF/OTA-Challenge-Bot)
- [NullCTF](https://github.com/NullPxl/NullCTF)

## License
Distributed under the MIT License. See [`LICENSE`](./LICENSE) for more information.

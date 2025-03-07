# Sigrok Decoder for Joybus Protocol

Sigrok protocol decoder for the Joybus protocol, used by N64 and GameCube controllers.

Adds Joybus protocol decoding support to [sigrok](https://sigrok.org), [PulseView](https://sigrok.org/wiki/PulseView), [DSView](https://github.com/DreamSourceLab/DSView), and other tools built on `libsigrokdecode`.

## Screenshot

![Screenshot 2025-03-06 at 9 37 19 PM](https://github.com/user-attachments/assets/5c48b36f-75b0-42ae-8f28-35652731533f)

## Installation

### PulseView and sigrok-cli

Copy the `joybus` directory to your local `decoders` directory, creating it if it doesnt exist.

- Linux: `~/.local/share/libsigrokdecode/decoders`
- Windows: `%LOCALAPPDATA%\libsigrokdecode\decoders`

### DSView

Copy the `joybus` directory to the `decoders` directory in the DSView installation directory.

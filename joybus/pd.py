"""Joybus protocol decoder for sigrok.

The Joybus protocol is used for communicating between N64/GameCube controllers and
consoles, over the console's serial interface.

The serial interface (SI) is a half-duplex, asynchronous serial bus using a single,
open-drain line with an external pull-up resistor.

Each bit is transmitted over a fixed period T with an initial low pulse followed by a
high pulse such that a logical “0” is encoded with a low-to-high ratio of 3:1
(3T/4 low, T/4 high) and a logical “1” with a ratio of 1:3 (T/4 low, 3T/4 high).

An GameCube/Wii console sends bits at 200 kHz (a 5µs period):
- Logic 0 pulse:   3.75µs low, 1.25µs high
- Logic 1 pulse:   1.25µs low, 3.75µs high
- Stop bit:        1.25µs low, 3.75µs high (same as logic 1)

OEM wired GameCube controllers reply at 250 kHz (a 4µs period):
- Logic 0 pulse:   3µs low, 1µs high
- Logic 1 pulse:   1µs low, 3µs high
- Stop bit:        2µs low, 2µs high

WaveBird receivers send SI pulses at 225 kHz (a 4.44µs period):
- Logic 0 pulse:   3.33µs low, 1.11µs high
- Logic 1 pulse:   1.11µs low, 3.33µs high
- Stop bit:        2.22µs low, 2.22µs high

Communication:
- Host (console) sends a 1-3 byte command to a device (controller).
- Device responds with a multi-byte response.
- Command and responses are terminated with a stop bit.
"""

import math
import sigrokdecode as srd

# A partial list of Joybus commands
JOYBUS_COMMANDS = {
    0x00: {
        "name": "Info",
        "command_len": 1,
        "response_len": 3,
    },
    0x01: {
        "name": "Controller State",
        "command_len": 1,
        "response_len": 4,
    },
    0x02: {
        "name": "Read Accessory",
        "command_len": 3,
        "response_len": 33,
    },
    0x03: {
        "name": "Write Accessory",
        "command_len": 35,
        "response_len": 1,
    },
    0x04: {
        "name": "Read EEPROM",
        "command_len": 2,
        "response_len": 8,
    },
    0x05: {
        "name": "Write EEPROM",
        "command_len": 10,
        "response_len": 1,
    },
    0x14: {
        "name": "Read GBA",
        "command_len": 3,
        "response_len": 33,
    },
    0x15: {
        "name": "Write GBA",
        "command_len": 35,
        "response_len": 1,
    },
    0x40: {
        "name": "Short Poll",
        "command_len": 3,
        "response_len": 8,
    },
    0x41: {
        "name": "Read Origin",
        "command_len": 1,
        "response_len": 10,
    },
    0x42: {
        "name": "Calibrate",
        "command_len": 3,
        "response_len": 10,
    },
    0x43: {
        "name": "Long Poll",
        "command_len": 3,
        "response_len": 10,
    },
    0x4E: {
        "name": "Fix Device",
        "command_len": 3,
        "response_len": 3,
    },
    0x54: {
        "name": "Keyboard Poll",
        "command_len": 3,
        "response_len": 8,
    },
    0xFF: {
        "name": "Reset",
        "command_len": 1,
        "response_len": 3,
    },
}


class Decoder(srd.Decoder):
    api_version = 3
    id = "joybus"
    name = "Joybus"
    longname = "Joybus (N64/GameCube)"
    desc = "Joybus protocol for N64 and GameCube controllers"
    license = "mit"
    inputs = ["logic"]
    outputs = []
    tags = ["Retro computing"]
    channels = ({"id": "si", "name": "SI", "desc": "SI data line"},)
    optional_channels = ()
    annotations = (
        ("command", "Command"),
        ("command_data_byte", "Command data byte"),
        ("response_data_byte", "Response data byte"),
        ("data_bit", "Data bit"),
        ("stop_bit", "Stop bit"),
        ("error", "Error"),
    )
    annotation_rows = (
        ("bytes", "Data", (0, 1, 2)),
        ("bits", "Bits", (3, 4)),
        ("errors", "Errors", (5,)),
    )

    def __init__(self, **kwargs):
        self.reset()

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def reset(self):
        self.state = "INITIAL"

    def putg(self, ss, es, data):
        self.put(ss, es, self.out_ann, data)

    def put_command(self, ss, es, command):
        """Output a command annotation."""
        if command in JOYBUS_COMMANDS:
            command_name = JOYBUS_COMMANDS[command]["name"]
        else:
            command_name = f"0x{command:02X}"

        self.putg(ss, es, [0, [f"Command: {command_name}", f"{command_name}"]])

    def put_command_data(self, ss, es, data):
        """Output a command byte annotation."""
        self.putg(ss, es, [1, [f"Data: 0x{data:02X}", f"0x{data:02X}", f"{data:02X}"]])

    def put_response_data(self, ss, es, data):
        """Output a response byte annotation."""
        self.putg(ss, es, [2, [f"Data: 0x{data:02X}", f"0x{data:02X}", f"{data:02X}"]])

    def put_bit(self, ss, es, bit):
        """Output a bit annotation."""
        self.putg(ss, es, [3, [str(bit)]])

    def put_stop_bit(self, ss, es):
        """Output a stop bit annotation."""
        self.putg(ss, es, [4, ["Stop", "S"]])

    def read_bit(self):
        """Read a single bit from the SI line and return its value."""
        bit_start = self.samplenum

        # Wait for the low pulse to end
        (si,) = self.wait([{0: "r"}, {"skip": self.bit_timeout_samples}])
        if si == 0:
            raise Exception("Bit timeout")

        # Measure the duration of the low pulse
        low_duration = self.samplenum - bit_start

        # Determine the bit value based on the duration of the low pulse
        bit_value = 0 if low_duration > self.bit_midpoint_samples else 1

        # Wait for the high pulse to end
        (si,) = self.wait([{0: "f"}, {"skip": self.bit_timeout_samples}])
        if si == 1:
            raise Exception("Bit timeout")

        # Add bit annotation
        self.put_bit(bit_start, self.samplenum, bit_value)

        return bit_value

    def read_byte(self):
        """Read a byte from the SI line and return its value."""
        byte_start = self.samplenum
        byte_value = 0

        # Read 8 bits to form a byte
        for _ in range(8):
            bit_value = self.read_bit()
            byte_value = (byte_value << 1) | bit_value

        return byte_start, byte_value

    def read_stop_bit(self, width=None):
        """Read a stop bit from the SI line."""
        stop_start = self.samplenum
        self.wait({0: "r"})

        if width is None:
            self.put_stop_bit(stop_start, self.samplenum)
        else:
            self.put_stop_bit(stop_start, stop_start + width)

    def decode(self):
        if not self.samplerate:
            raise Exception("Cannot decode without samplerate.")

        while True:
            if self.state == "INITIAL":
                # Wait for bus to be high for at least 100us before moving to idle state
                # This is to ensure we don't start decoding in the middle of a command/response
                self.wait({0: "h"})
                (si,) = self.wait([{0: "f"}, {"skip": self.idle_min_samples}])
                if si == 1:
                    self.state = "IDLE"

            elif self.state == "IDLE":
                # Wait for a falling edge to indicate the start of a new command
                self.wait({0: "f"})
                self.state = "COMMAND"

            elif self.state == "COMMAND":
                command_start = self.samplenum
                try:
                    # Read the command byte
                    command_start, command = self.read_byte()
                    self.put_command(command_start, self.samplenum, command)

                    if command not in JOYBUS_COMMANDS:
                        raise Exception("Unknown command")

                    # Read command data bytes if needed
                    for _ in range(1, JOYBUS_COMMANDS[command]["command_len"]):
                        start, byte = self.read_byte()
                        self.put_command_data(start, self.samplenum, byte)

                    # Read command stop bit
                    self.read_stop_bit(self.bit_command_samples)

                    # Wait for the response
                    (si,) = self.wait(
                        [{0: "f"}, {"skip": self.response_timeout_samples}]
                    )
                    if si == 1:
                        raise Exception("Response timeout")

                    # Read response bytes
                    for _ in range(JOYBUS_COMMANDS[command]["response_len"]):
                        start, byte = self.read_byte()
                        self.put_response_data(start, self.samplenum, byte)

                    # Read response stop bit
                    self.read_stop_bit(self.bit_response_samples)

                    # Return to idle state
                    self.state = "IDLE"
                except Exception as e:
                    self.putg(
                        command_start,
                        self.samplenum,
                        [5, [str(e)]],
                    )
                    self.state = "INITIAL"

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

            # Update timing parameters based on the samplerate
            def us_to_samples(us):
                return math.floor(self.samplerate / 1000000 * us)

            self.idle_min_samples = us_to_samples(100)
            self.bit_midpoint_samples = us_to_samples(2.5)
            self.bit_command_samples = us_to_samples(5)
            self.bit_response_samples = us_to_samples(4)
            self.bit_timeout_samples = us_to_samples(10)
            self.response_timeout_samples = us_to_samples(50)

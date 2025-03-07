"""SI (Serial Interface) protocol

SI is a half-duplex, asynchronous serial protocol using a single, open-drain
line with an external pull-up resistor.

A GameCube/Wii console sends SI messages at 200 kHz (a 5µs period):
- Logic 0 pulse:   3.75µs low, 1.25µs high
- Logic 1 pulse:   1.25µs low, 3.75µs high
- Stop bit:        1.25µs low, 3.75µs high (same as logic 1)

GameCube controllers reply with SI pulses at 250 kHz (a 4µs period):
- Logic 0 pulse:   3µs low, 1µs high
- Logic 1 pulse:   1µs low, 3µs high
- Stop bit:        2µs low, 2µs high

Communication:
- Host (console) sends a 1-3 byte command to a device (controller).
- Device responds with a multi-byte response.
- Command and responses are terminated with a stop bit.
"""

import math
import sigrokdecode as srd

SI_COMMANDS = {
    0x00: {
        "name": "Info",
        "command_len": 1,
        "response_len": 3,
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
    0xFF: {
        "name": "Reset",
        "command_len": 1,
        "response_len": 3,
    },
}


class Decoder(srd.Decoder):
    api_version = 3
    id = "si"
    name = "SI"
    longname = "SI"
    desc = "N64 and GameCube controller protocol"
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
    )
    annotation_rows = (
        ("bytes", "Data", (0, 1, 2)),
        ("bits", "Bits", (3, 4)),
    )

    def __init__(self, **kwargs):
        self.reset()

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def reset(self):
        self.state = "INITIAL"

    def put_command(self, start, command):
        """Output a command annotation."""
        if command in SI_COMMANDS:
            command_name = SI_COMMANDS[command]["name"]
        else:
            command_name = f"0x{command:02X}"

        self.put(start, self.samplenum, self.out_ann, [0, [f"Command: {command_name}"]])

    def put_command_data(self, start, data):
        """Output a command byte annotation."""
        self.put(start, self.samplenum, self.out_ann, [1, [f"Data: 0x{data:02X}"]])

    def put_response_data(self, start, data):
        """Output a response byte annotation."""
        self.put(start, self.samplenum, self.out_ann, [2, [f"Data: 0x{data:02X}"]])

    def put_bit(self, start, bit):
        """Output a bit annotation."""
        self.put(start, self.samplenum, self.out_ann, [3, [str(bit)]])

    def put_stop_bit(self, start):
        """Output a stop bit annotation."""
        self.put(start, self.samplenum, self.out_ann, [4, ["S"]])

    def read_bit(self):
        """Read a single bit from the SI line and return its value."""
        bit_start = self.samplenum

        # Measure the duration of the low pulse
        self.wait({0: "r"})
        low_duration = self.samplenum - bit_start

        # Determine the bit value based on the duration of the low pulse
        bit_value = 0 if low_duration > self.low_midpoint_samples else 1

        # Wait for the high pulse to end
        self.wait({0: "f"})

        # Add bit annotation
        self.put_bit(bit_start, bit_value)

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

    def read_stop_bit(self):
        """Read a stop bit from the SI line."""
        stop_start = self.samplenum
        self.wait({0: "r"})
        self.put_stop_bit(stop_start)

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
                # Read the command byte
                command_start, command = self.read_byte()
                self.put_command(command_start, command)

                # Read command data bytes if needed
                if command in SI_COMMANDS:
                    for _ in range(1, SI_COMMANDS[command]["command_len"]):
                        data_start, data_byte = self.read_byte()
                        self.put_command_data(data_start, data_byte)

                # Read command stop bit
                self.read_stop_bit()

                # Wait for the response
                self.wait({0: "f"})

                # Read response bytes
                if command in SI_COMMANDS:
                    for _ in range(SI_COMMANDS[command]["response_len"]):
                        resp_start, resp_byte = self.read_byte()
                        self.put_response_data(resp_start, resp_byte)

                # Read response stop bit
                self.read_stop_bit()

                # Return to idle state
                self.state = "IDLE"

    def us_to_samples(self, us):
        return math.floor(self.samplerate / 1000000 * us)

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

            # Update timing parameters based on the samplerate
            self.idle_min_samples = self.us_to_samples(100)
            self.low_midpoint_samples = self.us_to_samples(2.5)

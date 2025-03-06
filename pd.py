import sigrokdecode as srd

# SI (Serial Interface) protocol.
#
# SI is a half-duplex, asynchronous serial protocol using a single, open-drain
# line with an external pull-up resistor.
#
# A GameCube/Wii console sends SI messages at 200 kHz (a 5µs period):
# - Logic 0 pulse:   3.75µs low, 1.25µs high
# - Logic 1 pulse:   1.25µs low, 3.75µs high
# - Stop bit:        1.25µs low, 3.75µs high (same as logic 1)
#
# GameCube controllers reply with SI pulses at 250 kHz (a 4µs period):
# - Logic 0 pulse:   3µs low, 1µs high
# - Logic 1 pulse:   1µs low, 3µs high
# - Stop bit:        2µs low, 2µs high
#
# Communication:
# - Host (console) sends a 1-3 byte command to a device (controller).
# - Device responds with a multi-byte response.
# - Command and responses are terminated with a stop bit.
#
# Commands:
# - 0x00 - Get device type and status
# - 0xFF - Reset device


class Decoder(srd.Decoder):
    api_version = 3
    id = "si"
    name = "SI"
    longname = "SI"
    desc = "N64 and GameCube controller protocol"
    license = "gplv2+"
    inputs = ["logic"]
    outputs = []
    tags = ["Retro computing"]
    channels = ({"id": "si", "name": "SI", "desc": "SI data line"},)
    optional_channels = ()
    annotations = (("bit", "Data bit"),)
    annotation_rows = (("bits", "Bits", (0,)),)

    def __init__(self, **kwargs):
        self.reset()

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def reset(self):
        self.state = "INITIAL"

    def decode(self):
        while True:
            if self.state == "INITIAL":
                print("State is INITIAL")
                # Wait for bus to be high for at least 100us
                # When this matches, move into the idle state
                self.wait({0: "h"})
                pins = self.wait([{0: "f"}, {"skip": int(self.samplerate * 0.0001)}])
                if pins[0] == 1:
                    self.state = "IDLE"
            elif self.state == "IDLE":
                print("State is IDLE")
                # Wait for a falling edge to indicate the start of a new command from the host
                # When this matches, move into the command state
                self.wait({0: "f"})
                self.state = "COMMAND"
            elif self.state == "COMMAND":
                print("State is COMMAND")
                # Add a bit annotation for each bit
                # Detect the stop bit (either by timing or counting)
                # When the stop bit is detected, move into the response state
                self.w
            elif self.state == "RESPONSE":
                # Add a bit annotation for each bit
                # Detect the stop bit (either by timing or counting)
                # When the stop bit is detected, move into the idle state

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value
            self.idle_min_samples = int(self.samplerate * 0.0001)  # 100µs of high idle
            self.host_bit0_low_samples = int(self.samplerate * 0.00375)

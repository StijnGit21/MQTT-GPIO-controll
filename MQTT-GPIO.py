import paho.mqtt.client as mqtt
import RPi.GPIO as GPIO
import time
import logging
import json
import os
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from .env file
load_dotenv()

class RGBDriver:
    """
    A class to control the Open-Smart RGB LED Strip Driver Module.
    """
    def __init__(self, clk_pin, data_pin):
        self.clk_pin = clk_pin
        self.data_pin = data_pin
        try:
            GPIO.setmode(GPIO.BCM)  # Set GPIO mode to BCM
            GPIO.setup(self.data_pin, GPIO.OUT)  # Set data pin as output
            GPIO.setup(self.clk_pin, GPIO.OUT)  # Set clock pin as output
            GPIO.output(self.data_pin, GPIO.LOW)  # Initialize data pin to LOW
            GPIO.output(self.clk_pin, GPIO.LOW)  # Initialize clock pin to LOW
            logging.info("GPIO pins initialized successfully.")
        except Exception as e:
            logging.error(f"Failed to initialize GPIO pins: {e}")

    def begin(self):
        """Initialize transmission by sending 32 zero bits."""
        self.send_32_zero()

    def end(self):
        """End transmission by sending 32 zero bits."""
        self.send_32_zero()

    def clk_rise(self):
        """Generate a clock pulse."""
        try:
            GPIO.output(self.clk_pin, GPIO.LOW)
            time.sleep(0.00002)  # 20µs delay
            GPIO.output(self.clk_pin, GPIO.HIGH)
            time.sleep(0.00002)  # 20µs delay
        except Exception as e:
            logging.error(f"Failed to generate clock pulse: {e}")

    def send_32_zero(self):
        """Send 32 zero bits."""
        for _ in range(32):
            GPIO.output(self.data_pin, GPIO.LOW)
            self.clk_rise()  # Raise the clock signal

    def take_anti_code(self, data):
        """Calculate the anti-code for the given data."""
        tmp = 0
        if (data & 0x80) == 0:  # Check bit 7
            tmp |= 0x02
        if (data & 0x40) == 0:  # Check bit 6
            tmp |= 0x01
        return tmp

    def dat_send(self, dx):
        """Send data to the LED strip."""
        for i in range(32):
            GPIO.output(self.data_pin, GPIO.HIGH if (dx & 0x80000000) else GPIO.LOW)
            dx <<= 1
            self.clk_rise()  # Raise the clock signal

    def set_color(self, red, green, blue):
        """Set the color of the LED strip."""
        dx = 0
        dx |= (0x03 << 30)
        dx |= (self.take_anti_code(blue) << 28)
        dx |= (self.take_anti_code(green) << 26)
        dx |= (self.take_anti_code(red) << 24)
        dx |= (blue << 16)
        dx |= (green << 8)
        dx |= red
        self.begin()  # Initialize transmission
        self.dat_send(dx)  # Send data
        self.end()    # End transmission
        logging.info(f"Color set: R:{red}, G:{green}, B:{blue}")

# MQTT Configuration using environment variables
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT"))
MQTT_TOPIC_COLOR = os.getenv("MQTT_TOPIC_COLOR")
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASS")

# Home Assistant auto-discovery configuration
HA_DISCOVERY_TOPIC = "homeassistant/light/rgb_led_strip/config"

# Load the discovery template from the JSON file
with open('config/ha_discovery_template.json', 'r') as file:
    ha_discovery_template = json.load(file)

# Replace placeholders with actual values
ha_discovery_template['command_topic'] = MQTT_TOPIC_COLOR
#ha_discovery_template['state_topic'] = MQTT_TOPIC_STATE  # Add this line if you have a state topic


# Load MQTT messages from the JSON file
with open('config/mqtt_messages.json', 'r') as file:
    mqtt_messages = json.load(file)

# Hardware pins on pi
clk_pin = 17  # BCM 17 (Physical Pin 11)
data_pin = 18  # BCM 18 (Physical Pin 12)

driver = RGBDriver(clk_pin, data_pin)

# MQTT Callbacks
def on_connect(client, userdata, flags, rc):
    """Callback when the client connects to the MQTT broker."""
    if rc == 0:
        logging.info("Connected to MQTT Broker!")
        client.subscribe(MQTT_TOPIC_COLOR)
        # Publish Home Assistant discovery message
        client.publish(HA_DISCOVERY_TOPIC, json.dumps(ha_discovery_template), retain=True)
    else:
        logging.error(f"Connection failed with code: {rc}")

def on_message(client, userdata, message):
    """Callback when a message is received from the MQTT broker."""
    payload = message.payload.decode()
    logging.info(f"Received on {message.topic}: {payload}")

    if message.topic == MQTT_TOPIC_COLOR:
        try:
            r, g, b = map(int, payload.split(','))
            driver.set_color(r, g, b)  # begin/end already handled in set_color()
        except ValueError:
            logging.error(f"Invalid color format: {payload}")

def publish_color_command(client, red, green, blue):
    """Publish a color command using the template from the JSON file."""
    message_template = mqtt_messages['color_command']
    topic = message_template['topic']
    payload = message_template['payload'].replace("{{r}}", str(red)).replace("{{g}}", str(green)).replace("{{b}}", str(blue))
    client.publish(topic, payload)

# Start MQTT Client
client = mqtt.Client()
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.on_connect = on_connect
client.on_message = on_message

try:
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()
    logging.info("RGB driver ready. Waiting for commands...")
    while True:
        time.sleep(1)
except Exception as e:
    logging.error(f"MQTT connection error: {e}")
finally:
    logging.info("Shutting down...")
    driver.end()
    GPIO.cleanup()
    client.loop_stop()

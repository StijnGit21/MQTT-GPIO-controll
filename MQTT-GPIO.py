import paho.mqtt.client as mqtt
import RPi.GPIO as GPIO
import time
from dotenv import load_dotenv
import os
import json

print("Starting script...")

# Load environment variables from .env file
load_dotenv()

#to controll the Open-Smart RGB LED Strip Driver Module
class RGBDriver:
    def __init__(self, clk_pin, data_pin):
        self.clk_pin = clk_pin
        self.data_pin = data_pin
        GPIO.setmode(GPIO.BCM)  # Set GPIO mode to BCM
        GPIO.setup(self.data_pin, GPIO.OUT)  # Set data pin as output
        GPIO.setup(self.clk_pin, GPIO.OUT)  # Set clock pin as output
        GPIO.output(self.data_pin, GPIO.LOW)  # Initialize data pin to LOW
        GPIO.output(self.clk_pin, GPIO.LOW)  # Initialize clock pin to LOW

    def begin(self):
        self.send_32_zero()  # Send 32 zero bits to start the transmission

    def end(self):
        self.send_32_zero()  # Send 32 zero bits to end the transmission

    def clk_rise(self):
        GPIO.output(self.clk_pin, GPIO.LOW)
        time.sleep(0.00002)  # 20µs delay
        GPIO.output(self.clk_pin, GPIO.HIGH)
        time.sleep(0.00002)  # 20µs delay

    def send_32_zero(self):
        for _ in range(32):
            GPIO.output(self.data_pin, GPIO.LOW)
            self.clk_rise()  # Raise the clock signal

    def take_anti_code(self, data):
        tmp = 0
        if (data & 0x80) == 0:  # Check bit 7
            tmp |= 0x02
        if (data & 0x40) == 0:  # Check bit 6
            tmp |= 0x01
        return tmp

    def dat_send(self, dx):
        for i in range(32):
            GPIO.output(self.data_pin, GPIO.HIGH if (dx & 0x80000000) else GPIO.LOW)
            dx <<= 1
            self.clk_rise()  # Raise the clock signal

    def set_color(self, red, green, blue):
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
        print(f"Color set: R:{red}, G:{green}, B:{blue}")

# MQTT Configuration
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT"))
MQTT_TOPIC_COLOR = os.getenv("MQTT_TOPIC_COLOR")
MQTT_TOPIC_DISCOVERY = os.getenv("MQTT_TOPIC_DISCOVERY")
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASS")
DEVICE_ID = os.getenv("DEVICE_ID")
DEVICE_NAME = os.getenv("DEVICE_NAME")

# Hardware pins on pi
clk_pin = 17  # BCM 17 (Physical Pin 11)
data_pin = 18  # BCM 18 (Physical Pin 12)

driver = RGBDriver(clk_pin, data_pin)

# MQTT Callbacks
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Broker!") #initial connection
        # Autodiscovery payload
        config_payload = {
            "name": DEVICE_NAME,
            "unique_id": DEVICE_ID,
            "command_topic": MQTT_TOPIC_COLOR,
            "rgb_command_topic": MQTT_TOPIC_COLOR,
            "schema": "json",
            "brightness": False,
            "device": {
                "identifiers": [DEVICE_ID],
                "name": DEVICE_NAME,
                "manufacturer": "Open-Smart"
            }
        }
        client.publish(MQTT_TOPIC_DISCOVERY, json.dumps(config_payload), retain=True)
        client.subscribe(MQTT_TOPIC_COLOR)
    else:
        print(f"Connection failed: {rc}")

def on_message(client, userdata, message):
    try:
        payload = json.loads(message.payload)
        r = payload.get("r", payload.get("red", 0))
        g = payload.get("g", payload.get("green", 0))
        b = payload.get("b", payload.get("blue", 0))
        driver.set_color(r, g, b)
    except json.JSONDecodeError:
        # Fallback to comma-separated format
        try:
            r, g, b = map(int, message.payload.decode().split(','))
            driver.set_color(r, g, b)
        except:
            print(f"Invalid payload: {message.payload}")

# Initialize MQTT client
client = mqtt.Client(client_id=f"rgb_driver_{DEVICE_ID}")  # Unique client ID
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.on_connect = on_connect
client.on_message = on_message

client.will_set(MQTT_TOPIC_DISCOVERY, payload=None, qos=0, retain=True)  # Cleanup on disconnect

try:
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()
    print("RGB driver ready. Waiting for commands...")
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Shutting down...")
    driver.end()
    GPIO.cleanup()
    client.loop_stop()
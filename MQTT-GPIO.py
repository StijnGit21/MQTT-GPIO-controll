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
MQTT_TOPIC_STATE = os.getenv("MQTT_TOPIC_STATE", "home/rgb_strip/state")
MQTT_TOPIC_COMMAND = os.getenv("MQTT_TOPIC_COMMAND", "home/rgb_strip/command")
MQTT_TOPIC_DISCOVERY = os.getenv("MQTT_TOPIC_DISCOVERY")
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASS")
DEVICE_ID = os.getenv("DEVICE_ID")
DEVICE_NAME = os.getenv("DEVICE_NAME")

# Hardware pins on pi
clk_pin = 17  # BCM 17 (Physical Pin 11)
data_pin = 18  # BCM 18 (Physical Pin 12)

driver = RGBDriver(clk_pin, data_pin)

# State tracking
current_state = "OFF"
current_color = (0, 0, 0)

def update_state(new_state, color=None):
    global current_state, current_color
    current_state = new_state
    if color:
        current_color = color
    client.publish(MQTT_TOPIC_STATE, json.dumps({
        "state": current_state,
        "color": {
            "r": current_color[0],
            "g": current_color[1],
            "b": current_color[2]
        }
    }), retain=True)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Broker!")
        config_payload = {
            "name": DEVICE_NAME,
            "unique_id": DEVICE_ID,
            "command_topic": MQTT_TOPIC_COMMAND,
            "rgb_command_topic": MQTT_TOPIC_COLOR,
            "state_topic": MQTT_TOPIC_STATE,
            "schema": "json",
            "brightness": False,
            "optimistic": False,
            "payload_on": "ON",
            "payload_off": "OFF",
            "device": {
                "identifiers": [DEVICE_ID],
                "name": DEVICE_NAME,
                "manufacturer": "Open-Smart"
            }
        }
        client.publish(MQTT_TOPIC_DISCOVERY, json.dumps(config_payload), retain=True)
        client.subscribe(MQTT_TOPIC_COMMAND)
        client.subscribe(MQTT_TOPIC_COLOR)
        update_state("OFF")  # Initial state

def on_message(client, userdata, msg):
    if msg.topic == MQTT_TOPIC_COMMAND:
        handle_power_command(msg.payload.decode())
    elif msg.topic == MQTT_TOPIC_COLOR:
        handle_color_command(msg.payload)

def handle_power_command(payload):
    if payload == "ON":
        driver.set_color(*current_color)
        update_state("ON")
    elif payload == "OFF":
        driver.set_color(0, 0, 0)
        update_state("OFF")

def handle_color_command(payload):
    try:
        color_data = json.loads(payload)
        r = max(0, min(255, color_data.get("r", color_data.get("red", 0))))
        g = max(0, min(255, color_data.get("g", color_data.get("green", 0))))
        b = max(0, min(255, color_data.get("b", color_data.get("blue", 0))))
        
        driver.set_color(r, g, b)
        if current_state == "OFF":
            update_state("ON", (r, g, b))
        else:
            update_state(current_state, (r, g, b))
    except json.JSONDecodeError:
        try:
            parts = list(map(int, payload.decode().split(',')))
            r = max(0, min(255, parts[0]))
            g = max(0, min(255, parts[1]))
            b = max(0, min(255, parts[2]))
            driver.set_color(r, g, b)
            update_state("ON", (r, g, b))
        except:
            print(f"Invalid color payload: {payload}")

client = mqtt.Client(client_id=f"rgb_driver_{DEVICE_ID}")
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.on_connect = on_connect
client.on_message = on_message

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
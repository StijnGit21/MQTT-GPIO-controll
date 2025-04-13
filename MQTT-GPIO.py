import paho.mqtt.client as mqtt
import RPi.GPIO as GPIO
import time
from dotenv import load_dotenv
import os

print("Starting script...")

# Load environment variables from .env
load_dotenv()

class RGBDriver:
    def __init__(self, clk_pin, data_pin):
        self.clk_pin = clk_pin
        self.data_pin = data_pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.data_pin, GPIO.OUT)
        GPIO.setup(self.clk_pin, GPIO.OUT)
        GPIO.output(self.data_pin, GPIO.LOW)
        GPIO.output(self.clk_pin, GPIO.LOW)

    def begin(self):
        self.send_32_zero()

    def end(self):
        self.send_32_zero()

    def clk_rise(self):
        GPIO.output(self.clk_pin, GPIO.LOW)
        time.sleep(0.00002)  # 20µs delay
        GPIO.output(self.clk_pin, GPIO.HIGH)
        time.sleep(0.00002)  # 20µs delay

    def send_32_zero(self):
        for _ in range(32):
            GPIO.output(self.data_pin, GPIO.LOW)
            self.clk_rise()

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
            self.clk_rise()

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
        self.dat_send(dx)
        self.end()    # End transmission
        print(f"Color set: R:{red}, G:{green}, B:{blue}")

# MQTT Configuration using env vars
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT"))
MQTT_TOPIC_COLOR = os.getenv("MQTT_TOPIC_COLOR")
MQTT_TOPIC_FAN = os.getenv("MQTT_TOPIC_FAN")
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASS")

# Hardware Setup
clk_pin = 17  # BCM 17 (Physical Pin 11)
data_pin = 18  # BCM 18 (Physical Pin 12)
fan_pin = 14   # BCM 14 (Physical Pin 8)

driver = RGBDriver(clk_pin, data_pin)
GPIO.setup(fan_pin, GPIO.OUT)
GPIO.output(fan_pin, GPIO.LOW)

# MQTT Callbacks
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Broker!")
        client.subscribe(MQTT_TOPIC_COLOR)
        client.subscribe(MQTT_TOPIC_FAN)
    else:
        print(f"Connection failed with code {rc}")

def on_message(client, userdata, message):
    payload = message.payload.decode()
    print(f"Received on {message.topic}: {payload}")
    
    if message.topic == MQTT_TOPIC_COLOR:
        try:
            r, g, b = map(int, payload.split(','))
            driver.set_color(r, g, b)  # begin/end already handled in set_color()
        except ValueError:
            print(f"Invalid color format: {payload}")
    
    elif message.topic == MQTT_TOPIC_FAN:
        if payload.lower() == "on":
            GPIO.output(fan_pin, GPIO.HIGH)
            print("Fan ON")
        elif payload.lower() == "off":
            GPIO.output(fan_pin, GPIO.LOW)
            print("Fan OFF")

# Start MQTT Client
client = mqtt.Client()
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.on_connect = on_connect
client.on_message = on_message

client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

try:
    print("RGB driver ready. Waiting for commands...")
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Shutting down...")
    driver.end()
    GPIO.cleanup()
    client.loop_stop()
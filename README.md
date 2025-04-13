# MQTT-GPIO-Control

This project enables you to control an LED strip from a Raspberry Pi using the Open-Smart RGB LED Strip Driver Module via MQTT.

## Table of Contents

1. [Credentials](#credentials)
2. [Libraries Needed](#libraries-needed)
3. [Wiring the Module](#wiring-the-module)
4. [Usage](#usage)

## Credentials

Create a `.env` file in the project root directory with your MQTT credentials. An example can be found in `secrets.env.example`. Your `.env` file should look like this:

```
MQTT_BROKER=your_broker_address
MQTT_PORT=your_broker_port
MQTT_TOPIC_COLOR=your_topic
MQTT_USER=your_username
MQTT_PASS=your_password
```

## Libraries Needed

This code relies on several libraries, which you need to install using `pip`:

- **MQTT Library**:
  ```bash
  pip install paho-mqtt
  ```

- **Raspberry Pi GPIO Library**:
  ```bash
  pip install RPi.GPIO
  ```

- **Dotenv Library**:
  ```bash
  pip install python-dotenv
  ```

You can install all the libraries at once with:
```bash
pip install paho-mqtt RPi.GPIO python-dotenv
```

## Wiring the Module

To control the LED strip, you need to connect the Open-Smart RGB LED Strip Driver Module to the Raspberry Pi's GPIO pins. Follow these steps:

1. **Identify the Pins**:
   - **CIN Pin (CLK)**: BCM 17 (Physical Pin 11)
   - **DIN Pin (Data)**: BCM 18 (Physical Pin 12)

2. **Connect the Wires**:
   - Connect the **CIN pin** to the CLK pin on the Raspberry Pi.
   - Connect the **DIN pin** to the Data pin on the Raspberry Pi.
   - Connect the **GND** of the module to any GND pin on the Raspberry Pi.
   - Connect the **5V** of the module to the 5V pin on the Raspberry Pi.

3. **Power the LED Strip**:
   - Use the barrel jack on the driver to power the LED strip according to its specifications.

## Usage

Use an MQTT client to publish color commands to the topic specified in your `.env` file. The payload should be in the format `R,G,B` (e.g., `255,0,0` for red).
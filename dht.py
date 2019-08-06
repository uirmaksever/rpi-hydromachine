import Adafruit_DHT
import RPi.GPIO as GPIO
import time
from datetime import datetime
from flask import Flask

app = Flask(__name__)

dht_pin = 4
dht_sensor = Adafruit_DHT.DHT22


def get_dht():
	humidity, temperature = Adafruit_DHT.read_retry(dht_sensor, dht_pin)
	print("Humidity ", humidity, " - Temperature: ", temperature)
	return humidity, temperature


# 		1,	2,	3,	4,	5,	6,	7,	8
pins = [14,	15,	18,	23,	24,	25,	8,	7]

GPIO.setmode(GPIO.BCM)

# Start by turning of all relays
for i in pins:
	GPIO.setup(i, GPIO.OUT)
	GPIO.setup(i, GPIO.HIGH)

@app.route('/relay/<int:relay_pin>')
def get_relay_state(relay_pin):
	current_state = GPIO.input(relay_pin)
	payload = {
		"current_state": current_state,
		"timestamp": datetime.timestamp(datetime.now())
	}
	return str(current_state)


@app.route('/relay/<int:relay_pin>/<int:state>')	
def set_relay(relay_pin, state):
	original_state = get_relay_state(relay_pin)
	if state not in [0,1,"0","1"]:
		return "error"
	
	GPIO.setmode(GPIO.BCM)
	GPIO.setup(relay_pin, GPIO.OUT)
	GPIO.output(relay_pin, state)
	print("Relay {} has been set to {}".format(relay_pin, state))
	payload = {
		"relay": relay_pin,
		"original_state": original_state,
		"changed_state": state,
		"changed_state_confirm": get_relay_state(relay_pin),
		"event_timestamp": datetime.timestamp(datetime.now())
	}
	return payload

@app.route('/relay/<int:relay_pin>/switch')
def switch_relay(relay_pin):
	original_state = get_relay_state(relay_pin)
	# This thing does not work
	reverse_state = not original_state
	
	set_relay(relay_pin, reverse_state)
	payload = {
		"relay": relay_pin,
		"original_state": original_state,
		"changed_state": reverse_state,
		"changed_state_confirm": get_relay_state(relay_pin),
		"timestamp": datetime.timestamp(datetime.now())
	}
	return str(not original_state)


@app.route('/playtime')
def playtime():
	for j in [0, 1]:
		for i in pins:			
			set_relay(i, j)
			time.sleep(1)
	return "Playtime done. Hope you enjoyed it."


@app.route('/temp')
def temp():
	data = get_dht()[1]
	payload = {
		"temperature": data,
		"timestamp": datetime.timestamp(datetime.now())
	}
	return payload

@app.route('/humi')
def humi():
	data = get_dht()[0]
	payload = {
		"humidity": data,
		"timestamp": datetime.timestamp(datetime.now())
	}
	return payload

if __name__ == "__main__":
	get_dht()
	app.run(host='0.0.0.0')


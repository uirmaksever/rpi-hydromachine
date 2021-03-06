import Adafruit_DHT
import RPi.GPIO as GPIO
import time
import datetime
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
import paho.mqtt.client as mqtt
import json

# Declare instances of flask and apscheduler. Apscheduler responsible
# from time dependent tasks such as switching relays at certain time
scheduler = BackgroundScheduler(timezone="Asia/Istanbul")

## CONFIG
# Settings such as light open and close times, sensor pins etc
# TODO!: Take those settings to a json file
DEFAULT_OPENING_STATE = GPIO.LOW
# Default settings relay for lighting

# OPEN_TIME = "15:35"
# CLOSE_TIME = "15:34"
# LIGHT_PINS = [1, 2, 3]
open_close_time_json_filename = "open_close_time.json"
def get_settings():
	with open(open_close_time_json_filename) as time_file:
		time_json = json.loads(time_file.read())
		print(time_json)
		return time_json

dht_pin = 4
dht_sensor = Adafruit_DHT.DHT22


# Get measurements from dht sensor. It gives temp and humidity levels
# TODO!: DHT is just some type of custom sensor. Create a class of
# custom sensor and make it available for other future sensors
def get_dht():
	humidity, temperature = Adafruit_DHT.read_retry(dht_sensor, dht_pin)
	print("Humidity ", humidity, " - Temperature: ", temperature)
	return humidity, temperature

# Gives current time to any asking function
def get_timestamp():
	return datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
	
# Setting for pin layout between relay board and pi
# 		1,	2,	3,	4,	5,	6,	7,	8
pins = [14,	15,	18,	23,	24,	25,	8,	7]
pins = {
		1: 14,
		2: 15,
		3: 18,
		4: 23,
		5: 24,
		6: 25,
		7: 8,
		8: 7,
		}
GPIO.setmode(GPIO.BCM)

# Start by turning off all relays
for i in pins.values():
	GPIO.setup(i, GPIO.OUT)
	GPIO.setup(i, DEFAULT_OPENING_STATE)

# Returns the current relay state info
def get_relay_state(relay_pin):
	current_state = GPIO.input(pins[relay_pin])
	payload = {
		"relay_id": relay_pin,
		"current_state": current_state,
		"timestamp": get_timestamp()
	}
	return json.dumps(payload)

# Changes the relay state. You should provide 0 or 1 as state	
def set_relay(relay_pin, state):
	original_state = get_relay_state(relay_pin)
	if state not in [0,1,"0","1"]:
		return "error"

	GPIO.setmode(GPIO.BCM)
	print("Relay {} has been set to {}".format(relay_pin, state))
	GPIO.setup(pins[relay_pin], GPIO.OUT)

	GPIO.output(pins[relay_pin], state)

	payload = {
		"relay": relay_pin,
		"original_state": original_state,
		"changed_state": state,
		"changed_state_confirm": get_relay_state(relay_pin),
		"event_timestamp": get_timestamp()
	}
	return json.dumps(payload)

# Switches the relay based on current state
# This thing does not work
def switch_relay(relay_pin):
	original_state = get_relay_state(relay_pin)
	reverse_state = not original_state	
	print(original_state, reverse_state)

	set_relay(relay_pin, reverse_state)
	payload = {
		"relay": relay_pin,
		"original_state": original_state,
		"changed_state": reverse_state,
		"changed_state_confirm": get_relay_state(relay_pin),
		"timestamp": get_timestamp()
	}
	return json.dumps(payload)

# For fun and testing the physical connections. Iteratively opens and 
# closes all relays

def playtime():
	for j in [0, 1]:
		for i in pins:			
			set_relay(i, j)
			time.sleep(1)
	return "Playtime done. Hope you enjoyed it."

# Returns relay state info for all relays. Iterates over pins dict and
# asks for state for eah of them
def get_relay_states():
	states = {}
	for pin in pins.keys():
		state = get_relay_state(pin)
		states[str(pin)] = state
	# states["timestamp"] = get_timestamp()
	print(states)
	return json.dumps(states)

# Saves given key value to json file
def update_time_json(key_, value_):
	time_json[key_] = value_
	print("SETTINGS FILE UPDATED - {}:{}".format(key_, value_))
	with open(open_close_time_json_filename, "w") as time_file:
		time_file.write(json.dumps(time_json, sort_keys=True, indent=4))
	return time_json
	
# Returns only temperature data
def temp():
	data = get_dht()[1]
	payload = {
		"temperature": data,
		"timestamp": get_timestamp()
	}
	return json.dumps(payload)

# Returns only humidity data
def humi():
	data = get_dht()[0]
	payload = {
		"humidity": data,
		"timestamp": get_timestamp()
	}
	return json.dumps(payload)


def check_open_close_time():
	now = datetime.datetime.now()
	# Get settings from json file
	settings = get_settings()
	# Split hours and minutes
	open_time_set = settings["open_time"].split(":")
	close_time_set = settings["close_time"].split(":")
	# We are comparing time against today
	open_time = now.replace(hour=int(open_time_set[0]), minute=int(open_time_set[1]), second=0)
	close_time = now.replace(hour=int(close_time_set[0]), minute=int(close_time_set[1]), second=0)
	# Check if current time is within specified interval
	if (now > open_time) and (now < close_time):
		print("Light is open now")
		print(open_time, ">", now, ">", close_time)
		# Iterate over designated light pins and open them
		for light_pin in settings["light_pins"]:
			set_relay(int(light_pin), 0)
	else:
		print("Close time")
		print(now, "<", open_time)
		# Close light pins
		for light_pin in settings["light_pins"]:
			set_relay(int(light_pin), 1)
	time.sleep(1)
scheduler.add_job(func=check_open_close_time, trigger="interval", seconds=60)

### MQTT PART START ###

# Subscribed topics for pi to listen to
topics_to_subscribe = get_settings()["subscribed_topics"]

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
	print("Connected with result code "+str(rc))

	# Subscribing in on_connect() means that if we lose the connection and
	# reconnect then subscriptions will be renewed.

	for topic in topics_to_subscribe:
		client.subscribe(topic)
		print("[MQTT] Connected to {}.".format(topic))

# This is the part calls for relevant function to take action based on request
# Each if statement looks for the msg topic and contains code block to call for
# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
	print("[MQTT] {} | Payload: {}".format(msg.topic, str(msg.payload)))
	
	# Opens the relay
	if msg.topic == "relay/on":
		relay_pin = int(msg.payload.decode())
		relay_on = set_relay(relay_pin, 0)
		print("[MQTT] Relay is on: ", relay_pin)
		client.publish("relay_state/{}".format(relay_pin), 0)
		return relay_on
		
	# Closes the relay
	if msg.topic == "relay/off":
		relay_pin = int(msg.payload.decode())
		relay_off = set_relay(relay_pin, 1)
		# TODO!: Write a function called notify that both prints debug
		# msg to stdout and to an MQTT topic at the same time
		print("[MQTT] Relay is off: ", relay_pin)
		client.publish("relay_state/{}".format(relay_pin), 1)
		return relay_off
		
	# Relay state get switched. Currently does
	if msg.topic == "relay/switch":
		relay_pin = int(msg.payload.decode())
		relay_switch = switch_relay(relay_pin)
		print("[MQTT] Relay switched: {}".format(str(relay_pin)))
		return relay_switch
	
	# Returns the current relay state
	if msg.topic == "relay/get":
		relay_pin = int(msg.payload.decode())
		relay_state = get_relay_state(relay_pin)
		client.publish("relay_state/{}".format(relay_pin), relay_state)
		print("[MQTT] Relay {} | State: {}".format(
												str(relay_pin),
												str(relay_state)))
		return relay_state
	
	# Returns all relay states
	if msg.topic == "relays":
		relay_states = get_relay_states()
		client.publish("relays_res", relay_states)
	
	# Runs playtime
	if msg.topic == "rpi/playtime":
		print("PLAYTIME")
		play = playtime()
		client.publish("rpi/playtime_res", play)
	
	# Returns current humi value 
	if msg.topic == "weather/humidity":
		humidity = str(humi())
		client.publish("weather/humidity_res", humidity)
	
	# Returns current temp value
	if msg.topic == "weather/temperature":
		temperature = str(temp())
		client.publish("weather/temperature_res", temperature)
	
	# Sets the open time for light pins
	# Syntax for this msg is [time_input, relay_input] 
	
	# Since mqtt msgs are not stored, open_time should be set every time
	# after a pi reboot. If this message is not available on the mqtt 
	# server, it falls to hard coded open_time in this script.
	# It is recommended that once open_time changes, print it to a file 
	# and read at startup 
	if msg.topic == "settings/time/open_time":
		user_input = msg.payload.decode()
		print(user_input)
		confirmed_time = datetime.datetime.strptime(user_input, "%H:%M")
		print("Open time added or changed: {}".format(user_input))
		update_time_json("open_time", user_input)

	# Sets the close time for light pins
	# Syntax for this msg is [time_input, relay_input]
	if msg.topic == "settings/time/close_time":
		user_input = msg.payload.decode()
		print("Open time added or changed: {}".format(user_input))
		#~ time_input = user_input[0]
		#~ relay_id = user_input[1]
		#~ confirmed_time = datetime.datetime.strptime(time_input, "%H:%M")
		#~ print(scheduler.add_job(id="close_time",
						#~ func=set_relay,
						#~ args=[int(relay_id),1],
						#~ replace_existing=True,
						#~ trigger="cron",
						#~ hour=confirmed_time.hour,
						#~ minute=confirmed_time.minute)
						#~ )
		update_time_json("close_time", user_input)

		
	if msg.topic == "settings/light_pins":
		user_input = msg.payload.decode()
		# List comes as str, converting it to literal by json library
		light_pins_list = json.loads(user_input)
		update_time_json("light_pins", light_pins_list)

		
	# Returns all existing jobs
	if msg.topic == "jobs":
		print("Getting scheduled jobs work")
		jobs = get_scheduled_jobs()
		client.publish("jobs_res", str(jobs))


# Returns all existing jobs in cron
def get_scheduled_jobs():
	job_list = []
	for job in scheduler.get_jobs():
		job_dict = {
			"job_id": job.id,
			"job_next_run": job.next_run_time.strftime("%d-%m-%Y %H:%m"),
			"called_function": job.name
		}
		#~ print("name: %s, trigger: %s, next run: %s, handler: %s" % (
		#~ job.name, job.trigger, job.next_run_time, job.func))
		job_list.append(job_dict)
		print(job_dict)
	jobs_list_json = json.dumps(job_list)
	print(jobs_list_json)
	return jobs_list_json
	


# This function periodically called for updating temp, humi and relay state values
def schedule_periodic_info():
	humidity = str(humi())
	client.publish("weather/humidity_res", humidity)	
	temperature = str(temp())
	client.publish("weather/temperature_res", temperature)
	relay_states = get_relay_states()
	client.publish("relays_res", relay_states)
scheduler.add_job(func=schedule_periodic_info, trigger="interval", seconds=60)

# MQTT connection settings
# TODO!: Containing auth info in code is dangerous. Split it into another
# file and don't forget to exclude the file in .gitignore
MQTT_HOST = "farmer.cloudmqtt.com"
MQTT_PORT = 10280
MQTT_CLIENT_USERNAME = "emxojmmk"
MQTT_CLIENT_PASSWORD = "A6eATnW1njMR"

client = mqtt.Client(client_id="rpi")
client.username_pw_set(username= MQTT_CLIENT_USERNAME, password= MQTT_CLIENT_PASSWORD)
client.on_connect = on_connect
client.on_message = on_message

client.connect(MQTT_HOST, MQTT_PORT, 60)




if __name__ == "__main__":
	get_dht()
	scheduler.start()
	while True:
		client.loop()





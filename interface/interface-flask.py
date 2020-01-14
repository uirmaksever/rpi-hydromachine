from flask import Flask, request, render_template
from flask_mqtt import Mqtt
from flask_socketio import SocketIO, emit
from flask_debugtoolbar import DebugToolbarExtension
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'araba123'
app.config['MQTT_BROKER_URL'] = 'farmer.cloudmqtt.com'
app.config['MQTT_BROKER_PORT'] = 10280
app.config['MQTT_USERNAME'] = 'emxojmmk'
app.config['MQTT_PASSWORD'] = 'A6eATnW1njMR'
app.config['MQTT_REFRESH_TIME'] = 1.0  # refresh time in seconds
app.config['MQTT_TLS_ENABLED'] = False
mqtt = Mqtt(app)
socketio = SocketIO(app)
toolbar = DebugToolbarExtension(app)


# Subscribed topics for pi to listen to
topics_to_subscribe = [
    "weather/#",
    "rpi/#",
    "relays/#",
    "relays_res",
    "relay/#",
    "settings/time/#",
    "settings/light_pins",
    "jobs"
]
relays = list(range(1,9))


@mqtt.on_connect()
def handle_connect(client, userdata, flags, rc):
    for topic in topics_to_subscribe:
        mqtt.subscribe(topic)



@mqtt.on_message()
def handle_mqtt_message(client, userdata, message):
    data = dict(
        topic=message.topic,
        payload=message.payload.decode()
    )

@mqtt.on_topic("relays_res")
def handle_relay_states(client, userdata, message):
    print(message.payload.decode())
    relay_states = message.payload.decode()

    socketio.emit("relay_states", relay_states, broadcast=True)
    print("Relays message: {}".format(message.payload.decode()), type(message.payload.decode()))
    return relay_states


@socketio.on("relay_state_change")
def relay_state_changed(message):
    print(message["who"], message["data"])
    if message["data"] is False:
        mqtt.publish("relay/off", message["who"])
    elif message["data"] is True:
        mqtt.publish("relay/on", message["who"])
    else:
        pass
    mqtt.publish("relays")
    emit('update value', message, broadcast=True)

@app.route("/")
def index():
    print(relays)
    context = {"relays": relays}
    mqtt.publish('relays/1')

    return render_template("mqtt/relays.html", context=context)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, use_reloader=False, debug=True)
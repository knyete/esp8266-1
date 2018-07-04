import time
from datetime import datetime
import json
import paho.mqtt.client as MQTTClient
from uuid import getnode

from announce_config import config


class AnnounceController:
    MQTT_BROKER = config['broker']
    MQTT_SUB = config['topic_root']
    MQTT_APP = config['topic_app']
    MQTT_SYS = config['topic_sys']
    DEVICE_FILE = 'devices.json'

    def __init__(self):
        self.mqtt_sub_app = ''.join([self.MQTT_SUB, '/', self.MQTT_APP])
        self.mqtt_sub_sys = ''.join([self.MQTT_SUB, '/', self.MQTT_SYS])

        self.mqtt = self.init_mqtt()
        self.device_map = {}
        self.load_devices()

    def init_mqtt(self):
        client = MQTTClient.Client(self.get_mac())
        client.on_message = self.mqtt_process_sub
        client.will_set(self.mqtt_sub_sys, 'OOPS - app controller crashed!')
        time.sleep(0.1)
        client.connect(self.MQTT_BROKER)
        client.subscribe(self.mqtt_sub_app)
        client.subscribe(self.mqtt_sub_sys)
        return client

    def mqtt_process_sub(self, client, userdata, msg):
        channel = msg.topic
        payload = msg.payload.decode("utf-8")
        print("{}: {}".format(channel, payload))

        data = json.loads(payload)

        channel_group = channel.split('/')[-1]
        if channel_group == 'notify':
            mac = data['mac']
            mqtt_pub = ''.join([self.MQTT_SUB, '/', mac])
            if 'cmd' in data:
                if data['cmd'] == 'HELP':
                    self.mqtt.publish(mqtt_pub, '{"led":"ON"}')
                elif data['cmd'] == 'CANCEL':
                    self.mqtt.publish(mqtt_pub, '{"led":"OFF"}')
        elif channel_group == 'system':
            mac = data['mac']
            mqtt_pub = ''.join([self.MQTT_SUB, '/', mac])
            if 'cmd' in data:
                # Handle RTC update requests
                if data['cmd'] == 'RTC':
                    self.mqtt.publish(mqtt_pub, ''.join(['{"time":"', self.get_time(), '"}']))

                # Handle device name requests
                elif data['cmd'] == 'DEVICE_ADD':
                    self.device_map[data['device_mac']] = data['device_name']
                    self.save_devices()
                elif data['cmd'] == 'DEVICE_DEL':
                    if data['device_mac'] in self.device_map:
                        del self.device_map[data['device_mac']]
                        self.save_devices()
                elif data['cmd'] == 'DEVICE_GET':
                    if data['device_mac'] in self.device_map:
                        self.mqtt.publish(mqtt_pub, ''.join(['{"device_mac":"', data['device_mac'], '", "device_name":"', self.device_map[data['device_mac']], '"}']))
                    else:
                        self.mqtt.publish(mqtt_pub, ''.join(['{"device_mac":"', data['device_mac'], '", "device_name":"', data['device_mac'], '"}']))
                elif data['cmd'] == 'DEVICE_GET_ALL':
                    devices = str(self.device_map)[1:-1]
                    self.mqtt.publish(mqtt_pub, ''.join(['{"devices":"', devices, '"}']))
                    # reconstitute dictionary with   d=ast.literal_eval(''.join(['{', devices, '}']))
                elif data['cmd'] == 'DEVICE_RESET':
                    self.device_map = {}
                    self.save_devices()
                    devices = str(self.device_map)[1:-1]
                    self.mqtt.publish(mqtt_pub, ''.join(['{"devices":"', devices, '"}']))
        else:
            print("Unknown topic: '{}'".format(channel))

    @staticmethod
    def get_mac():
        mac_hex = hex(getnode())[2:]
        mac = ':'.join(mac_hex[i: i + 2] for i in range(0, 11, 2)).upper()
        return mac

    @staticmethod
    def get_time():
        t = datetime.now()
        (dt, micro) = t.strftime('%Y:%m:%d:%H:%M:%S/%f').split('/')
        (ms, us) = str(int(micro) / 1000).split('.')
        return ''.join([dt, ':', ms, ':', us])

    def load_devices(self):
        try:
            with open(self.DEVICE_FILE) as f:
                self.device_map = json.load(f)
        except FileNotFoundError:
            self.device_map = {}

    def save_devices(self):
        data = json.dumps(self.device_map)
        with open(self.DEVICE_FILE, "w") as f:
            f.write(data)

    def start(self):
        print('Listening for {}...'.format(self.mqtt_sub_app))
        print('Listening for {}...'.format(self.mqtt_sub_sys))
        self.mqtt.loop_start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.mqtt.loop_stop()
            self.mqtt.disconnect()


if __name__ == '__main__':
    announce = AnnounceController()
    announce.start()


# TODO: Create UI for monitoring, manual updates, and button config
# TODO: add mqtt security
# TODO: jsonify pubs rather than string building

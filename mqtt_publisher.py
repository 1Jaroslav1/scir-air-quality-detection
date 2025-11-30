import time
import json
import ssl
from datetime import datetime
import paho.mqtt.client as mqtt


class AirQualityMQTTPublisher:
    def __init__(self, config):
        self.broker_host = config['broker']
        self.broker_port = config['port']
        self.username = config['username']
        self.password = config['password']
        self.use_tls = config['use_tls']
        self.client_id = config['client_id']
        self.topics = config['topics']
        self.connected = False

        self.client = mqtt.Client(
            client_id=self.client_id,
            clean_session=True,
            protocol=mqtt.MQTTv311
        )

        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_publish = self.on_publish
 
        self.client.username_pw_set(username=self.username, password=self.password)

        if self.use_tls:
            self.client.tls_set(
                ca_certs=config.get('ca_cert', "/etc/mosquitto/certs/ca.crt"),
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLSv1_2
            )

        self.client.will_set(
            self.topics['availability'],
            payload="offline",
            qos=1,
            retain=True
        )
    
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"✓ Connected to MQTT: {self.broker_host}:{self.broker_port}")
            self.connected = True
            self.client.publish(
                self.topics['availability'],
                payload="online",
                qos=1,
                retain=True
            )
        else:
            print(f"✗ MQTT connection error. Code: {rc}")
            self.connected = False
    
    def on_disconnect(self, client, userdata, rc):
        self.connected = False
        if rc != 0:
            print(f"⚠ Unexpected MQTT disconnection. Code: {rc}")
    
    def on_publish(self, client, userdata, mid):
        pass
    
    def connect(self, retry_attempts=5, retry_delay=5):
        for attempt in range(retry_attempts):
            try:
                print(f"Connecting to MQTT ({attempt + 1}/{retry_attempts})...")
                self.client.connect(self.broker_host, self.broker_port, keepalive=60)
                self.client.loop_start()
 
                timeout = 10
                start_time = time.time()
                while not self.connected and (time.time() - start_time) < timeout:
                    time.sleep(0.1)
                
                if self.connected:
                    return True
                    
            except Exception as e:
                print(f"✗ MQTT connection error: {e}")
            
            if attempt < retry_attempts - 1:
                print(f"Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
        
        return False
    
    def disconnect(self):
        if self.connected:
            self.client.publish(
                self.topics['availability'],
                payload="offline",
                qos=1,
                retain=True
            )
        self.client.loop_stop()
        self.client.disconnect()
    
    def publish(self, topic, value, unit="", status="", qos=1, retain=True):
        if not self.connected:
            print("⚠ No MQTT connection. Skipping publish.")
            return False
        
        timestamp = datetime.now().isoformat()

        payload = {
            'value': value,
            'timestamp': timestamp
        }
        
        if unit:
            payload['unit'] = unit
        if status:
            payload['status'] = status
        
        try:
            result = self.client.publish(
                topic,
                json.dumps(payload),
                qos=qos,
                retain=retain
            )
            
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                print(f"⚠ Publish error to {topic}: {result.rc}")
                return False
            
            return True
            
        except Exception as e:
            print(f"✗ Exception during publish: {e}")
            return False
    
    def publish_status(self, message):
        if self.connected:
            payload = json.dumps({
                'message': message,
                'timestamp': datetime.now().isoformat()
            })
            self.client.publish(self.topics['status'], payload, qos=1, retain=False)
    
    def publish_sensor_data(self, bme_data=None, mq7_data=None):
        if not self.connected:
            return

        if bme_data:
            self.publish(self.topics['temperature'], bme_data['temperature'], unit="°C")
            self.publish(self.topics['humidity'], bme_data['humidity'], unit="%")
            self.publish(self.topics['pressure'], bme_data['pressure'], unit="hPa")
            self.publish(self.topics['gas_resistance'], bme_data['gas_resistance'], unit="Ω")
            self.publish(self.topics['air_quality_iaq'], bme_data['iaq'], unit="IAQ")
            self.publish(self.topics['air_quality_category'], bme_data['iaq_category'], unit="")

        if mq7_data:
            self.publish(self.topics['co_ppm'], mq7_data['co_ppm'], unit="ppm", status=mq7_data['status'])
            self.publish(self.topics['co_voltage'], mq7_data['voltage'], unit="V")
            self.publish(self.topics['co_status'], mq7_data['status'], unit="")

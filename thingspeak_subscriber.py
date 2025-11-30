import time
import json
import signal
import sys
import os
from datetime import datetime
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
import requests
import traceback

def load_config():
    load_dotenv()
    
    config = {
        'mqtt_broker': os.getenv('MQTT_BROKER', 'localhost'),
        'mqtt_port': int(os.getenv('MQTT_PORT', 1883)),
        'mqtt_username': os.getenv('MQTT_USERNAME', 'airquality_sensor'),
        'mqtt_password': os.getenv('MQTT_PASSWORD', ''),
        'mqtt_base_topic': os.getenv('MQTT_BASE_TOPIC', 'home/airquality'),
        
        'thingspeak_url': os.getenv('THINGSPEAK_URL', 'https://api.thingspeak.com/update'),
        'thingspeak_write_key': os.getenv('THINGSPEAK_WRITE_KEY', ''),
        'thingspeak_channel_id': os.getenv('THINGSPEAK_CHANNEL_ID', ''),
        'thingspeak_min_interval': int(os.getenv('THINGSPEAK_MIN_INTERVAL', 15)),
        
        'field_mapping': {
            'field1': 'temperature',
            'field2': 'humidity',
            'field3': 'pressure',
            'field4': 'co_ppm',
            'field5': 'air_quality_iaq',
            'field6': 'gas_resistance',
            'field7': 'co_voltage',
            'field8': None
        }
    }

    print(config)
    print("hello", os.getenv('THINGSPEAK_WRITE_KEY', ''))
    
    return config

class ThingSpeakBridge:
    def __init__(self, config):
        self.config = config
        self.running = True
        self.last_update = 0
        self.data_buffer = {}
        
        self.stats = {
            'mqtt_messages': 0,
            'thingspeak_updates': 0,
            'thingspeak_errors': 0,
            'start_time': time.time()
        }

        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        self.mqtt_client = mqtt.Client(
            client_id="thingspeak_bridge",
            clean_session=True,
            protocol=mqtt.MQTTv311
        )
        
        self.mqtt_client.username_pw_set(
            username=config['mqtt_username'],
            password=config['mqtt_password']
        )
        
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.on_disconnect = self.on_disconnect
        
        print("=" * 80)
        print("  MQTT TO THINGSPEAK BRIDGE")
        print("=" * 80)
        print(f"MQTT Broker:      {config['mqtt_broker']}:{config['mqtt_port']}")
        print(f"MQTT Topic:       {config['mqtt_base_topic']}/#")
        print(f"ThingSpeak URL:   {config['thingspeak_url']}")
        print(f"ThingSpeak Ch:    {config['thingspeak_channel_id']}")
        print(f"Update Interval:  {config['thingspeak_min_interval']}s")
        print("=" * 80)
        print()
    
    def signal_handler(self, sig, frame):
        print("\n\n" + "=" * 80)
        print("Stopping bridge...")
        print("=" * 80)
        self.running = False
    
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"✓ Connected to MQTT broker")
            
            topic = f"{self.config['mqtt_base_topic']}/#"
            client.subscribe(topic, qos=1)
            print(f"✓ Subscribed to: {topic}")
            print("\nWaiting for data...\n")
        else:
            print(f"✗ MQTT connection failed. Code: {rc}")
    
    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            print(f"Unexpected MQTT disconnection. Code: {rc}")
    
    def on_message(self, client, userdata, msg):
        try:
            topic_parts = msg.topic.split('/')
            if len(topic_parts) < 3:
                return
            
            metric_name = topic_parts[-1]
            
            if metric_name in ['availability', 'status']:
                return
            
            try:
                payload = json.loads(msg.payload.decode())
                value = payload.get('value')
            except json.JSONDecodeError:
                value = msg.payload.decode().strip()
            
            self.data_buffer[metric_name] = value
            self.stats['mqtt_messages'] += 1
            
            timestamp = datetime.now().strftime('%H:%M:%S')
            print(f"[{timestamp}] MQTT → {metric_name}: {value}")
            
            self.check_and_send_to_thingspeak()
            
        except Exception as e:
            print(f"Error processing message: {e}")
    
    def check_and_send_to_thingspeak(self):
        now = time.time()
        time_since_last = now - self.last_update

        if time_since_last < self.config['thingspeak_min_interval']:
            return
        
        if not self.data_buffer:
            return
        
        self.send_to_thingspeak()
    
    def send_to_thingspeak(self):
        try:
            payload = {
                'api_key': self.config['thingspeak_write_key']
            }
            
            field_mapping = self.config['field_mapping']
            for field_num, metric_name in field_mapping.items():
                if metric_name and metric_name in self.data_buffer:
                    value = self.data_buffer[metric_name]
                    
                    if isinstance(value, str):
                        if metric_name in ['air_quality_category', 'co_status']:
                            continue
                        try:
                            value = float(value)
                        except ValueError:
                            continue
                    
                    payload[field_num] = value
            
            if len(payload) == 1:
                print("No numeric data to send to ThingSpeak")
                return
            
            print(payload)
            response = requests.get(
                self.config['thingspeak_url'],
                params=payload,
                timeout=10,
                verify=True
            )
            
            if response.status_code == 200:
                entry_id = response.text.strip()
                
                if entry_id and entry_id != '0':
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    print(f"\n{'=' * 80}")
                    print(f"[{timestamp}] ThingSpeak: Data sent successfully ✓")
                    print(f"Entry ID: {entry_id}")
                    print(f"Fields sent: {len(payload) - 1}")
                    
                    for field_num, value in payload.items():
                        if field_num != 'api_key':
                            metric = field_mapping.get(field_num, 'unknown')
                            print(f"  {field_num}: {metric} = {value}")
                    
                    print("=" * 80 + "\n")
                    
                    self.last_update = time.time()
                    self.stats['thingspeak_updates'] += 1
                    
                    self.data_buffer.clear()
                else:
                    print(f"ThingSpeak: Update rejected (rate limit or invalid data)")
                    self.stats['thingspeak_errors'] += 1
            else:
                print(f"✗ ThingSpeak: HTTP {response.status_code}")
                self.stats['thingspeak_errors'] += 1
        
        except requests.exceptions.Timeout:
            print(f"✗ ThingSpeak: Timeout")
            self.stats['thingspeak_errors'] += 1
        
        except requests.exceptions.SSLError as e:
            print(f"✗ ThingSpeak: SSL Error: {e}")
            self.stats['thingspeak_errors'] += 1
        
        except Exception as e:
            print(f"✗ ThingSpeak: Error: {e}")
            self.stats['thingspeak_errors'] += 1
    
    def connect_mqtt(self):
        try:
            self.mqtt_client.connect(
                self.config['mqtt_broker'],
                self.config['mqtt_port'],
                keepalive=60
            )
            return True
        except Exception as e:
            print(f"✗ Failed to connect to MQTT: {e}")
            return False
    
    def run(self):
        if not self.connect_mqtt():
            print("Cannot start without MQTT connection")
            return
        
        print("Bridge running. Press Ctrl+C to stop.\n")
        
        self.mqtt_client.loop_start()
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup()
    
    def cleanup(self):
        print("\nStopping MQTT client...")
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        
        runtime = time.time() - self.stats['start_time']
        print("\n" + "=" * 80)
        print("STATISTICS")
        print("=" * 80)
        print(f"Runtime:              {runtime:.0f}s ({runtime/60:.1f} min)")
        print(f"MQTT messages:        {self.stats['mqtt_messages']}")
        print(f"ThingSpeak updates:   {self.stats['thingspeak_updates']}")
        print(f"ThingSpeak errors:    {self.stats['thingspeak_errors']}")
        
        if self.stats['thingspeak_updates'] > 0:
            success_rate = (self.stats['thingspeak_updates'] / 
                          (self.stats['thingspeak_updates'] + self.stats['thingspeak_errors'])) * 100
            print(f"Success rate:         {success_rate:.1f}%")
        
        print("=" * 80)
        print("Bridge stopped")


if __name__ == "__main__":
    try:
        config = load_config()
        bridge = ThingSpeakBridge(config)
        bridge.run()
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)

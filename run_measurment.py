import time
import signal
import sys
import os
import traceback
from datetime import datetime
from dotenv import load_dotenv

import board
import busio
from adafruit_bme680 import Adafruit_BME680_I2C
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

from mqtt_publisher import AirQualityMQTTPublisher
from sensor_functions import read_bme680, read_mq7, print_measurement

def load_config():
    load_dotenv()

    base_topic = os.getenv('MQTT_BASE_TOPIC', 'home/airquality')
    
    mqtt_config = {
        'broker': os.getenv('MQTT_BROKER', 'localhost'),
        'port': int(os.getenv('MQTT_PORT', 1883)),
        'username': os.getenv('MQTT_USERNAME', 'airquality_sensor'),
        'password': os.getenv('MQTT_PASSWORD', 'Air123123'),
        'use_tls': os.getenv('MQTT_USE_TLS', 'False').lower() == 'true',
        'client_id': os.getenv('MQTT_CLIENT_ID', 'airquality_sensor_rpi'),
        'ca_cert': os.getenv('MQTT_CA_CERT', '/etc/mosquitto/certs/ca.crt'),
        'topics': {
            'temperature': f"{base_topic}/temperature",
            'humidity': f"{base_topic}/humidity",
            'pressure': f"{base_topic}/pressure",
            'gas_resistance': f"{base_topic}/gas_resistance",
            'air_quality_iaq': f"{base_topic}/air_quality_iaq",
            'air_quality_category': f"{base_topic}/air_quality_category",
            'co_ppm': f"{base_topic}/co_ppm",
            'co_voltage': f"{base_topic}/co_voltage",
            'co_status': f"{base_topic}/co_status",
            'availability': f"{base_topic}/availability",
            'status': f"{base_topic}/status"
        }
    }

    sensor_config = {
        'measurement_interval': int(os.getenv('MEASUREMENT_INTERVAL', 10)),
        'bme680_address': int(os.getenv('BME680_ADDRESS', '0x77'), 16),
        'ads1115_address': int(os.getenv('ADS1115_ADDRESS', '0x48'), 16),
        'mq7_channel': int(os.getenv('MQ7_CHANNEL', 0)),
        'sea_level_pressure': float(os.getenv('SEA_LEVEL_PRESSURE', 1013.25)),
        'mq7_r0': int(os.getenv('MQ7_R0', 10000)),
        'mq7_rl': int(os.getenv('MQ7_RL', 10000))
    }
    
    return mqtt_config, sensor_config

class AirQualityMonitor:
    def __init__(self):
        print("=" * 80)
        print("  SYSTEM MONITOROWANIA JAKOŚCI POWIETRZA")
        print("  Projekt: SCIR - IoT Air Quality Detection")
        print("=" * 80)
        print()
        
        print("Loading configuration...")
        self.mqtt_config, self.sensor_config = load_config()
        print("✓ Configuration loaded from .env")
        
        self.running = True
        self.measurement_count = 0
        
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        print("\nInitializing I2C...")
        try:
            self.i2c = busio.I2C(board.SCL, board.SDA)
            print("✓ I2C initialized")
        except Exception as e:
            print(f"✗ I2C error: {e}")
            sys.exit(1)
        
        print("\nInitializing BME680...")
        try:
            self.bme680 = Adafruit_BME680_I2C(
                self.i2c, 
                address=self.sensor_config['bme680_address']
            )
            self.bme680.sea_level_pressure = self.sensor_config['sea_level_pressure']
            print(f"✓ BME680 initialized (0x{self.sensor_config['bme680_address']:02X})")
        except Exception as e:
            print(f"⚠ BME680 unavailable: {e}")
            self.bme680 = None
        
        print("\nInitializing MQ-7 (via ADS1115)...")
        try:
            self.ads = ADS.ADS1115(
                self.i2c, 
                address=self.sensor_config['ads1115_address']
            )
            self.mq7_channel = AnalogIn(
                self.ads, 
                self.sensor_config['mq7_channel']
            )
            print(f"✓ MQ-7 initialized (ADS1115 @ 0x{self.sensor_config['ads1115_address']:02X})")
        except Exception as e:
            print(f"⚠ MQ-7 unavailable: {e}")
            self.ads = None
            self.mq7_channel = None

        print("\nInitializing MQTT...")
        self.mqtt = AirQualityMQTTPublisher(self.mqtt_config)
        
        if not self.mqtt.connect():
            print("Cannot connect to MQTT")
            print("Continuing without MQTT (local logs only)")
        
        print("\n" + "=" * 80)
        print("System ready")
        print("=" * 80)
        print()
    
    def signal_handler(self, sig, frame):
        print("\n\n" + "=" * 80)
        print("Stopping system...")
        print("=" * 80)
        self.running = False
    
    def run(self):
        interval = self.sensor_config['measurement_interval']
        print(f"\nStarting monitoring (interval: {interval}s)")
        print(f"Press Ctrl+C to stop\n")
        
        self.mqtt.publish_status("System started")
        
        try:
            while self.running:
                self.measurement_count += 1
                
                bme_data = read_bme680(self.bme680)
                mq7_data = read_mq7(
                    self.mq7_channel,
                    R0=self.sensor_config['mq7_r0'],
                    RL=self.sensor_config['mq7_rl']
                )

                print_measurement(bme_data, mq7_data, self.measurement_count)
                
                self.mqtt.publish_sensor_data(bme_data, mq7_data)
                
                for _ in range(interval):
                    if not self.running:
                        break
                    time.sleep(1)
        
        except Exception as e:
            print(f"\nCritical error: {e}")
            traceback.print_exc()
        
        finally:
            self.cleanup()
    
    def cleanup(self):
        print("\nClosing connections...")
        
        self.mqtt.publish_status("System stopped")
        self.mqtt.disconnect()
        
        print(f"\nStatistics:")
        print(f"  Measurements:    {self.measurement_count}")
        print(f"  Runtime:         ~{self.measurement_count * self.sensor_config['measurement_interval'] // 60} minutes")
        print("\nSystem stopped")
        print("=" * 80)

if __name__ == "__main__":
    try:
        monitor = AirQualityMonitor()
        monitor.run()
    except Exception as e:
        print(f"\nInitialization error: {e}")
        traceback.print_exc()
        sys.exit(1)

Instalacja i Konfiguracja MQTT
```
sudo apt install -y mosquitto mosquitto-clients
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```

```
sudo mosquitto_passwd -c /etc/mosquitto/passwd airquality_sensor
# air_sensor_password
sudo mosquitto_passwd /etc/mosquitto/passwd homeassistant
# home_assistant_password

sudo chmod 600 /etc/mosquitto/passwd
sudo chown mosquitto:mosquitto /etc/mosquitto/passwd

cat /etc/mosquitto/mosquitto.conf

sudo tee /etc/mosquitto/mosquitto.conf > /dev/null << 'EOF'
pid_file /run/mosquitto/mosquitto.pid
include_dir /etc/mosquitto/conf.d
EOF

sudo tee /etc/mosquitto/conf.d/airquality.conf > /dev/null << 'EOF'
listener 1883 localhost
allow_anonymous false
password_file /etc/mosquitto/passwd
log_dest stdout
persistence true
persistence_location /var/lib/mosquitto/
EOF

sudo mosquitto -c /etc/mosquitto/mosquitto.conf -v

sudo systemctl restart mosquitto
sudo systemctl status mosquitto
```

Testowanie MQTT
W pierwszym terminalu:
```
mosquitto_sub -h localhost -p 1883 -u airquality_sensor -P "air_sensor_password" -t "home/airquality/#" -v
```
W drugim terminalu:
```
mosquitto_pub -h localhost -p 1883 -u airquality_sensor -P "air_sensor_password" -t "home/airquality/test" -m "Test 123"
```


Nowa strtuktura:
```
├── main.py              # Program główny - orkiestracja całego systemu
├── mqtt_publisher.py    # Moduł MQTT - komunikacja z brokerem
├── sensor_functions.py  # Moduł czujników - pomiary i obliczenia
├── .env                 # Konfiguracja - wszystkie ustawienia
└── requirements.txt     # Zależności Python
```

- main.py - Orkiestracja całego systemu monitorowania
- mqtt_publisher.py - Zarządzanie całą komunikacją z brokerem MQTT
- sensor_functions.py - Odczyt, przetwarzanie i prezentacja danych z czujników

Publikowanie danych:

System publikuje dane z dwóch czujników:
- BME680 - parametry środowiskowe (temperatura, wilgotność, ciśnienie, gazy)
MQ-7 - tlenek węgla (CO/czad)

Dane z Czujnika BME680

1. Temperatura - home/airquality/temperature
2. Wilgotność - home/airquality/humidity
3. Ciśnienie - home/airquality/pressure
4. Opór Gazu (VOC) - home/airquality/gas_resistance
5. Wskaźnik IAQ - home/airquality/air_quality_iaq
6. Kategoria Jakości Powietrza - home/airquality/air_quality_category

Dane z Czujnika MQ-7 

1. Stężenie CO - home/airquality/co_ppm
2. Napięcie Czujnika CO - home/airquality/co_voltage
3. Status CO - home/airquality/co_status

Dane Systemowe

1. Dostępność Systemu - home/airquality/availability
2. Status Systemu - home/airquality/status

Warstwa Sieciowa

System monitorowania jakości powietrza wykorzystuje wielowarstwową architekturę komunikacyjną opartą o protokół MQTT oraz HTTPS, zapewniającą niezawodne przesyłanie danych z czujników do systemów przetwarzania i wizualizacji.

System wykorzystuje topologię gwiazdy, w której wszystkie komponenty komunikują się przez centralny broker MQTT działający lokalnie na węźle Raspberry Pi oraz usługę chmurową ThingSpeak. Główne komponenty systemu:

- Raspberry Pi 4B – węzeł IoT wyposażony w czujniki, komunikujący się z siecią lokalną przez Wi-Fi
- Broker MQTT (Mosquitto) – pośredniczy w komunikacji między czujnikami a konsumentami danych
- ThingSpeak Cloud – platforma chmurowa do przechowywania i wizualizacji danych

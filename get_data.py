import time
import board
import busio
from adafruit_bme680 import Adafruit_BME680_I2C
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

i2c = busio.I2C(board.SCL, board.SDA)

try:
    bme680 = Adafruit_BME680_I2C(i2c, address=0x77)
    bme680.sea_level_pressure = 1013.25
except Exception as e:
    bme680 = None

try:
    ads = ADS.ADS1115(i2c, address=0x48)
    mq7_channel = AnalogIn(ads, 0)
except Exception as e:
    ads = None
    mq7_channel = None

def calculate_iaq(gas_resistance, humidity):
    if gas_resistance == 0:
        return 500
    
    gas_score = min(100, (gas_resistance / 2000))
    
    hum_score = 100 - abs(humidity - 40) * 2.5
    hum_score = max(0, min(100, hum_score))
    
    iaq = (gas_score * 0.75 + hum_score * 0.25) * 5
    return 500 - iaq

def get_iaq_category(iaq):
    if iaq < 50:
        return "DOSKONALA"
    elif iaq < 100:
        return "DOBRA"
    elif iaq < 150:
        return "UMIARKOWANA"
    elif iaq < 200:
        return "NIEZDROWA"
    else:
        return "ZLA"

def calculate_co_ppm(voltage, R0=10000):
    if voltage < 0.1:
        return 0
    
    RL = 10000
    Rs = ((5.0 * RL) / voltage) - RL
    
    if Rs <= 0:
        return 0
    
    ratio = Rs / R0
    
    try:
        co_ppm = 98.322 * (ratio ** -1.458)
        return max(0, min(2000, co_ppm))
    except:
        return 0

def get_co_status(co_ppm):
    if co_ppm < 9:
        return "BEZPIECZNY"
    elif co_ppm < 50:
        return "DOPUSZCZALNY"
    elif co_ppm < 200:
        return "UWAGA"
    else:
        return "ALARM"

measurement_count = 0

try:
    while True:
        measurement_count += 1
        
        print("-" * 80)
        print(f"Pomiar #{measurement_count:04d} | {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 80)

        if bme680:
            try:
                temp = bme680.temperature
                hum = bme680.humidity
                pres = bme680.pressure
                gas = bme680.gas
                
                iaq = calculate_iaq(gas, hum)
                iaq_cat = get_iaq_category(iaq)
                
                print()
                print("BME680 - Parametry srodowiskowe:")
                print(f"  Temperatura:        {temp:6.1f} C")
                print(f"  Wilgotnosc:         {hum:6.1f} %")
                print(f"  Cisnienie:          {pres:7.1f} hPa")
                print(f"  Opor gazu (VOC):    {gas:8d} Ohm")
                print(f"  IAQ Score:          {iaq:6.0f} / 500")
                print(f"  Jakosc powietrza:   {iaq_cat}")
                
            except Exception as e:
                print(e)
        
        if mq7_channel:
            try:
                voltage = mq7_channel.voltage
                raw_value = mq7_channel.value
                co_ppm = calculate_co_ppm(voltage)
                co_status = get_co_status(co_ppm)
                
                print()
                print("MQ-7 - Tlenek wegla (CO):")
                print(f"  CO (czad):          {co_ppm:6.1f} ppm")
                print(f"  Napiecie:           {voltage:6.3f} V")
                print(f"  ADC Raw:            {raw_value:6d}")
                print(f"  Status:             {co_status}")
                
                if co_ppm > 50:
                    print()
                    print("!" * 80)
                    print("UWAGA! PODWYZSZONE STEZENIE TLENKU WEGLA!")
                    print("Otworz okna i sprawdz zrodla spalania!")
                    print("!" * 80)
                
            except Exception as e:
                print(e)
        
        print()
        print("-" * 80)
        print("Nastepny pomiar za 5 sekund... (Ctrl+C aby zatrzymac)")
        print()
        
        time.sleep(5)

except KeyboardInterrupt:
    print(f"Liczba pomiarow:    {measurement_count}")
    print(f"Czas dzialania:     ~{measurement_count * 5 // 60} minut")
except Exception as e:
    print(e)

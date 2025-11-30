import time

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
        return "Excellent"
    elif iaq < 100:
        return "Good"
    elif iaq < 150:
        return "Ok"
    elif iaq < 200:
        return "Not Good"
    else:
        return "Bad"

def calculate_co_ppm(voltage, R0=10000, RL=10000):
    if voltage < 0.1:
        return 0
    
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
        return "Safe"
    elif co_ppm < 50:
        return "Acceptable"
    elif co_ppm < 200:
        return "Warning"
    else:
        return "ALARM"


def read_bme680(sensor):
    if not sensor:
        return None
    
    try:
        temp = sensor.temperature
        hum = sensor.humidity
        pres = sensor.pressure
        gas = sensor.gas
        
        iaq = calculate_iaq(gas, hum)
        iaq_category = get_iaq_category(iaq)
        
        return {
            'temperature': round(temp, 2),
            'humidity': round(hum, 2),
            'pressure': round(pres, 2),
            'gas_resistance': int(gas),
            'iaq': round(iaq, 1),
            'iaq_category': iaq_category
        }
        
    except Exception as e:
        print(f"BME680 read error: {e}")
        return None


def read_mq7(mq7_channel, R0=10000, RL=10000):
    if not mq7_channel:
        return None
    
    try:
        voltage = mq7_channel.voltage
        raw_value = mq7_channel.value
        co_ppm = calculate_co_ppm(voltage, R0, RL)
        co_status = get_co_status(co_ppm)
        
        return {
            'co_ppm': round(co_ppm, 2),
            'voltage': round(voltage, 3),
            'raw_value': raw_value,
            'status': co_status
        }
        
    except Exception as e:
        print(f"MQ-7 read error: {e}")
        return None

def print_measurement(bme_data, mq7_data, measurement_count):    
    print("-" * 80)
    print(f"Measurement #{measurement_count:04d} | {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 80)
    
    if bme_data:
        print("\nBME680 - Environmental Parameters:")
        print(f"  Temperature:        {bme_data['temperature']:6.1f} C")
        print(f"  Humidity:           {bme_data['humidity']:6.1f} %")
        print(f"  Pressure:           {bme_data['pressure']:7.1f} hPa")
        print(f"  Gas Resistance (VOC): {bme_data['gas_resistance']:8d} O")
        print(f"  IAQ Score:          {bme_data['iaq']:6.1f} / 500")
        print(f"  Air Quality:        {bme_data['iaq_category']}")
    else:
        print("\nBME680: No data")
    
    if mq7_data:
        print("\nMQ-7 - Carbon Monoxide (CO):")
        print(f"  CO (carbon monoxide): {mq7_data['co_ppm']:6.1f} ppm")
        print(f"  Voltage:              {mq7_data['voltage']:6.3f} V")
        print(f"  ADC Raw:              {mq7_data['raw_value']:6d}")
        print(f"  Status:               {mq7_data['status']}")
        
        if mq7_data['co_ppm'] > 50:
            print("\n" + "!" * 80)
            print("WARNING! ELEVATED CARBON MONOXIDE LEVEL!")
            print("Open windows and check combustion sources!")
            print("!" * 80)
    else:
        print("\nMQ-7: No data")
    
    print("\n" + "-" * 80)


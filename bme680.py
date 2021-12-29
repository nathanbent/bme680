#!/usr/bin/env python

import bme680
import time
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

sensor_host_name = "RaspiTest"
client = InfluxDBClient(url="http://10.0.0.12:8086", token="U_O0SpT05ZAqNcuorQme0oIfTbzN6XEpVzwno8wAd1nmSGUDF1k9gKr6yJwj_lwPcpwvq5zDH59qHOPZS3aPCg==")

def write_aq_to_influx(air_quality_score, run_count, run_time):
    global sensor_host_name
    bme280_data = [
        {
            "measurement": "bme280",
            "tags": {
                "host": sensor_host_name
            },
            "fields": {
                "gas": float(air_quality_score),
                "readruncount": float(run_count),
                "readruntime": float(run_time)
            }
        }
    ]
    print(run_time)
    print((run_count))
    try:
        write_api = client.write_api(write_options=SYNCHRONOUS)
        write_api.write(bucket, org, bme280_data)

    except:
        print("Error encountered BME, waiting for next pass to try again")

print("""indoor-air-quality.py - Estimates indoor air quality.

Runs the sensor for a burn-in period, then uses a
combination of relative humidity and gas resistance
to estimate indoor air quality as a percentage.

Press Ctrl+C to exit!

""")

try:
    sensor = bme680.BME680(bme680.I2C_ADDR_PRIMARY)
except (RuntimeError, IOError):
    sensor = bme680.BME680(bme680.I2C_ADDR_SECONDARY)

# These oversampling settings can be tweaked to
# change the balance between accuracy and noise in
# the data.

sensor.set_humidity_oversample(bme680.OS_2X)
sensor.set_pressure_oversample(bme680.OS_4X)
sensor.set_temperature_oversample(bme680.OS_8X)
sensor.set_filter(bme680.FILTER_SIZE_3)
sensor.set_gas_status(bme680.ENABLE_GAS_MEAS)

print('\n\nInitial reading:')
for name in dir(sensor.data):
    value = getattr(sensor.data, name)

    if not name.startswith('_'):
        print('{}: {}'.format(name, value))

sensor.set_gas_heater_temperature(320)
sensor.set_gas_heater_duration(150)
sensor.select_gas_heater_profile(0)

# start_time and curr_time ensure that the
# burn_in_time (in seconds) is kept track of.

run_count = 0
start_time = time.time()
curr_time = time.time()
burn_in_time = 300

burn_in_data = []

try:
    # Collect gas resistance burn-in values, then use the average
    # of the last 50 values to set the upper limit for calculating
    # gas_baseline.
    print('Collecting gas resistance burn-in data for 5 mins\n')
    while curr_time - start_time < burn_in_time:
        curr_time = time.time()
        if sensor.get_sensor_data() and sensor.data.heat_stable:
            gas = sensor.data.gas_resistance
            burn_in_data.append(gas)
            print('Gas: {0} Ohms'.format(gas))
            time.sleep(1)

    gas_baseline = sum(burn_in_data[-50:]) / 50.0

    # Set the humidity baseline to 40%, an optimal indoor humidity.
    hum_baseline = 40.0

    # This sets the balance between humidity and gas reading in the
    # calculation of air_quality_score (25:75, humidity:gas)
    hum_weighting = 0.25

    print('Gas baseline: {0} Ohms, humidity baseline: {1:.2f} %RH\n'.format(
        gas_baseline,
        hum_baseline))

    while True:
        curr_time = time.time()
        if sensor.get_sensor_data() and sensor.data.heat_stable:
            gas = sensor.data.gas_resistance
            gas_offset = gas_baseline - gas

            hum = sensor.data.humidity
            hum_offset = hum - hum_baseline

            # Calculate hum_score as the distance from the hum_baseline.
            if hum_offset > 0:
                hum_score = (100 - hum_baseline - hum_offset)
                hum_score /= (100 - hum_baseline)
                hum_score *= (hum_weighting * 100)

            else:
                hum_score = (hum_baseline + hum_offset)
                hum_score /= hum_baseline
                hum_score *= (hum_weighting * 100)

            # Calculate gas_score as the distance from the gas_baseline.
            if gas_offset > 0:
                gas_score = (gas / gas_baseline)
                gas_score *= (100 - (hum_weighting * 100))

            else:
                gas_score = 100 - (hum_weighting * 100)

            # Calculate air_quality_score.
            air_quality_score = hum_score + gas_score
            run_time = curr_time - start_time
            print('Gas: {0:.2f} Ohms,humidity: {1:.2f} %RH,air quality: {2:.2f}'.format(
                gas,
                hum,
                air_quality_score))
            print(run_count)
            if runcount == 0 or runcount % 30 == 0:
                write_aq_to_influx(air_quality_score, run_count, run_time)
            time.sleep(1)
            run_count = run_count + 1



except KeyboardInterrupt:
    pass
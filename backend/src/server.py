from flask import Flask, jsonify, request
import requests
from bs4 import BeautifulSoup
from flask_cors import CORS
import math
import datetime
import csv
import threading
import time
from os import path

app = Flask(__name__)
CORS(app)

CSV_FILE = path.join(path.dirname(path.realpath(__file__)), "db", "wetbulb.csv")
STATION_URL = "https://www.wunderground.com/dashboard/pws/KMALOWEL100"

def calculate_wet_bulb(T, RH):
    try:
        Tw = (
            T * math.atan(0.151977 * math.sqrt(RH + 8.313659))
            + math.atan(T + RH)
            - math.atan(RH - 1.676331)
            + 0.00391838 * (RH ** 1.5) * math.atan(0.023101 * RH)
            - 4.686035
        )
        return round(Tw, 2)
    except:
        return None

@app.route('/get_temperature_history')
def get_temperature_history():
    raw_url = request.args.get("link")
    if not raw_url:
        return jsonify({"error": "Missing 'link' query parameter."}), 400

    try:
        headers = { "User-Agent": "Mozilla/5.0" }
        response = requests.get(raw_url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        rows = soup.find_all("tr", class_="ng-star-inserted")
        history = []

        for row in rows:
            time_tag = row.find("strong")
            temp_tag = row.find("span", class_="wu-value wu-value-to")

            if time_tag and temp_tag:
                time_str = time_tag.text.strip()
                try:
                    temp_val = float(temp_tag.text.strip())
                    history.append({
                        "time": time_str,
                        "temperature": temp_val
                    })
                except ValueError:
                    continue

        return jsonify(history)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_current_weather')
def get_current_weather():
    raw_url = request.args.get("link")
    if not raw_url:
        return jsonify({"error": "Missing 'link' query parameter."}), 400

    try:
        headers = { "User-Agent": "Mozilla/5.0" }
        response = requests.get(raw_url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        temperature = None
        temp_div = soup.find("div", class_="current-temp")
        if temp_div:
            temp_text = temp_div.text.strip().replace("°", "")
            try:
                temperature = float(temp_text)
            except:
                pass

        humidity = None
        humidity_container = soup.find("span", class_="wu-unit-humidity")
        if humidity_container:
            humidity_element = humidity_container.find("span", class_="wu-value wu-value-to")
            if humidity_element:
                try:
                    humidity = float(humidity_element.text.strip())
                except:
                    pass

        wet_bulb = calculate_wet_bulb(temperature, humidity) if temperature is not None and humidity is not None else None

        return jsonify({
            "temperature": temperature,
            "humidity": humidity,
            "wet_bulb": wet_bulb
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_logged_data')
def get_logged_data():
    try:
        data = []
        with open(CSV_FILE, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) != 4 or row[0] == "time":
                    continue
                data.append({
                    "time": row[0],
                    "temp": float(row[1]),
                    "humidity": float(row[2]),
                    "wetbulb": float(row[3])
                })
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def log_weather_loop():
    while True:
        try:
            headers = { "User-Agent": "Mozilla/5.0" }
            response = requests.get(STATION_URL, headers=headers)
            soup = BeautifulSoup(response.text, "html.parser")

            temp_div = soup.find("div", class_="current-temp")
            humidity_container = soup.find("span", class_="wu-unit-humidity")

            if temp_div and humidity_container:
                temp = float(temp_div.text.strip().replace("°", ""))
                humidity_elem = humidity_container.find("span", class_="wu-value wu-value-to")
                humidity = float(humidity_elem.text.strip()) if humidity_elem else None

                wet_bulb = calculate_wet_bulb(temp, humidity)
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

                with open(CSV_FILE, 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([timestamp, temp, humidity, wet_bulb])
        except Exception as e:
            print("Logging error:", e)

        time.sleep(600)  # every 10 minutes

# Start the logging thread
threading.Thread(target=log_weather_loop, daemon=True).start()

if __name__ == '__main__':
    # Write header if it doesn't exist
    try:
        with open(CSV_FILE, 'x') as f:
            writer = csv.writer(f)
            writer.writerow(['time', 'temp', 'humidity', 'wetbulb'])
    except FileExistsError:
        pass
    app.run(debug=True, host='0.0.0.0', port=8080) # Change port to 8080 for local testing

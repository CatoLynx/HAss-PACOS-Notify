"""
Copyright (C) 2026 Julian Metzler

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import datetime
import json
import threading
import time
import traceback

from flask import Flask, request, Response
from homeassistant_api import Client
from pyfis.ibis import IBISMaster
from pyfis.utils.serial import TcpSerialPort

from secrets import *


app = Flask(__name__)


NOTIFICATION_DURATION_SECONDS = 2 * 60 * 60


class NotificationDisplay:
    def __init__(self, host, port, address, home_assistant):
        self.host = host
        self.port = port
        self.display = None
        self.reconnect()
        self.address = address
        self.hass = home_assistant
        self.running = True
        self.display_on = True
        self.fullscreen_notification = False
        self.prev_fullscreen_notification = False
        self.notifications = []

    def reconnect(self):
        try:
            self.display = IBISMaster(TcpSerialPort(self.host, self.port))
        except:
            print("Failed to reconnect")
            #traceback.print_exc()

    def notify(self, text):
        self.notifications.append((time.time(), text))
        self.notifications.sort(key=lambda n:n[0], reverse=True) # newest first
        self.update_display()

    def get_state(self):
        return self.display_on

    def set_state(self, state):
        self.display_on = state
        self.update_display()

    def clear_display(self):
        attempt = 1
        while True:
            try:
                self.display.DS021_PACOS(self.address, "%32")
                time.sleep(0.5)
                break
            except:
                if attempt > 3:
                    print("Giving up")
                    break
                print(f"Error, reconnecting (attempt {attempt})")
                self.reconnect()
                attempt += 1
                time.sleep(5)

    def update_display(self):
        attempt = 1
        while True:
            try:
                self._update_display()
                break
            except:
                if attempt > 3:
                    print("Giving up")
                    break
                print(f"Error, reconnecting (attempt {attempt})")
                self.reconnect()
                attempt += 1
                time.sleep(5)

    def send_texts(self, texts):
        for text_group in texts:
            message = ""
            for text in text_group:
                if 'line' in text:
                    if text['line'] == 'h':
                        message += f"%40{text['x_start']:03d}{text['x_end']:03d}{text['y']:03d}{text['width']}"
                    elif text['line'] == 'v':
                        message += f"%41{text['x']:03d}{text['y_start']:03d}{text['y_end']:03d}{text['width']}"
                else:
                    message += f"%00{text['x_start']:03d}{text['x_end']:03d}{text['y']:03d}{text['attribute']}%10$1{text['font']}{text['text']}"
            self.display.DS021_PACOS(self.address, message)
            time.sleep(0.5)

    def lines_to_texts(self, text, font, blink=False):
        lines = text.splitlines()
        num_lines = len(lines)
        line_height = 14
        block_height = num_lines * line_height
        margin = (48 - block_height) // 2
        texts = []
        for i, line in enumerate(lines):
            y_bottom = margin + line_height * (i + 1)
            if blink:
                line = f"$61{line}"
            texts.append({
                'text': line,
                'x_start': 1,
                'x_end': 160,
                'y': y_bottom,
                'font': font,
                'attribute': 2
            })
        return [texts]

    def get_sensor_texts(self):
        # Build messages for sensor values
        co2_state = self.hass.get_state(entity_id="sensor.co2_meter_co2")
        pm25_state = self.hass.get_state(entity_id="sensor.flur_luft_pm25")
        voc_state = self.hass.get_state(entity_id="sensor.flur_luft_voc_index")
        rh_state = self.hass.get_state(entity_id="sensor.flur_luft_humidity")
        sz_temp_state = self.hass.get_state(entity_id="sensor.sz_umgebung_temperature")
        wz_temp_state = self.hass.get_state(entity_id="sensor.wz_umgebung_temperature")
        bad_temp_state = self.hass.get_state(entity_id="sensor.bad_umgebung_temperature")
        flur_temp_state = self.hass.get_state(entity_id="sensor.flur_luft_temperature")
        texts = [
            [
                {
                    'text': "Schlafz.",
                    'x_start': 1,
                    'x_end': 43,
                    'y': 21,
                    'font': 5,
                    'attribute': 3
                },
                {
                    'text': "Wohnz.",
                    'x_start': 1,
                    'x_end': 43,
                    'y': 30,
                    'font': 5,
                    'attribute': 3
                },
                {
                    'text': "Bad",
                    'x_start': 1,
                    'x_end': 43,
                    'y': 39,
                    'font': 5,
                    'attribute': 3
                },
                {
                    'text': "Flur",
                    'x_start': 1,
                    'x_end': 43,
                    'y': 48,
                    'font': 5,
                    'attribute': 3
                }
            ],
            [
                {
                    'text': f"{float(sz_temp_state.state):.1f} C",
                    'x_start': 45,
                    'x_end': 78,
                    'y': 21,
                    'font': 5,
                    'attribute': 1
                },
                {
                    'text': f"{float(wz_temp_state.state):.1f} C",
                    'x_start': 45,
                    'x_end': 78,
                    'y': 30,
                    'font': 5,
                    'attribute': 1
                },
                {
                    'text': f"{float(bad_temp_state.state):.1f} C",
                    'x_start': 45,
                    'x_end': 78,
                    'y': 39,
                    'font': 5,
                    'attribute': 1
                },
                {
                    'text': f"{float(flur_temp_state.state):.1f} C",
                    'x_start': 45,
                    'x_end': 78,
                    'y': 48,
                    'font': 5,
                    'attribute': 1
                }
            ],
            [
                {
                    'text': "Hum",
                    'x_start': 82,
                    'x_end': 110,
                    'y': 21,
                    'font': 5,
                    'attribute': 3
                },
                {
                    'text': "PM2.5",
                    'x_start': 82,
                    'x_end': 110,
                    'y': 30,
                    'font': 5,
                    'attribute': 3
                },
                {
                    'text': "tVOC",
                    'x_start': 82,
                    'x_end': 110,
                    'y': 39,
                    'font': 5,
                    'attribute': 3
                },
                {
                    'text': "CO2",
                    'x_start': 82,
                    'x_end': 110,
                    'y': 48,
                    'font': 5,
                    'attribute': 3
                }
            ],
            [
                {
                    'text': f"{rh_state.state}%% rH",
                    'x_start': 112,
                    'x_end': 160,
                    'y': 21,
                    'font': 5,
                    'attribute': 1
                },
                {
                    'text': f"{pm25_state.state} ug",
                    'x_start': 112,
                    'x_end': 160,
                    'y': 30,
                    'font': 5,
                    'attribute': 1
                },
                {
                    'text': f"{voc_state.state}",
                    'x_start': 112,
                    'x_end': 160,
                    'y': 39,
                    'font': 5,
                    'attribute': 1
                },
                {
                    'text': f"{float(co2_state.state):.0f} ppm",
                    'x_start': 112,
                    'x_end': 160,
                    'y': 48,
                    'font': 5,
                    'attribute': 1
                }
            ]
        ]
        return texts

    def _update_display(self):
        if not self.display_on:
            self.clear_display()
            return

        now = time.time()
        now_str = time.strftime("%a %d.%m.%Y %H:%M")
        now_str_short = time.strftime("%H:%M")

        sensor_texts = []
        try:
            sensor_texts = self.get_sensor_texts()
        except:
            traceback.print_exc()

        texts = [
            [
                {
                    'text': "Lynx Lair",
                    'x_start': 1,
                    'x_end': 48,
                    'y': 9,
                    'font': 5,
                    'attribute': 3
                },
                {
                    'text': now_str,
                    'x_start': 50,
                    'x_end': 160,
                    'y': 9,
                    'font': 5,
                    'attribute': 1
                },
                {
                    'line': 'h',
                    'x_start': 1,
                    'x_end': 160,
                    'y': 11,
                    'width': 1
                },
                {
                    'line': 'v',
                    'x': 80,
                    'y_start': 12,
                    'y_end': 48,
                    'width': 1
                }
            ]
        ]

        texts += sensor_texts

        scroll_texts = []
        for notification in self.notifications:
            timestamp, text = notification
            absolute_time = datetime.datetime.fromtimestamp(timestamp).strftime("%H:%M")
            seconds = round(now - timestamp)
            if seconds >= 3600:
                hours = seconds // 3600
                if hours == 1:
                    relative_str = f"{hours} hour ago ({absolute_time})"
                else:
                    relative_str = f"{hours} hours ago ({absolute_time})"
            elif seconds >= 60:
                minutes = seconds // 60
                if minutes == 1:
                    relative_str = f"{minutes} minute ago ({absolute_time})"
                else:
                    relative_str = f"{minutes} minutes ago ({absolute_time})"
            else:
                # For fresh notifications, show them as a big flashing text for the first minute
                # self.notifications is sorted by newest first, so returning after this is fine
                self.fullscreen_notification = True
                if not self.prev_fullscreen_notification:
                    self.clear_display()
                    self.prev_fullscreen_notification = True
                texts = self.lines_to_texts(text, font=1, blink=True)
                self.send_texts(texts)
                return

            scroll_texts.append(f"{relative_str}: {text}")

        if scroll_texts:
            texts[0][1]['text'] = now_str_short
            texts[0][1]['x_start'] = 130
            # Move scroll text to new group because of size
            texts.append([texts[0][0].copy()])
            del texts[0][0]
            texts[-1][0]['text'] = "  ***  ".join(scroll_texts).replace("\n", " ")
            texts[-1][0]['x_end'] = 128
            texts[-1][0]['attribute'] = 7

        self.fullscreen_notification = False
        if self.prev_fullscreen_notification:
            self.clear_display()
            self.prev_fullscreen_notification = False
        self.send_texts(texts)

    def stop(self):
        self.running = False

    def loop(self):
        last_minute = ""
        while self.running:
            now = time.time()
            minute = time.strftime("%M")

            # Remove old notifications
            for notification in list(self.notifications): # iterate over copy
                timestamp, text = notification
                if now - timestamp >= NOTIFICATION_DURATION_SECONDS:
                    self.notifications.remove(notification)

            # Update display on minute change
            if minute != last_minute:
                self.update_display()
                last_minute = minute

            time.sleep(1)


@app.route("/notify.json", methods=["GET", 'POST'])
def rest_notify():
    if 'message' in request.args:
        display.notify(request.args.get('message'))
    return Response(json.dumps({"test": True}), mimetype='application/json')

@app.route("/switch.json", methods=["GET", 'POST'])
def rest_switch():
    if request.method == "POST":
        if request.data == b"ON":
            display.set_state(True)
        elif request.data == b"OFF":
            display.set_state(False)
    return Response("ON" if display.get_state() else "OFF", mimetype='application/json')


hass = Client(HASS_API_URL, HASS_TOKEN, cache_session=False)
display = NotificationDisplay(host=PACOS_HOST, port=PACOS_PORT, address=PACOS_ADDRESS, home_assistant=hass)
display.clear_display()

if __name__ == "__main__":
    display_thread = threading.Thread(target=display.loop)
    print("Starting display thread")
    display_thread.start()
    print("Starting server")
    app.run(host="0.0.0.0", port=LISTEN_PORT)
    print("Server stopped")
    print("Stopping display thread")
    display.stop()

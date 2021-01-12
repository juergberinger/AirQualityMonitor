"""
Air quality monitor in MicroPython using ESP32
"""
__author__ = 'Juerg Beringer'
__version__ = "0.2"

import math

import machine
import ssd1306
import dht
import uasyncio as asyncio
import pms5003


# Configuration and display
smoke_corr_factor = 0.48

display_config = {
    # each entry is a triple (text,x_pos,y_pos), negative pos_x means right-aligned text
    'title': ('Air Monitor v%s' % __version__,0,0),
    'dht_temp': ('%4.1fC',-16,3),
    'dht_humidity': ('%3.0f%%',-16,4),
    'dewpoint': ('dew %4.1fC',-16,5),
    'aqi': ('AQI = %3.0f', 0,3),
    'aqismoke': ('Smoke %3.0f', 0,4),
    'pms_25': ('%3i ug/m3',0,7),
    'debug': ('debug %i/%i',-16,7)
}

rgb_colors = {
    # each entry is a triple (red, green, blue, blinking) with colors in [0,255] and blinking = false/true
    'b': (0, 0, 0, False),
    'g': (0, 100, 0, False),
    'y': (100, 100, 0, False),
    'o': (120, 20, 0, False),
    'r': (150, 0, 0, False),
    'p': (120, 0, 80, True),
    'm': (50, 0, 20, True)
}


def aqi(concentration):
    """Convert PM 2.5 concentration to AQI."""
    if concentration <= 12.:
        return round(4.1667 * concentration)
    elif concentration <= 35.4:
        return round(2.1030 * (concentration - 12.1) + 51.)
    elif concentration <= 55.4:
        return round(2.4623 * (concentration - 35.5) + 101.)
    elif concentration <= 150.4:
        return round(0.5163 * (concentration - 55.5) + 151.)
    elif concentration <= 250.4:
        return round(0.9910 * (concentration - 150.5) + 201.)
    elif concentration <= 500.4:
        return round(0.7963 * (concentration - 250.5) + 301.)
    else:
        return 999.


def aqilevel(aqi):
    """Return AQI level (g,y,o,r,p,m)."""
    aqi = int(aqi)
    if aqi <= 50:
        return 'g'
    elif aqi <= 100:
        return 'y'
    elif aqi <= 150:
        return 'o'
    elif aqi <= 200:
        return 'r'
    elif aqi <= 300:
        return 'p'
    else:
        return 'm'


class Display:
    """Utility class to display data on SSD1306 display."""

    def __init__(self, scl_pin, sda_pin, out_pin):
        self.i2c = machine.I2C(scl=machine.Pin(scl_pin), sda=machine.Pin(sda_pin))
        self.pin = machine.Pin(out_pin, machine.Pin.OUT)
        self.pin.value(0)  # set low to reset OLED
        self.pin.value(1)  # while OLED is running, must set high
        self.oled = ssd1306.SSD1306_I2C(128, 64, self.i2c)
        self.oled.fill(0)  # erase screen to black

    def write(self, text, posX, posY):
        """Write text to OLED display (assuming 8x8 font).

        Negative posX means right-aligned text."""
        if posX<0:
           posX = -posX-len(text)
        self.oled.fill_rect(posX * 8, posY * 8, len(text) * 8, 8, 0)
        self.oled.text(text, posX * 8, posY * 8)
        self.oled.show()

    def show(self, what, values=None):
        """Show value on oled display as configured in global display_config dict."""
        fmt = display_config[what]
        if values is None:
            self.write(*fmt)
        else:
            self.write(fmt[0] % values, fmt[1], fmt[2])


class RGBLed:

    def __init__(self, red_pin, green_pin, blue_pin, blink_delay=500, brightness=0.2):
        self.red = machine.PWM(machine.Pin(red_pin),freq=1000)
        self.green = machine.PWM(machine.Pin(green_pin),freq=1000)
        self.blue = machine.PWM(machine.Pin(blue_pin),freq=1000)
        self.blink_delay = blink_delay
        self.brightness = brightness
        self.set_color('g')
        asyncio.create_task(self._run())

    def set_channel(self, pin, value):
        """Set LED color value to brightness between 0 and 255."""
        if value>255:
            value = 255
        if value<0:
            value = 0
        value = 255 - value*self.brightness    # convert for common anode LED
        v = int(value/255.*1023.)
        pin.duty(v)

    def set_rgb(self, r, g, b):
        self.set_channel(self.red,r)
        self.set_channel(self.green,g)
        self.set_channel(self.blue,b)
        self.on = (r>0) or (b>0) or (g>0)

    def set_color(self, color):
        self.color = color
        v = rgb_colors[color]
        self.set_rgb(v[0],v[1],v[2])
        self.blinking = v[3]

    async def _run(self):
        while True:
            await asyncio.sleep_ms(self.blink_delay)
            if self.blinking:
                if self.on:
                    self.set_rgb(0,0,0)
                else:
                    v = rgb_colors[self.color]
                    self.set_rgb(v[0], v[1], v[2])


class Buzzer:
    """Control alarm buzzer."""

    def __init__(self, buzzer_pin):
        self.buzzer = machine.PWM(machine.Pin(buzzer_pin))
        self.buzzer.duty(0)
        self.freq = None
        self.duration = None
        self.pause = None
        self.remaining_beeps = 0
        asyncio.create_task(self._run())

    def alarm(self, freq=700, duration=140, pause=30, no_of_beeps=60):
        self.freq = freq
        self.duration = duration
        self.pause = pause
        self.remaining_beeps = no_of_beeps

    async def _run(self):
        while True:
            if self.remaining_beeps>0:
                # The following is not super precise ...
                self.buzzer.freq(self.freq)
                self.buzzer.duty(512)
                await asyncio.sleep_ms(self.duration)
                self.buzzer.duty(0)
                self.remaining_beeps -= 1
                await asyncio.sleep_ms(self.pause)
            else:
                await asyncio.sleep_ms(2000)


class DHTSensor:
    """Asynchronous measurement and display of temperature and humidity with DHT22 sensor."""

    def __init__(self, display, dhtPin, interval=2000):
        self.display = display
        self.sensor = dht.DHT22(machine.Pin(dhtPin))
        self.interval = max(interval,2000)    # measurement interval in ms
        self.temperature = 0.
        self.humidity = 0.
        self.dewpoint = 0.
        self.n_measurements = 0
        asyncio.create_task(self._run())

    async def _run(self):
        while True:
            await asyncio.sleep_ms(self.interval)
            self.sensor.measure()
            self.temperature = self.sensor.temperature()
            self.humidity = self.sensor.humidity()
            alpha = math.log(self.humidity/100.)+17.62*self.temperature/(243.12+self.temperature)
            self.dewpoint = 243.12*alpha/(17.62-alpha)
            self.display.show('dht_temp', self.temperature)
            self.display.show('dht_humidity', self.humidity)
            self.display.show('dewpoint', self.dewpoint)
            self.n_measurements += 1

            # Temporary
            #f = open('dht.log','a')
            #f.write('%4.1fC   %4.1f%%   %4.1fC\n' % (self.temperature, self.humidity, self.dewpoint))
            #f.close()


class PMSSensor:
    """PMS5003 particle concentration sensor."""

    def __init__(self, display, buzzer, led, to_pms_pin, from_pms_pin):
        self.display = display
        self.led = led
        self.aqi = None
        self.aqismoke = None
        self.aqilevel = None
        self.alarm_enable_threshold = 80    # alarm thresholds specified in terms of smoke AQI
        self.alarm_disable_threshold = 50
        self.alarm_on = False
        self.uart = machine.UART(1, tx=to_pms_pin, rx=from_pms_pin, baudrate=9600)
        self.pm = pms5003.PMS5003(self.uart)
        self.pm.registerCallback(self.show)

    def show(self):
        self.aqi = aqi(self.pm.pm25_env)
        self.aqismoke = aqi(self.pm.pm25_env*smoke_corr_factor)
        self.aqilevel = aqilevel(self.aqismoke)
        self.display.show('aqi', self.aqi)
        self.display.show('aqismoke', self.aqismoke)
        self.display.show('pms_25', self.pm.pm25_env)
        self.led.set_color(self.aqilevel)
        if self.aqismoke>=self.alarm_enable_threshold and not self.alarm_on:
            self.alarm_on = True
            buzzer.alarm()
        if self.aqismoke<=self.alarm_disable_threshold and self.alarm_on:
            self.alarm_on = False


def set_global_exception():
    """Global exception handler to abort on unhandled exception."""
    def handle_exception(loop, context):
        import sys
        sys.print_exception(context["exception"])
        sys.exit()
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handle_exception)


async def main():
    """Main routine creating sensors and showing heartbeat."""
    set_global_exception()
    display = Display(15,4,16)
    display.show('title')
    global rgb_led
    rgb_led = RGBLed(23, 19, 22)
    global buzzer
    buzzer = Buzzer(18)
    global dht_sensor
    dht_sensor = DHTSensor(display,17)
    global pms_sensor
    pms_sensor = PMSSensor(display,buzzer,rgb_led,14,27)

    #vext = machine.Pin(21, machine.Pin.OUT)
    #await asyncio.sleep_ms(10000)
    #vext.on()

    global n_heartbeat
    n_heartbeat = 0
    delay = 100
    pos_x = 15
    pos_y = 7
    while True:
        #display.show('debug', (dht_sensor.n_measurements, n_heartbeat))
        display.write('|',pos_x, pos_y)
        await asyncio.sleep_ms(delay)
        display.write('/', pos_x, pos_y)
        await asyncio.sleep_ms(delay)
        display.write('-', pos_x, pos_y)
        await asyncio.sleep_ms(delay)
        display.write('\\', pos_x, pos_y)
        await asyncio.sleep_ms(delay)
        n_heartbeat += 1


if __name__ == '__main__':
    asyncio.run(main())

"""
Air quality monitor in MicroPython using ESP32
"""
__author__ = 'Juerg Beringer'
__version__ = "0.1"

import machine
import ssd1306
import dht
import uasyncio as asyncio
import pms5003


# Configuration and display
display_config = {
    # each entry is a triple (text,x_pos,y_pos), negative pos_x means right-aligned text
    'title': ('Air Monitor v%s' % __version__,0,0),
    'dht_temp': ('%4.1fC',-16,3),
    'dht_humidity': ('%3.0f%%',-16,4),
    'pms_25': ('%3i ug/m3',0,7),
    'debug': ('debug %i/%i',-16,7)
}


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


class DHTSensor:
    """Asynchronous measurement and display of temperature and humidity with DHT22 sensor."""

    def __init__(self, display, dhtPin, interval=2000):
        self.display = display
        self.sensor = dht.DHT22(machine.Pin(dhtPin))
        self.interval = max(interval,2000)    # measurement interval in ms
        self.temperature = 0
        self.humidity = 0
        self.n_measurements = 0
        asyncio.create_task(self._run())

    async def _run(self):
        while True:
            await asyncio.sleep_ms(self.interval)
            self.sensor.measure()
            self.temperature = self.sensor.temperature()
            self.humidity = self.sensor.humidity()
            self.display.show('dht_temp', self.temperature)
            self.display.show('dht_humidity', self.humidity)
            self.n_measurements += 1


class PMSSensor:
    """PMS5003 particle concentration sensor."""

    def __init__(self, display, toPmsPin, fromPmsPin):
        self.display = display
        self.uart = machine.UART(1, tx=toPmsPin, rx=fromPmsPin, baudrate=9600)
        self.pm = pms5003.PMS5003(self.uart)
        self.pm.registerCallback(self.show)

    def show(self):
        self.display.show('pms_25', self.pm.pm25_env)


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
    global dht_sensor
    dht_sensor = DHTSensor(display,17)
    global pms_sensor
    pms_sensor = PMSSensor(display,14,27)
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

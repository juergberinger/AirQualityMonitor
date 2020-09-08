"""
Air quality monitor in MicroPython using ESP32
"""
__author__ = 'Juerg Beringer'
__version__ = "0.1"

import machine
import ssd1306
from dht import DHT22
import uasyncio as asyncio


# Global variables
oled = None
dht_sensor = None
current_temp = 0
current_humidity = 0
n_measure_temp = 0
n_display = 0


def hardware_init():
    """Hardware initialization"""
    i2c = machine.I2C(scl=machine.Pin(15), sda=machine.Pin(4))
    pin = machine.Pin(16, machine.Pin.OUT)
    pin.value(0)  # set GPIO16 low to reset OLED
    pin.value(1)  # while OLED is running, must set GPIO16 in high
    global oled
    oled = ssd1306.SSD1306_I2C(128, 64, i2c)
    oled.fill(0)
    oled.text('Air Monitor v%s' % __version__, 0, 0)
    oled.show()
    global dht_sensor
    dht_sensor = DHT22(machine.Pin(17))


def oled_write(text, posX, posY):
    """Write text to OLED display (assuming 8x8 font)"""
    oled.fill_rect(posX * 8, posY * 8, len(text) * 8, 8, 0)
    oled.text(text, posX * 8, posY * 8)
    oled.show()


async def measure_temp():
    global current_temp
    global current_humidity
    global n_measure_temp
    while True:
        await asyncio.sleep_ms(2000)
        dht_sensor.measure()
        current_temp = dht_sensor.temperature()
        current_humidity = dht_sensor.humidity()
        n_measure_temp += 1


def set_global_exception():
    """Global exception handler to abort on unhandled exception"""
    def handle_exception(loop, context):
        import sys
        sys.print_exception(context["exception"])
        sys.exit()
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handle_exception)


async def main():
    set_global_exception()
    asyncio.create_task(measure_temp())
    global n_display
    while True:
        oled_write('Temp = %3.1f C' % current_temp,0,3)
        oled_write('#measure = %5i' % n_measure_temp,0,5)
        oled_write('#display = %5i' % n_display,0,6)
        n_display += 1
        await asyncio.sleep_ms(100)


if __name__ == '__main__':
    hardware_init()
    asyncio.run(main())

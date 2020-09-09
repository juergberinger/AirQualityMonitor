"""
Air quality monitor in MicroPython using ESP32
"""
__author__ = 'Juerg Beringer'
__version__ = "0.1"

import machine
import ssd1306
import dht
import uasyncio as asyncio


# Configuration and display
display_config = {
    # each entry is a triple (text,x_pos,y_pos), negative pos_x means right-aligned text
    'title': ('Air Monitor v%s' % __version__,0,0),
    'dht_temp': ('%4.1fC',-16,3),
    'dht_humidity': ('%3.0f%%',-16,4),
    'heartbeat': ('debug %i/%i',-16,7)
}


# Global variables
oled = None
dht_sensor = None
current_temp = 0
current_humidity = 0
n_measure_temp = 0
n_main = 0


def hardware_init():
    """Hardware initialization"""
    i2c = machine.I2C(scl=machine.Pin(15), sda=machine.Pin(4))
    pin = machine.Pin(16, machine.Pin.OUT)
    pin.value(0)  # set GPIO16 low to reset OLED
    pin.value(1)  # while OLED is running, must set GPIO16 in high
    global oled
    oled = ssd1306.SSD1306_I2C(128, 64, i2c)
    oled.fill(0)  # erase screen to black
    global dht_sensor
    dht_sensor = dht.DHT22(machine.Pin(17))


def oled_write(text, posX, posY):
    """Write text to OLED display (assuming 8x8 font)

    Negative posX means right-aligned test."""
    if posX<0:
        posX = -posX-len(text)
    oled.fill_rect(posX * 8, posY * 8, len(text) * 8, 8, 0)
    oled.text(text, posX * 8, posY * 8)
    oled.show()


def display(what, values=None):
    """Show value on oled display as configure in display_config"""
    fmt = display_config[what]
    if values is None:
        oled_write(*fmt)
    else:
        oled_write(fmt[0] % values, fmt[1], fmt[2])


async def measure_temp():
    global current_temp
    global current_humidity
    global n_measure_temp
    while True:
        await asyncio.sleep_ms(2000)
        dht_sensor.measure()
        current_temp = dht_sensor.temperature()
        current_humidity = dht_sensor.humidity()
        display('dht_temp',current_temp)
        display('dht_humidity',current_humidity)
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
    global n_main
    display('title')
    while True:
        display('heartbeat', (n_measure_temp, n_main))
        n_main += 1
        await asyncio.sleep_ms(100)


if __name__ == '__main__':
    hardware_init()
    asyncio.run(main())

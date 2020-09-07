"""
Air quality monitor in MicroPython using ESP32
"""
__author__  = 'Juerg Beringer'

import machine
import ssd1306
import utime
import _thread


# Global variables
oled = None
counter = 0

def testThread():
    global counter
    while True:
        counter += 1
        utime.sleep_ms(10)


def init():
    """Hardware initialization"""
    i2c = machine.I2C(scl=machine.Pin(15), sda=machine.Pin(4))
    pin = machine.Pin(16, machine.Pin.OUT)
    pin.value(0) # set GPIO16 low to reset OLED
    pin.value(1) # while OLED is running, must set GPIO16 in high
    global oled
    oled = ssd1306.SSD1306_I2C(128, 64, i2c)
    oled.fill(0)
    oled.text('Air Monitor', 0, 0)
    oled.show()


def oledWrite(text, posX, posY):
    """Write and show text on OLED display (assuming 8x8 font)"""
    oled.fill_rect(posX*8, posY*8, len(text)*8, 8, 0)
    oled.text(text, posX*8, posY*8)
    oled.show()


if __name__ == '__main__':
    init()
    _thread.start_new_thread(testThread, ())


    i = 0
    while True:
        oledWrite('i = %5i' % i, 0,1)
        oledWrite('c = %5i' % counter, 0,2)
        i += 1
        oled.show()
        utime.sleep_ms(500)

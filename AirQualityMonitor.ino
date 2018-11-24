// Air quality monitor using PMS5003 sensor


// PMS5003 particle sensor
//
// PMS5003 sensor TX connected to Arduino pin 2
//
#include <SoftwareSerial.h>
SoftwareSerial pmsSerial(2, 3);

// Data structure for PMS5003 data
struct pms5003data {
  uint16_t framelen;
  uint16_t pm10_standard, pm25_standard, pm100_standard;
  uint16_t pm10_env, pm25_env, pm100_env;
  uint16_t particles_03um, particles_05um, particles_10um, particles_25um, particles_50um, particles_100um;
  uint16_t unused;
  uint16_t checksum;
};
struct pms5003data data;


// 16x2 LCD display
//
// LCD RS pin to digital pin 12
// LCD Enable pin to digital pin 11
// LCD D4 pin to digital pin 7
// LCD D5 pin to digital pin 6
// LCD D6 pin to digital pin 5
// LCD D7 pin to digital pin 4
// LCD R/W pin to ground
// 10K resistor:
// ends to +5V and ground
// wiper to LCD VO pin (pin 3) - better just put pin 3 to GND, as otherwise LCD is very dim
// Backlight: A to +5V, K via 220ohm resistor to GND
//
#include <LiquidCrystal.h>
LiquidCrystal lcd(12, 11, 7, 6, 5, 4);


void setup() {
  lcd.begin(16, 2);
  //lcd.print("hello, world!");
  pmsSerial.begin(9600);   // PMS5003 communication is at 9600 baud
}


void loop() {
  if (readPMSdata(&pmsSerial)) {
    lcd.clear();
    lcd.write("PM 2.5 = ");
    lcd.print(data.pm25_env);
    lcd.setCursor(0,1);
    lcd.write("(in ug/m^3)");
  }
}


// Routine to read PMS5003 data from Adafruit's PMS5003_Arduino
boolean readPMSdata(Stream *s) {
  if (! s->available()) {
    return false;
  }
  
  // Read a byte at a time until we get to the special '0x42' start-byte
  if (s->peek() != 0x42) {
    s->read();
    return false;
  }

  // Now read all 32 bytes
  if (s->available() < 32) {
    return false;
  }
    
  uint8_t buffer[32];    
  uint16_t sum = 0;
  s->readBytes(buffer, 32);

  // get checksum ready
  for (uint8_t i=0; i<30; i++) {
    sum += buffer[i];
  }

  /* debugging
  for (uint8_t i=2; i<32; i++) {
    Serial.print("0x"); Serial.print(buffer[i], HEX); Serial.print(", ");
  }
  Serial.println();
  */
  
  // The data comes in endian'd, this solves it so it works on all platforms
  uint16_t buffer_u16[15];
  for (uint8_t i=0; i<15; i++) {
    buffer_u16[i] = buffer[2 + i*2 + 1];
    buffer_u16[i] += (buffer[2 + i*2] << 8);
  }

  // put it into a nice struct :)
  memcpy((void *)&data, (void *)buffer_u16, 30);

  if (sum != data.checksum) {
    //Serial.println("Checksum failure");
    return false;
  }
  // success!
  return true;
}


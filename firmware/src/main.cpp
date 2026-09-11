#include <Arduino.h>
#include <U8g2lib.h>
#include <Wire.h>

// SSD1306 OLED via I2C (SCL on GPIO 9, SDA on GPIO 8 for ESP32-S3)
U8G2_SSD1306_128X64_NONAME_F_HW_I2C u8g2(U8G2_R0, /* reset=*/ U8X8_PIN_NONE, /* clock=*/ 9, /* data=*/ 8);

void setup() {
  Serial.begin(115200);
  u8g2.begin();
  
  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_ncenB08_tr);
  u8g2.drawStr(0, 10, "Optics Test OK");
  u8g2.sendBuffer();
}

void loop() {
  // Firmware event loop
  delay(1000);
}

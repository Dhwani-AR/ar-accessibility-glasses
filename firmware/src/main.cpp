#include "credentials.h"
#include <Arduino.h>
#include <ArduinoJson.h>
#include <U8g2lib.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <Wire.h>

const unsigned int udpPort = 5005;

WiFiUDP udpClient;
U8G2_SSD1306_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE, 9, 8);

QueueHandle_t subtitleQueue;

struct SubtitleData {
    char text[64];
    char speaker[16];
    int angle;
    bool haptic;
};

void runNetworkTask(void *params) {
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    while (WiFi.status() != WL_CONNECTED) {
        vTaskDelay(pdMS_TO_TICKS(500));
    }

    udpClient.begin(udpPort);

    char packetBuffer[512];
    SubtitleData parsedData;

    for (;;) {
        int packetSize = udpClient.parsePacket();
        if (packetSize) {
            int len = udpClient.read(packetBuffer, sizeof(packetBuffer) - 1);
            if (len > 0) {
                packetBuffer[len] = '\0';

                JsonDocument doc;
                DeserializationError err = deserializeJson(doc, packetBuffer);

                if (!err) {
                    strncpy(parsedData.text, doc["text"] | "", sizeof(parsedData.text) - 1);
                    strncpy(parsedData.speaker, doc["speaker"] | "Unknown", sizeof(parsedData.speaker) - 1);
                    parsedData.angle = doc["angle"] | 0;
                    parsedData.haptic = doc["haptic"] | false;

                    xQueueSend(subtitleQueue, &parsedData, portMAX_DELAY);
                }
            }
        }
        vTaskDelay(pdMS_TO_TICKS(5));
    }
}

void runDisplayTask(void *params) {
    oled.begin();
    oled.setFont(u8g2_font_ncenB08_tr);

    SubtitleData incomingData;

    for (;;) {
        if (xQueueReceive(subtitleQueue, &incomingData, portMAX_DELAY) == pdPASS) {
            oled.clearBuffer();

            oled.setCursor(0, 15);
            oled.print(incomingData.speaker);
            oled.print(": ");

            oled.setCursor(0, 35);
            oled.print(incomingData.text);

            if (incomingData.haptic) {
                // Haptic GPIO trigger logic will go here
            }

            oled.sendBuffer();
        }
    }
}

void setup() {
    Serial.begin(115200);

    subtitleQueue = xQueueCreate(5, sizeof(SubtitleData));

    xTaskCreatePinnedToCore(runNetworkTask, "NetTask", 8192, NULL, 1, NULL, 0);
    xTaskCreatePinnedToCore(runDisplayTask, "DispTask", 8192, NULL, 1, NULL, 1);
}

void loop() {
    // Frees memory by killing the default Arduino loop task since FreeRTOS handles execution
    vTaskDelete(NULL);
}

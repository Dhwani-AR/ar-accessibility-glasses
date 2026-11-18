#include "credentials.h"
#include <Arduino.h>
#include <ArduinoJson.h>
#include <U8g2lib.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <Wire.h>
#include <driver/gpio.h>
#include <driver/i2s.h>
#include <esp_rom_gpio.h>
#include <soc/gpio_sig_map.h>

const unsigned int udpPort = 5005;

const int oledSdaPin = 14;
const int oledSclPin = 21;
const int i2sSckPin = 41;
const int i2sWsPin = 42;
const int i2sSd0Pin = 1;
const int i2sSd1Pin = 47;
const int hapticPin = 38;
const int statusLedPin = 2;

const int sampleRate = 16000;
const size_t frameCount = 160;
const size_t chCount = 4;

WiFiUDP udpClient;
U8G2_SSD1306_128X64_NONAME_F_HW_I2C oled(U8G2_MIRROR_VERTICAL, U8X8_PIN_NONE, oledSclPin, oledSdaPin);

QueueHandle_t subtitleQueue;

struct __attribute__((packed)) AudioHeader {
    uint8_t type;
    uint8_t version;
    uint8_t channels;
    uint8_t reserved;
    uint32_t seq;
    uint32_t t_ms;
};

struct __attribute__((packed)) AudioPacket {
    AudioHeader hdr;
    int16_t pcm[frameCount * chCount];
};

struct SubtitleData {
    char text[64];
    char speaker[16];
    int angle;
    bool haptic;
};

const char *getDirTag(int angle) {
    if (angle >= -45 && angle <= 45) {
        return "^ FRONT";
    }
    if (angle > 45 && angle <= 135) {
        return "RIGHT >>";
    }
    if (angle >= -135 && angle < -45) {
        return "<< LEFT";
    }
    return "v REAR";
}

void drawSubtitles(const SubtitleData &sub) {
    oled.clearBuffer();

    oled.setCursor(0, 12);
    oled.print(sub.speaker);

    const char *dirTag = getDirTag(sub.angle);
    int tagWidth = oled.getStrWidth(dirTag);
    oled.setCursor(128 - tagWidth, 12);
    oled.print(dirTag);

    oled.drawHLine(0, 15, 128);

    const int lineY[3] = {29, 44, 59};
    int lineIdx = 0;
    char lineBuf[32] = "";
    char wordBuf[32] = "";
    size_t pos = 0;
    size_t len = strlen(sub.text);

    while (pos < len && lineIdx < 3) {
        while (pos < len && sub.text[pos] == ' ') {
            ++pos;
        }
        if (pos >= len) {
            break;
        }

        size_t wLen = 0;
        while (pos < len && sub.text[pos] != ' ' && wLen < sizeof(wordBuf) - 1) {
            wordBuf[wLen++] = sub.text[pos++];
        }
        wordBuf[wLen] = '\0';

        char testBuf[64];
        if (lineBuf[0] == '\0') {
            snprintf(testBuf, sizeof(testBuf), "%s", wordBuf);
        } else {
            snprintf(testBuf, sizeof(testBuf), "%s %s", lineBuf, wordBuf);
        }

        if (oled.getStrWidth(testBuf) <= 128) {
            strncpy(lineBuf, testBuf, sizeof(lineBuf) - 1);
            lineBuf[sizeof(lineBuf) - 1] = '\0';
        } else {
            if (lineBuf[0] != '\0') {
                oled.setCursor(0, lineY[lineIdx++]);
                oled.print(lineBuf);
                if (lineIdx >= 3) {
                    break;
                }
            }
            strncpy(lineBuf, wordBuf, sizeof(lineBuf) - 1);
            lineBuf[sizeof(lineBuf) - 1] = '\0';
        }
    }

    if (lineIdx < 3 && lineBuf[0] != '\0') {
        oled.setCursor(0, lineY[lineIdx]);
        oled.print(lineBuf);
    }

    oled.sendBuffer();
}

void triggerHaptic() {
    digitalWrite(statusLedPin, HIGH);
    int32_t buzzBuf[frameCount * 2];
    for (size_t i = 0; i < frameCount * 2; ++i) {
        buzzBuf[i] = (i & 64) ? 0x7FFF0000 : 0x80000000;
    }
    size_t bytesWritten = 0;
    for (int b = 0; b < 15; ++b) {
        i2s_write(I2S_NUM_0, buzzBuf, sizeof(buzzBuf), &bytesWritten, pdMS_TO_TICKS(15));
    }
    i2s_zero_dma_buffer(I2S_NUM_0);
    digitalWrite(statusLedPin, LOW);
}

void initI2sBus() {
    i2s_config_t masterCfg = {.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX | I2S_MODE_TX),
                              .sample_rate = sampleRate,
                              .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
                              .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT,
                              .communication_format = I2S_COMM_FORMAT_STAND_I2S,
                              .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
                              .dma_buf_count = 6,
                              .dma_buf_len = frameCount,
                              .use_apll = false,
                              .tx_desc_auto_clear = true,
                              .fixed_mclk = 0};

    i2s_config_t slaveCfg = masterCfg;
    slaveCfg.mode = (i2s_mode_t)(I2S_MODE_SLAVE | I2S_MODE_RX);

    i2s_pin_config_t pinCfg1 = {
        .bck_io_num = i2sSckPin, .ws_io_num = i2sWsPin, .data_out_num = I2S_PIN_NO_CHANGE, .data_in_num = i2sSd1Pin};

    i2s_pin_config_t pinCfg0 = {
        .bck_io_num = i2sSckPin, .ws_io_num = i2sWsPin, .data_out_num = hapticPin, .data_in_num = i2sSd0Pin};

    i2s_driver_install(I2S_NUM_1, &slaveCfg, 0, NULL);
    i2s_set_pin(I2S_NUM_1, &pinCfg1);

    i2s_driver_install(I2S_NUM_0, &masterCfg, 0, NULL);
    i2s_set_pin(I2S_NUM_0, &pinCfg0);

    gpio_set_direction((gpio_num_t)i2sSckPin, GPIO_MODE_INPUT_OUTPUT);
    gpio_set_direction((gpio_num_t)i2sWsPin, GPIO_MODE_INPUT_OUTPUT);
    esp_rom_gpio_connect_out_signal(i2sSckPin, I2S0I_BCK_OUT_IDX, false, false);
    esp_rom_gpio_connect_out_signal(i2sWsPin, I2S0I_WS_OUT_IDX, false, false);
    esp_rom_gpio_connect_in_signal(i2sSckPin, I2S1I_BCK_IN_IDX, false);
    esp_rom_gpio_connect_in_signal(i2sWsPin, I2S1I_WS_IN_IDX, false);

    i2s_zero_dma_buffer(I2S_NUM_1);
    i2s_zero_dma_buffer(I2S_NUM_0);
    i2s_start(I2S_NUM_1);
    i2s_start(I2S_NUM_0);
}

void runNetworkTask(void *params) {
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    while (WiFi.status() != WL_CONNECTED) {
        vTaskDelay(pdMS_TO_TICKS(500));
    }
    Serial.printf("Wi-Fi connected. ESP32 IP: %s\n", WiFi.localIP().toString().c_str());

    udpClient.begin(udpPort);
    initI2sBus();

    int32_t rawBus0[frameCount * 2];
    int32_t rawBus1[frameCount * 2];
    AudioPacket outPkt;
    char packetBuffer[512];
    SubtitleData parsedData;
    uint32_t seqNum = 0;

    for (;;) {
        size_t bytesRead0 = 0;
        size_t bytesRead1 = 0;

        i2s_read(I2S_NUM_0, rawBus0, sizeof(rawBus0), &bytesRead0, portMAX_DELAY);
        i2s_read(I2S_NUM_1, rawBus1, sizeof(rawBus1), &bytesRead1, pdMS_TO_TICKS(15));

        if (bytesRead0 == sizeof(rawBus0)) {
            bool hasBus1 = (bytesRead1 == sizeof(rawBus1));
            for (size_t i = 0; i < frameCount; ++i) {
                outPkt.pcm[i * 4 + 0] = static_cast<int16_t>(rawBus0[i * 2] >> 16);
                outPkt.pcm[i * 4 + 1] = static_cast<int16_t>(rawBus0[i * 2 + 1] >> 16);
                outPkt.pcm[i * 4 + 2] = hasBus1 ? static_cast<int16_t>(rawBus1[i * 2] >> 16) : 0;
                outPkt.pcm[i * 4 + 3] = hasBus1 ? static_cast<int16_t>(rawBus1[i * 2 + 1] >> 16) : 0;
            }

            outPkt.hdr = {0x01, 1, chCount, 0, seqNum++, millis()};
            udpClient.beginPacket(SERVER_IP, udpPort);
            udpClient.write(reinterpret_cast<const uint8_t *>(&outPkt), sizeof(outPkt));
            udpClient.endPacket();
        }

        int packetSize = udpClient.parsePacket();
        if (packetSize) {
            int len = udpClient.read(packetBuffer, sizeof(packetBuffer) - 1);
            if (len > 0) {
                packetBuffer[len] = '\0';

                JsonDocument doc;
                DeserializationError err = deserializeJson(doc, packetBuffer);

                if (!err) {
                    strncpy(parsedData.text, doc["text"] | "", sizeof(parsedData.text) - 1);
                    parsedData.text[sizeof(parsedData.text) - 1] = '\0';
                    strncpy(parsedData.speaker, doc["speaker"] | "Unknown", sizeof(parsedData.speaker) - 1);
                    parsedData.speaker[sizeof(parsedData.speaker) - 1] = '\0';
                    parsedData.angle = doc["angle"] | 0;
                    parsedData.haptic = doc["haptic"] | false;

                    xQueueSend(subtitleQueue, &parsedData, 0);
                }
            }
        }
    }
}

void runDisplayTask(void *params) {
    pinMode(statusLedPin, OUTPUT);
    digitalWrite(statusLedPin, LOW);

    vTaskDelay(pdMS_TO_TICKS(100));

    Wire.begin(oledSdaPin, oledSclPin);
    Wire.setClock(100000);
    Wire.beginTransmission(0x3C);
    uint8_t oledAddr = (Wire.endTransmission() == 0) ? 0x3C : 0x3D;
    Wire.end();

    oled.setI2CAddress(oledAddr * 2);
    oled.setBusClock(100000);
    oled.begin();
    oled.setContrast(255);
    oled.setFont(u8g2_font_ncenB08_tr);

    oled.clearBuffer();
    oled.setCursor(0, 20);
    oled.print("AR Glasses Ready");
    oled.setCursor(0, 40);
    oled.print("Waiting for UDP...");
    oled.sendBuffer();

    SubtitleData incomingData;

    for (;;) {
        if (xQueueReceive(subtitleQueue, &incomingData, portMAX_DELAY) == pdPASS) {
            drawSubtitles(incomingData);

            if (incomingData.haptic) {
                triggerHaptic();
            }
        }
    }
}

void setup() {
    Serial.begin(115200);

    subtitleQueue = xQueueCreate(5, sizeof(SubtitleData));

    xTaskCreatePinnedToCore(runNetworkTask, "NetTask", 16384, NULL, 2, NULL, 0);
    xTaskCreatePinnedToCore(runDisplayTask, "DispTask", 8192, NULL, 1, NULL, 1);
}

void loop() { vTaskDelete(NULL); }

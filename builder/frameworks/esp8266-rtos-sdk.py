"""
ESP8266 RTOS SDK

Latest ESP8266 SDK based on FreeRTOS http://bbs.espressif.com

http://github.com/espressif/ESP_8266_SDK
"""

from os.path import isdir, join

from SCons.Script import DefaultEnvironment

env = DefaultEnvironment()
platform = env.PioPlatform()

FRAMEWORK_DIR = platform.get_package_dir("framework-esp8266-rtos-sdk")
assert isdir(FRAMEWORK_DIR)

env.Prepend(
    CPPPATH=[
        join(FRAMEWORK_DIR, "include"),
        join(FRAMEWORK_DIR, "extra_include"),
        join(FRAMEWORK_DIR, "driver_lib", "include"),
        join(FRAMEWORK_DIR, "include", "espressif"),
        join(FRAMEWORK_DIR, "include", "lwip"),
        join(FRAMEWORK_DIR, "include", "lwip", "ipv4"),
        join(FRAMEWORK_DIR, "include", "lwip", "ipv6"),
        join(FRAMEWORK_DIR, "include", "nopoll"),
        join(FRAMEWORK_DIR, "include", "spiffs"),
        join(FRAMEWORK_DIR, "include", "ssl"),
        join(FRAMEWORK_DIR, "include", "json"),
        join(FRAMEWORK_DIR, "include", "openssl"),
    ],

    LIBPATH=[
        join(FRAMEWORK_DIR, "lib")
    ],

    LIBS=[
        "cirom", "crypto", "driver", "espconn", "espnow", "freertos", "gcc",
        "json", "hal", "lwip", "main", "mesh", "mirom", "net80211", "nopoll",
        "phy", "pp", "pwm", "smartconfig", "spiffs", "ssl", "wpa", "wps"
    ]
)

env.Replace(
    LDSCRIPT_PATH=[join(FRAMEWORK_DIR, "ld", "eagle.app.v6.ld")],
)

#
# Target: Build Driver Library
#

libs = []

envsafe = env.Clone()

libs.append(envsafe.BuildLibrary(
    join(FRAMEWORK_DIR, "lib", "driver"),
    join(FRAMEWORK_DIR, "driver_lib")
))

env.Prepend(LIBS=libs)

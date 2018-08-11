# Copyright 2014-present PlatformIO <contact@platformio.org>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
ESP8266 NONOS SDK

ESP8266 SDK C/C++ only

https://github.com/espressif/ESP8266_NONOS_SDK
"""

from os.path import isdir, join

from SCons.Script import DefaultEnvironment

env = DefaultEnvironment()
platform = env.PioPlatform()

FRAMEWORK_DIR = platform.get_package_dir("framework-esp8266-nonos-sdk")
assert isdir(FRAMEWORK_DIR)

env.Append(
    ASFLAGS=["-x", "assembler-with-cpp"],

    CFLAGS=[
        "-std=gnu99",
        "-Wpointer-arith",
        "-Wno-implicit-function-declaration",
        "-Wl,-EL",
        "-fno-inline-functions",
        "-nostdlib"
    ],

    CCFLAGS=[
        "-Os",  # optimize for size
        "-mlongcalls",
        "-mtext-section-literals",
        "-falign-functions=4",
        "-U__STRICT_ANSI__",
        "-ffunction-sections",
        "-fdata-sections",
        "-fno-builtin-printf"
    ],

    CXXFLAGS=[
        "-fno-rtti",
        "-fno-exceptions",
        "-std=c++11"
    ],

    LINKFLAGS=[
        "-Os",
        "-nostdlib",
        "-Wl,--no-check-sections",
        "-Wl,-static",
        "-Wl,--gc-sections",
        "-u", "call_user_start",
        "-u", "_printf_float",
        "-u", "_scanf_float"
    ],

    CPPDEFINES=[
        ("F_CPU", "$BOARD_F_CPU"),
        "__ets__",
        "ICACHE_FLASH"
    ],

    CPPPATH=[
        join(FRAMEWORK_DIR, "include"),
        join(FRAMEWORK_DIR, "extra_include"),
        join(FRAMEWORK_DIR, "driver_lib", "include"),
        join(FRAMEWORK_DIR, "include", "espressif"),
        join(FRAMEWORK_DIR, "include", "lwip"),
        join(FRAMEWORK_DIR, "include", "lwip", "ipv4"),
        join(FRAMEWORK_DIR, "include", "lwip", "ipv6"),
        join(FRAMEWORK_DIR, "include", "nopoll"),
        join(FRAMEWORK_DIR, "include", "ssl"),
        join(FRAMEWORK_DIR, "include", "json"),
        join(FRAMEWORK_DIR, "include", "openssl"),
        join("$SDK_ESP8266_DIR", "include"), "$PROJECTSRC_DIR"
    ],

    LIBPATH=[
        join(FRAMEWORK_DIR, "lib")
    ],

    LIBS=[
        "airkiss", "at", "c", "crypto", "driver", "espnow", "gcc", "json", "lwip",
        "main", "mbedtls", "mesh", "net80211", "phy", "pp", "pwm", "smartconfig",
        "ssl", "upgrade", "wpa", "wpa2", "wps"
    ]
)

# copy CCFLAGS to ASFLAGS (-x assembler-with-cpp mode)
env.Append(ASFLAGS=env.get("CCFLAGS", [])[:])

env.Replace(
    LDSCRIPT_PATH=[join(FRAMEWORK_DIR, "ld", "eagle.app.v6.ld")],
    UPLOAD_ADDRESS="0x10000"
)

#
# Target: Build Driver Library
#

libs = []

libs.append(env.BuildLibrary(
    join(FRAMEWORK_DIR, "lib", "driver"),
    join(FRAMEWORK_DIR, "driver_lib")
))

env.Prepend(LIBS=libs)

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

#
# Default flags for bare-metal programming (without any framework layers)
#

from os.path import join

from SCons.Script import Import

Import("env")

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
        "-fdata-sections"
    ],

    CXXFLAGS=[
        "-fno-rtti",
        "-fno-exceptions",
        "-std=c++11"
    ],

    CPPDEFINES=[
        ("F_CPU", "$BOARD_F_CPU"),
        "__ets__",
        "ICACHE_FLASH"
    ],

    LINKFLAGS=[
        "-Os",
        "-nostdlib",
        "-Wl,--no-check-sections",
        "-u", "call_user_start",
        "-u", "_printf_float",
        "-u", "_scanf_float",
        "-Wl,-static",
        "-Wl,--gc-sections"
    ],

    CPPPATH=[
        join("$SDK_ESP8266_DIR", "include"), "$PROJECTSRC_DIR"
    ],

    LIBPATH=[
        join("$SDK_ESP8266_DIR", "lib"),
        join("$SDK_ESP8266_DIR", "ld")
    ],

    LIBS=[
        "c", "gcc", "phy", "pp", "net80211", "lwip", "wpa", "wpa2",
        "main", "wps", "crypto", "json", "ssl", "pwm", "upgrade",
        "smartconfig", "airkiss", "at"
    ]
)

# copy CCFLAGS to ASFLAGS (-x assembler-with-cpp mode)
env.Append(ASFLAGS=env.get("CCFLAGS", [])[:])

env.Replace(
    UPLOAD_ADDRESS="0x40000"
)

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

from SCons.Script import Builder, DefaultEnvironment

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
        join(FRAMEWORK_DIR, "include", "openssl")
    ],

    LIBPATH=[
        join(FRAMEWORK_DIR, "lib"),
        join(FRAMEWORK_DIR, "ld")
    ],

    LIBS=[
        "airkiss", "at", "c", "crypto", "driver", "espnow", "gcc", "json",
        "lwip", "main", "mbedtls", "mesh", "net80211", "phy", "pp", "pwm",
        "smartconfig", "ssl", "upgrade", "wpa", "wpa2", "wps"
    ],

    BUILDERS=dict(
        ElfToBin=Builder(
            action=env.VerboseAction(" ".join([
                '"%s"' % join(platform.get_package_dir("tool-esptool"), "esptool"),
                "-eo", "$SOURCE",
                "-bo", "${TARGET}",
                "-bm", "$BOARD_FLASH_MODE",
                "-bf", "${__get_board_f_flash(__env__)}",
                "-bz", "${__get_flash_size(__env__)}",
                "-bs", ".text",
                "-bs", ".data",
                "-bs", ".rodata",
                "-bc", "-ec",
                "-eo", "$SOURCE",
                "-es", ".irom0.text", "${TARGET}.irom0text.bin",
                "-ec", "-v"
            ]), "Building $TARGET"),
            suffix=".bin"
        )
    )
)

# copy CCFLAGS to ASFLAGS (-x assembler-with-cpp mode)
env.Append(ASFLAGS=env.get("CCFLAGS", [])[:])

if not env.BoardConfig().get("build.ldscript", ""):
    env.Replace(
        LDSCRIPT_PATH=join(FRAMEWORK_DIR, "ld", "eagle.app.v6.ld")
    )

board_flash_size = int(env.BoardConfig().get("upload.maximum_size", 0))
if board_flash_size > 8388608:
    init_data_flash_address = 0xffc000  # for 16 MB
elif board_flash_size > 4194304:
    init_data_flash_address = 0x7fc000  # for 8 MB
elif board_flash_size > 2097152:
    init_data_flash_address = 0x3fc000  # for 4 MB
elif board_flash_size > 1048576:
    init_data_flash_address = 0x1fc000  # for 2 MB
elif board_flash_size > 524288:
    init_data_flash_address = 0xfc000  # for 1 MB
else:
    init_data_flash_address = 0x7c000  # for 512 kB

env.Append(
    FLASH_EXTRA_IMAGES=[
        ("0x10000", join("$BUILD_DIR", "${PROGNAME}.bin.irom0text.bin")),
        (hex(init_data_flash_address),
            join(FRAMEWORK_DIR, "bin", "esp_init_data_default.bin")),
        (hex(init_data_flash_address + 0x2000),
            join(FRAMEWORK_DIR, "bin", "blank.bin"))
    ]
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

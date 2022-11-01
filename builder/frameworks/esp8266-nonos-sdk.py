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

from os.path import isdir, join, isfile

from SCons.Script import Builder, DefaultEnvironment

env = DefaultEnvironment()
platform = env.PioPlatform()

FRAMEWORK_DIR = platform.get_package_dir("framework-esp8266-nonos-sdk")
assert isdir(FRAMEWORK_DIR)

env.Append(
    ASFLAGS=[
        "-mlongcalls",
    ],
    ASPPFLAGS=[
        "-x", "assembler-with-cpp",
    ],

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
        "-std=c++11",
        "-Wno-literal-suffix"
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
        join(FRAMEWORK_DIR, "driver_lib", "include"),
        join(FRAMEWORK_DIR, "third_party", "include")
    ],

    LIBPATH=[
        join(FRAMEWORK_DIR, "lib"),
        join(FRAMEWORK_DIR, "ld")
    ],

    LIBS=[
        "airkiss", "at", "c", "crypto", "driver", "espnow", "gcc", "json",
        "lwip", "main", "mbedtls", "net80211", "phy", "pp", "pwm",
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

if not env.BoardConfig().get("build.ldscript", ""):
    env.Replace(
        LDSCRIPT_PATH=join(FRAMEWORK_DIR, "ld", "eagle.app.v6.ld")
    )

# evaluate SPI_FLASH_SIZE_MAP flag for NONOS_SDK 3.x and set CCFLAG
board_flash_size = int(env.BoardConfig().get("upload.maximum_size", 524288))
flash_size_maps = [0.5, 0.25, 1.0, 0.0, 0.0, 2.0, 4.0, 0.0, 8.0, 16.0]  # ignore maps 3 and 4.prefer 5 and 6
flash_sizes_str = ['512KB','256KB','1MB','2MB','4MB','2MB-c1','4MB-c1','4MB-c2','8MB','16MB']
try:
    flash_size_map = flash_size_maps.index(board_flash_size/1048576)
    flash_size_str = flash_sizes_str[flash_size_map]
except:
    flash_size_map = 6
    flash_size_str = '4MB-c1'
# for OTA, only size maps 5, 6, 8 and 9 are supported to avoid linking twice for user1 and user2

env.Append(CCFLAGS=["-DSPI_FLASH_SIZE_MAP="+str(flash_size_map)])     # NONOS-SDK 3.x user_main.c need it

init_data_flash_address  = board_flash_size-0x4000     # 3fc000 for 4M board data_bin


esp_init_data_default_file = "esp_init_data_default_v08.bin"       # new in NONS 3.04
if not isfile(join(FRAMEWORK_DIR, "bin", esp_init_data_default_file)):
    esp_init_data_default_file = "esp_init_data_default.bin"

env.Append(
    FLASH_EXTRA_IMAGES=[
        ("0x10000", join("$BUILD_DIR", "${PROGNAME}.bin.irom0text.bin")),
        (hex(init_data_flash_address),
            join(FRAMEWORK_DIR, "bin", esp_init_data_default_file)),
        (hex(init_data_flash_address + 0x2000),
            join(FRAMEWORK_DIR, "bin", "blank.bin"))
    ]
)


#
# Target: Build Driver Library
#

libs = []

if False:
    libs.append(env.BuildLibrary(
        join(FRAMEWORK_DIR, "lib", "driver"),
        join(FRAMEWORK_DIR, "driver_lib")
    ))

env.Prepend(LIBS=libs)

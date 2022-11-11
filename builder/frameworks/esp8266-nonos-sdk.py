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
SConscript("_embed_files.py", exports="env")
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
    ]
)


###################################################################################
# OTA support

board = env.BoardConfig()
partitions_csv = board.get("build.partitions", "partitions_singleapp.csv")

# choose LDSCRIPT_PATH based on OTA
if not board.get("build.ldscript", ""):
    if "ota" in partitions_csv:         # flash map size >= 5 only!!!
        LDSCRIPT_PATH=join(FRAMEWORK_DIR, "ld", "eagle.app.v6.new.2048.ld")
    else:
        LDSCRIPT_PATH=join(FRAMEWORK_DIR, "ld", "eagle.app.v6.ld")
    env.Replace(LDSCRIPT_PATH=LDSCRIPT_PATH)


# evaluate SPI_FLASH_SIZE_MAP flag for NONOS_SDK 3.x and set CCFLAG
board_flash_size = int(board.get("upload.maximum_size", 524288))
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
env.Append(FLASH_SIZE_STR=flash_size_str)                             # required for custom uploader


# create binaries list to upload

if "ota" in partitions_csv:     # if OTA, flash user1 but generate user1 and user2
    boot_bin  = join(FRAMEWORK_DIR, "bin", "boot_v1.7.bin")
    user_bin  = join("$BUILD_DIR", "${PROGNAME}.bin.user1.bin")      # firmware.bin.user1.bin # user1.4096.new.6.bin
    user_addr = 0x1000
else:                           # non ota
    boot_bin  = join("$BUILD_DIR", "${PROGNAME}.bin")                # firmware.bin # eagle.flash.bin
    user_bin  = join("$BUILD_DIR", "${PROGNAME}.bin.irom0text.bin")  # firmware.bin.irom0text.bin # eagle.irom0text.bin
    user_addr = 0x10000


# check the init_data_default file to use
esp_init_data_default_file = "esp_init_data_default_v08.bin"       # new in NONOS 3.04
if not isfile(join(FRAMEWORK_DIR, "bin", esp_init_data_default_file)):
    esp_init_data_default_file = "esp_init_data_default.bin"
    
data_bin  = join(FRAMEWORK_DIR, "bin", esp_init_data_default_file)
blank_bin = join(FRAMEWORK_DIR, "bin", "blank.bin")
rf_cal_addr    = board_flash_size-0x5000     # 3fb000 for 4M board blank_bin
phy_data_addr  = board_flash_size-0x4000     # 3fc000 for 4M board data_bin
sys_param_addr = board_flash_size-0x2000     # 3fe000 for 4M board blank_bin

env.Append(
    FLASH_EXTRA_IMAGES=[
        (hex(0),              boot_bin),
        (hex(user_addr),      user_bin),
        (hex(phy_data_addr),  data_bin),
        (hex(sys_param_addr), blank_bin),
        (hex(rf_cal_addr),    blank_bin),
        ("--flash_mode", "$BOARD_FLASH_MODE"),
        ("--flash_freq", "$${__get_board_f_flash(__env__)}m"),
        ("--flash_size", "$FLASH_SIZE_STR")     # required by NONOS 3.0.4
    ]
)

# register genbin.py BUILDER which allows to create OTA files 
if "ota" in partitions_csv:     # if OTA, flash user1 but generate user1 and user2
    env.Append(
        BUILDERS=dict(
            ElfToBin=Builder(
                action=env.VerboseAction(" ".join([
                    '"%s"' % env.subst("$PYTHONEXE"), join(platform.get_package_dir("tool-genbin"), "genbin.py"),
                    "12",       # create firmware.bin.user1.bin and firmware.bin.user2.bin
                    "$BOARD_FLASH_MODE", "${__get_board_f_flash(__env__)}m", "$FLASH_SIZE_STR",
                    "$SOURCE", "${TARGET}.user1.bin", "${TARGET}.user2.bin"
                           # could have used espressif naming: user1.4096.new.6.bin or user1.16384.new.9.bin
                ]), "Building $TARGET"),
                suffix=".bin"
            )
        )
    )
else:
    env.Append(
        BUILDERS=dict(
            ElfToBin=Builder(
                action=env.VerboseAction(" ".join([
                    '"%s"' % env.subst("$PYTHONEXE"), join(platform.get_package_dir("tool-genbin"), "genbin.py"),
                    "0",        # create firmware.bin and firmware.bin.irom0text.bin
                    "$BOARD_FLASH_MODE", "${__get_board_f_flash(__env__)}m", "$FLASH_SIZE_STR",
                    "$SOURCE", "${TARGET}", "${TARGET}.irom0text.bin"
                ]), "Building $TARGET"),
                suffix=".bin"
            )
        )
    )

###################################################################################


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

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

# pylint: disable=redefined-outer-name

import re
from os.path import join

from SCons.Script import (ARGUMENTS, COMMAND_LINE_TARGETS, AlwaysBuild,
                          Builder, Default, DefaultEnvironment)


def _get_flash_size(env):
    # use board's flash size by default
    board_max_size = int(env.BoardConfig().get("upload.maximum_size", 0))

    # check if user overrides LD Script
    match = re.search(r"\.flash\.(\d+)(m|k).*\.ld", env.GetActualLDScript())
    if match:
        if match.group(2) == "k":
            board_max_size = int(match.group(1)) * 1024
        elif match.group(2) == "m":
            board_max_size = int(match.group(1)) * 1024 * 1024

    return ("%dK" % (board_max_size / 1024) if board_max_size < 1048576
            else "%dM" % (board_max_size / 1048576))


def _get_board_f_flash(env):
    frequency = env.subst("$BOARD_F_FLASH")
    frequency = str(frequency).replace("L", "")
    return int(int(frequency) / 1000000)


env = DefaultEnvironment()
platform = env.PioPlatform()

env.Replace(
    __get_flash_size=_get_flash_size,
    __get_board_f_flash=_get_board_f_flash,

    AR="xtensa-lx106-elf-ar",
    AS="xtensa-lx106-elf-as",
    CC="xtensa-lx106-elf-gcc",
    CXX="xtensa-lx106-elf-g++",
    OBJCOPY="esptool",
    RANLIB="xtensa-lx106-elf-ranlib",
    SIZETOOL="xtensa-lx106-elf-size",

    ARFLAGS=["rcs"],

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

    #
    # Packages
    #

    FRAMEWORK_ARDUINOESP8266_DIR=platform.get_package_dir(
        "framework-arduinoespressif8266"),
    SDK_ESP8266_DIR=platform.get_package_dir("sdk-esp8266"),

    #
    # Upload
    #

    UPLOADER="esptool",
    UPLOADEROTA=join(platform.get_package_dir("tool-espotapy") or "",
                     "espota.py"),

    UPLOADERFLAGS=[
        "-cd", "$UPLOAD_RESETMETHOD",
        "-cb", "$UPLOAD_SPEED",
        "-cp", '"$UPLOAD_PORT"'
    ],
    UPLOADEROTAFLAGS=[
        "--debug",
        "--progress",
        "-i", "$UPLOAD_PORT",
        "$UPLOAD_FLAGS"
    ],

    UPLOADCMD='$UPLOADER $UPLOADERFLAGS -cf $SOURCE',
    UPLOADOTACMD='"$PYTHONEXE" "$UPLOADEROTA" $UPLOADEROTAFLAGS -f $SOURCE',

    #
    # Misc
    #

    MKSPIFFSTOOL="mkspiffs",
    SIZEPRINTCMD='$SIZETOOL -B -d $SOURCES',

    PROGNAME="firmware",
    PROGSUFFIX=".elf"
)

env.Append(
    ASFLAGS=env.get("CCFLAGS", [])[:]
)

if int(ARGUMENTS.get("PIOVERBOSE", 0)):
    env.Prepend(UPLOADERFLAGS=["-vv"])


#
# SPIFFS
#

def fetch_spiffs_size(env):
    spiffs_re = re.compile(
        r"PROVIDE\s*\(\s*_SPIFFS_(\w+)\s*=\s*(0x[\dA-F]+)\s*\)")
    with open(env.GetActualLDScript()) as f:
        for line in f.readlines():
            match = spiffs_re.search(line)
            if not match:
                continue
            env["SPIFFS_%s" % match.group(1).upper()] = match.group(2)

    assert all([k in env for k in ["SPIFFS_START", "SPIFFS_END", "SPIFFS_PAGE",
                                   "SPIFFS_BLOCK"]])

    # esptool flash starts from 0
    for k in ("SPIFFS_START", "SPIFFS_END"):
        _value = 0
        if int(env[k], 16) < 0x40300000:
            _value = int(env[k], 16) & 0xFFFFF
        else:
            _value = int(env[k], 16) & 0xFFFFFF
            _value -= 0x200000  # esptool offset

        env[k] = hex(_value)


def __fetch_spiffs_size(target, source, env):
    fetch_spiffs_size(env)
    return (target, source)


env.Append(
    BUILDERS=dict(
        DataToBin=Builder(
            action=env.VerboseAction(" ".join([
                '"$MKSPIFFSTOOL"',
                "-c", "$SOURCES",
                "-p", "${int(SPIFFS_PAGE, 16)}",
                "-b", "${int(SPIFFS_BLOCK, 16)}",
                "-s", "${int(SPIFFS_END, 16) - int(SPIFFS_START, 16)}",
                "$TARGET"
            ]), "Building SPIFFS image from '$SOURCES' directory to $TARGET"),
            emitter=__fetch_spiffs_size,
            source_factory=env.Dir,
            suffix=".bin"
        )
    )
)

if "uploadfs" in COMMAND_LINE_TARGETS:
    env.Append(
        UPLOADERFLAGS=["-ca", "$SPIFFS_START"],
        UPLOADEROTAFLAGS=["-s"]
    )

#
# Framework and SDK specific configuration
#

if "PIOFRAMEWORK" in env:
    env.Append(
        BUILDERS=dict(
            ElfToBin=Builder(
                action=env.VerboseAction(" ".join([
                    '"$OBJCOPY"',
                    "-eo",
                    '"%s"' % join("$FRAMEWORK_ARDUINOESP8266_DIR",
                                  "bootloaders", "eboot", "eboot.elf"),
                    "-bo", "$TARGET",
                    "-bm", "$BOARD_FLASH_MODE",
                    "-bf", "${__get_board_f_flash(__env__)}",
                    "-bz", "${__get_flash_size(__env__)}",
                    "-bs", ".text",
                    "-bp", "4096",
                    "-ec",
                    "-eo", "$SOURCES",
                    "-bs", ".irom0.text",
                    "-bs", ".text",
                    "-bs", ".data",
                    "-bs", ".rodata",
                    "-bc", "-ec"
                ]), "Building $TARGET"),
                suffix=".bin"
            )
        )
    )

    # Handle uploading via OTA
    ota_port = None
    if env.get("UPLOAD_PORT"):
        ota_port = re.match(
            r"\"?((([0-9]{1,3}\.){3}[0-9]{1,3})|.+\.local)\"?$",
            env.get("UPLOAD_PORT"))
    if ota_port:
        env.Replace(UPLOADCMD="$UPLOADOTACMD")

# Configure native SDK
else:
    env.Append(
        CPPPATH=[
            join("$SDK_ESP8266_DIR", "include"), "$PROJECTSRC_DIR"
        ],

        LIBPATH=[
            join("$SDK_ESP8266_DIR", "lib"),
            join("$SDK_ESP8266_DIR", "ld")
        ],

        BUILDERS=dict(
            ElfToBin=Builder(
                action=env.VerboseAction(" ".join([
                    '"$OBJCOPY"',
                    "-eo", "$SOURCES",
                    "-bo", "${TARGETS[0]}",
                    "-bm", "$BOARD_FLASH_MODE",
                    "-bf", "${__get_board_f_flash(__env__)}",
                    "-bz", "${__get_flash_size(__env__)}",
                    "-bs", ".text",
                    "-bs", ".data",
                    "-bs", ".rodata",
                    "-bc", "-ec",
                    "-eo", "$SOURCES",
                    "-es", ".irom0.text", "${TARGETS[1]}",
                    "-ec", "-v"
                ]), "Building $TARGET"),
                suffix=".bin"
            )
        )
    )
    env.Replace(
        LIBS=[
            "c", "gcc", "phy", "pp", "net80211", "lwip", "wpa", "wpa2",
            "main", "wps", "crypto", "json", "ssl", "pwm", "upgrade",
            "smartconfig", "airkiss", "at"
        ],

        UPLOADERFLAGS=[
            "-vv",
            "-cd", "$UPLOAD_RESETMETHOD",
            "-cb", "$UPLOAD_SPEED",
            "-cp", '"$UPLOAD_PORT"',
            "-ca", "0x00000",
            "-cf", "${SOURCES[0]}",
            "-ca", "0x40000",
            "-cf", "${SOURCES[1]}"
        ],

        UPLOADCMD='$UPLOADER $UPLOADERFLAGS',
    )

#
# Target: Build executable and linkable firmware or SPIFFS image
#


def __tmp_hook_before_pio_3_2():
    env.ProcessFlags(env.get("BUILD_FLAGS"))
    # append specified LD_SCRIPT
    if ("LDSCRIPT_PATH" in env and
            not any(["-Wl,-T" in f for f in env['LINKFLAGS']])):
        env.Append(LINKFLAGS=['-Wl,-T"$LDSCRIPT_PATH"'])


target_elf = None
if "nobuild" in COMMAND_LINE_TARGETS:
    if set(["uploadfs", "uploadfsota"]) & set(COMMAND_LINE_TARGETS):
        __tmp_hook_before_pio_3_2()
        fetch_spiffs_size(env)
        target_firm = join("$BUILD_DIR", "spiffs.bin")
    elif "PIOFRAMEWORK" not in env:
        target_firm = [
            join("$BUILD_DIR", "firmware_00000.bin"),
            join("$BUILD_DIR", "firmware_40000.bin")
        ]
    else:
        target_firm = join("$BUILD_DIR", "firmware.bin")
else:
    if set(["buildfs", "uploadfs", "uploadfsota"]) & set(COMMAND_LINE_TARGETS):
        __tmp_hook_before_pio_3_2()
        target_firm = env.DataToBin(
            join("$BUILD_DIR", "spiffs"), "$PROJECTDATA_DIR")
        AlwaysBuild(target_firm)
        AlwaysBuild(env.Alias("buildfs", target_firm))
    else:
        target_elf = env.BuildProgram()
        if "PIOFRAMEWORK" not in env:
            target_firm = env.ElfToBin([join("$BUILD_DIR", "firmware_00000"),
                                        join("$BUILD_DIR", "firmware_40000")],
                                       target_elf)
        else:
            target_firm = env.ElfToBin(
                join("$BUILD_DIR", "firmware"), target_elf)

AlwaysBuild(env.Alias("nobuild", target_firm))
target_buildprog = env.Alias("buildprog", target_firm, target_firm)

#
# Target: Print binary size
#

target_size = env.Alias(
    "size", target_elf,
    env.VerboseAction("$SIZEPRINTCMD", "Calculating size $SOURCE"))
AlwaysBuild(target_size)

#
# Target: Upload firmware or SPIFFS image
#

target_upload = env.Alias(
    ["upload", "uploadfs"], target_firm,
    [env.VerboseAction(env.AutodetectUploadPort, "Looking for upload port..."),
     env.VerboseAction("$UPLOADCMD", "Uploading $SOURCE")])
env.AlwaysBuild(target_upload)


#
# Default targets
#

Default([target_buildprog, target_size])

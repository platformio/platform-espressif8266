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
from platformio import util

#
# Helpers
#


def _get_board_f_flash(env):
    frequency = env.subst("$BOARD_F_FLASH")
    frequency = str(frequency).replace("L", "")
    return int(int(frequency) / 1000000)


def _parse_size(value):
    if isinstance(value, int):
        return value
    elif value.isdigit():
        return int(value)
    elif value.startswith("0x"):
        return int(value, 16)
    elif value[-1].upper() in ("K", "M"):
        base = 1024 if value[-1].upper() == "K" else 1024 * 1024
        return int(value[:-1]) * base
    return value


@util.memoized()
def _parse_ld_sizes(ldscript_path):
    assert ldscript_path
    result = {}
    # get flash size from board's manifest
    result['flash_size'] = int(env.BoardConfig().get("upload.maximum_size", 0))
    # get flash size from LD script path
    match = re.search(r"\.flash\.(\d+[mk]).*\.ld", ldscript_path)
    if match:
        result['flash_size'] = _parse_size(match.group(1))

    appsize_re = re.compile(
        r"irom0_0_seg\s*:.+len\s*=\s*(0x[\da-f]+)", flags=re.I)
    spiffs_re = re.compile(
        r"PROVIDE\s*\(\s*_SPIFFS_(\w+)\s*=\s*(0x[\da-f]+)\s*\)", flags=re.I)
    with open(ldscript_path) as fp:
        for line in fp.readlines():
            line = line.strip()
            if not line or line.startswith("/*"):
                continue
            match = appsize_re.search(line)
            if match:
                result['app_size'] = _parse_size(match.group(1))
                continue
            match = spiffs_re.search(line)
            if match:
                result['spiffs_%s' % match.group(1)] = _parse_size(
                    match.group(2))
    return result


def _get_flash_size(env):
    ldsizes = _parse_ld_sizes(env.GetActualLDScript())
    if ldsizes['flash_size'] < 1048576:
        return "%dK" % (ldsizes['flash_size'] / 1024)
    return "%dM" % (ldsizes['flash_size'] / 1048576)


def fetch_spiffs_size(env):
    ldsizes = _parse_ld_sizes(env.GetActualLDScript())
    for key in ldsizes:
        if key.startswith("spiffs_"):
            env[key.upper()] = ldsizes[key]

    assert all([
        k in env
        for k in ["SPIFFS_START", "SPIFFS_END", "SPIFFS_PAGE", "SPIFFS_BLOCK"]
    ])

    # esptool flash starts from 0
    for k in ("SPIFFS_START", "SPIFFS_END"):
        _value = 0
        if env[k] < 0x40300000:
            _value = env[k] & 0xFFFFF
        elif env[k] < 0x411FB000:
            _value = env[k] & 0xFFFFFF
            _value -= 0x200000  # correction
        else:
            _value = env[k] & 0xFFFFFF
            _value += 0xE00000  # correction

        env[k] = _value


def __fetch_spiffs_size(target, source, env):
    fetch_spiffs_size(env)
    return (target, source)


def _update_max_upload_size(env):
    ldsizes = _parse_ld_sizes(env.GetActualLDScript())
    if ldsizes and "app_size" in ldsizes:
        env.BoardConfig().update("upload.maximum_size", ldsizes['app_size'])


########################################################

env = DefaultEnvironment()
platform = env.PioPlatform()

env.Replace(
    __get_flash_size=_get_flash_size,
    __get_board_f_flash=_get_board_f_flash,

    AR="xtensa-lx106-elf-ar",
    AS="xtensa-lx106-elf-as",
    CC="xtensa-lx106-elf-gcc",
    CXX="xtensa-lx106-elf-g++",
    GDB="xtensa-lx106-elf-gdb",
    OBJCOPY="esptool",
    RANLIB="xtensa-lx106-elf-ranlib",
    SIZETOOL="xtensa-lx106-elf-size",

    ARFLAGS=["rc"],

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

    SIZEPROGREGEXP=r"^(?:\.irom0\.text|\.text|\.data|\.rodata|)\s+([0-9]+).*",
    SIZEDATAREGEXP=r"^(?:\.data|\.rodata|\.bss)\s+([0-9]+).*",
    SIZECHECKCMD="$SIZETOOL -A -d $SOURCES",
    SIZEPRINTCMD='$SIZETOOL -B -d $SOURCES',

    PROGSUFFIX=".elf"
)

if int(ARGUMENTS.get("PIOVERBOSE", 0)):
    env.Prepend(UPLOADERFLAGS=["-vv"])

# Allow user to override via pre:script
if env.get("PROGNAME", "program") == "program":
    env.Replace(PROGNAME="firmware")

#
# Keep support for old LD Scripts
#

env.Replace(BUILD_FLAGS=[
    f.replace("esp8266.flash", "eagle.flash") if "esp8266.flash" in f else f
    for f in env.get("BUILD_FLAGS", [])
])

env.Append(
    BUILDERS=dict(
        DataToBin=Builder(
            action=env.VerboseAction(" ".join([
                '"$MKSPIFFSTOOL"',
                "-c", "$SOURCES",
                "-p", "$SPIFFS_PAGE",
                "-b", "$SPIFFS_BLOCK",
                "-s", "${SPIFFS_END - SPIFFS_START}",
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
        UPLOADERFLAGS=["-ca", "${hex(SPIFFS_START)}"],
        UPLOADEROTAFLAGS=["-s"]
    )

#
# Framework and SDK specific configuration
#

if env.subst("$PIOFRAMEWORK") in ("arduino", "simba"):
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
            r"\"?((([0-9]{1,3}\.){3}[0-9]{1,3})|[^\\/]+\.[^\\/]+)\"?$",
            env.get("UPLOAD_PORT"))
    if ota_port:
        env.Replace(UPLOADCMD="$UPLOADOTACMD")

else:
    # ESP8266 RTOS SDK and Native SDK common configuration
    env.Append(
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
        UPLOADERFLAGS=[
            "-vv",
            "-cd", "$UPLOAD_RESETMETHOD",
            "-cb", "$UPLOAD_SPEED",
            "-cp", '"$UPLOAD_PORT"',
            "-ca", "0x00000",
            "-cf", "${SOURCES[0]}",
            "-ca", "$UPLOAD_ADDRESS",
            "-cf", "${SOURCES[1]}"
        ],
        UPLOADCMD='$UPLOADER $UPLOADERFLAGS',
    )

if not env.get("PIOFRAMEWORK"):
    env.SConscript("frameworks/_bare.py", exports="env")

#
# Target: Build executable and linkable firmware or SPIFFS image
#

target_elf = env.BuildProgram()
if "nobuild" in COMMAND_LINE_TARGETS:
    if set(["uploadfs", "uploadfsota"]) & set(COMMAND_LINE_TARGETS):
        fetch_spiffs_size(env)
        target_firm = join("$BUILD_DIR", "spiffs.bin")
    elif env.subst("$PIOFRAMEWORK") in ("arduino", "simba"):
        target_firm = join("$BUILD_DIR", "${PROGNAME}.bin")
    else:
        target_firm = [
            join("$BUILD_DIR", "eagle.flash.bin"),
            join("$BUILD_DIR", "eagle.irom0text.bin")
        ]
else:
    if set(["buildfs", "uploadfs", "uploadfsota"]) & set(COMMAND_LINE_TARGETS):
        target_firm = env.DataToBin(
            join("$BUILD_DIR", "spiffs"), "$PROJECTDATA_DIR")
        AlwaysBuild(target_firm)
        AlwaysBuild(env.Alias("buildfs", target_firm))
    else:
        if env.subst("$PIOFRAMEWORK") in ("arduino", "simba"):
            target_firm = env.ElfToBin(
                join("$BUILD_DIR", "${PROGNAME}"), target_elf)
        else:
            target_firm = env.ElfToBin([
                join("$BUILD_DIR", "eagle.flash.bin"),
                join("$BUILD_DIR", "eagle.irom0text.bin")
            ], target_elf)

AlwaysBuild(env.Alias("nobuild", target_firm))
target_buildprog = env.Alias("buildprog", target_firm, target_firm)

# update max upload size based on CSV file
if env.get("PIOMAINPROG"):
    env.AddPreAction(
        "checkprogsize",
        env.VerboseAction(
            lambda source, target, env: _update_max_upload_size(env),
            "Retrieving maximum program size $SOURCE"))
# remove after PIO Core 3.6 release
elif set(["checkprogsize", "upload"]) & set(COMMAND_LINE_TARGETS):
    _update_max_upload_size(env)

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

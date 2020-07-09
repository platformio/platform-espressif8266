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
import sys
from os.path import join


from SCons.Script import (COMMAND_LINE_TARGETS, AlwaysBuild,
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
    filesystem_re = re.compile(
        r"PROVIDE\s*\(\s*_%s_(\w+)\s*=\s*(0x[\da-f]+)\s*\)" % "FS"
        if "arduino" in env.subst("$PIOFRAMEWORK")
        else "SPIFFS",
        flags=re.I,
    )
    with open(ldscript_path) as fp:
        for line in fp.readlines():
            line = line.strip()
            if not line or line.startswith("/*"):
                continue
            match = appsize_re.search(line)
            if match:
                result['app_size'] = _parse_size(match.group(1))
                continue
            match = filesystem_re.search(line)
            if match:
                result['fs_%s' % match.group(1)] = _parse_size(
                    match.group(2))
    return result


def _get_flash_size(env):
    ldsizes = _parse_ld_sizes(env.GetActualLDScript())
    if ldsizes['flash_size'] < 1048576:
        return "%dK" % (ldsizes['flash_size'] / 1024)
    return "%dM" % (ldsizes['flash_size'] / 1048576)


def fetch_fs_size(env):
    ldsizes = _parse_ld_sizes(env.GetActualLDScript())
    for key in ldsizes:
        if key.startswith("fs_"):
            env[key.upper()] = ldsizes[key]

    assert all([
        k in env
        for k in ["FS_START", "FS_END", "FS_PAGE", "FS_BLOCK"]
    ])

    # esptool flash starts from 0
    for k in ("FS_START", "FS_END"):
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


def __fetch_fs_size(target, source, env):
    fetch_fs_size(env)
    return (target, source)


def _update_max_upload_size(env):
    ldsizes = _parse_ld_sizes(env.GetActualLDScript())
    if ldsizes and "app_size" in ldsizes:
        env.BoardConfig().update("upload.maximum_size", ldsizes['app_size'])


def get_esptoolpy_reset_flags(resetmethod):
    # no dtr, no_sync
    resets = ("no_reset_no_sync", "soft_reset")
    if resetmethod == "nodemcu":
        # dtr
        resets = ("default_reset", "hard_reset")
    elif resetmethod == "ck":
        # no dtr
        resets = ("no_reset", "soft_reset")

    return ["--before", resets[0], "--after", resets[1]]


########################################################

env = DefaultEnvironment()
env.SConscript("compat.py", exports="env")
platform = env.PioPlatform()
board = env.BoardConfig()
filesystem = board.get("build.filesystem", "spiffs")

env.Replace(
    __get_flash_size=_get_flash_size,
    __get_board_f_flash=_get_board_f_flash,

    AR="xtensa-lx106-elf-ar",
    AS="xtensa-lx106-elf-as",
    CC="xtensa-lx106-elf-gcc",
    CXX="xtensa-lx106-elf-g++",
    GDB="xtensa-lx106-elf-gdb",
    OBJCOPY="xtensa-lx106-elf-objcopy",
    RANLIB="xtensa-lx106-elf-ranlib",
    SIZETOOL="xtensa-lx106-elf-size",

    ARFLAGS=["rc"],

    #
    # Filesystem
    #

    MKFSTOOL="mk%s" % filesystem,
    ESP8266_FS_IMAGE_NAME=env.get("ESP8266_FS_IMAGE_NAME", env.get(
        "SPIFFSNAME", filesystem)),

    #
    # Misc
    #

    SIZEPROGREGEXP=r"^(?:\.irom0\.text|\.text|\.text1|\.data|\.rodata|)\s+([0-9]+).*",
    SIZEDATAREGEXP=r"^(?:\.data|\.rodata|\.bss)\s+([0-9]+).*",
    SIZECHECKCMD="$SIZETOOL -A -d $SOURCES",
    SIZEPRINTCMD='$SIZETOOL -B -d $SOURCES',

    ERASEFLAGS=[
        "--chip", "esp8266",
        "--port", '"$UPLOAD_PORT"'
    ],
    ERASETOOL=join(
        platform.get_package_dir("tool-esptoolpy") or "", "esptool.py"),
    ERASECMD='"$PYTHONEXE" "$ERASETOOL" $ERASEFLAGS erase_flash',

    PROGSUFFIX=".elf"
)

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
                '"$MKFSTOOL"',
                "-c", "$SOURCES",
                "-p", "$FS_PAGE",
                "-b", "$FS_BLOCK",
                "-s", "${FS_END - FS_START}",
                "$TARGET"
            ]), "Building file system image from '$SOURCES' directory to $TARGET"),
            emitter=__fetch_fs_size,
            source_factory=env.Dir,
            suffix=".bin"
        )
    )
)


#
# Target: Build executable and linkable firmware or file system image
#

target_elf = None
if "nobuild" in COMMAND_LINE_TARGETS:
    target_elf = join("$BUILD_DIR", "${PROGNAME}.elf")
    if set(["uploadfs", "uploadfsota"]) & set(COMMAND_LINE_TARGETS):
        fetch_fs_size(env)
        target_firm = join("$BUILD_DIR", "${ESP8266_FS_IMAGE_NAME}.bin")
    else:
        target_firm = join("$BUILD_DIR", "${PROGNAME}.bin")
else:
    target_elf = env.BuildProgram()
    if set(["buildfs", "uploadfs", "uploadfsota"]) & set(COMMAND_LINE_TARGETS):
        if filesystem not in ("littlefs", "spiffs"):
            sys.stderr.write("Filesystem %s is not supported!\n" % filesystem)
            env.Exit(1)
        target_firm = env.DataToBin(
            join("$BUILD_DIR", "${ESP8266_FS_IMAGE_NAME}"), "$PROJECTDATA_DIR")
        AlwaysBuild(target_firm)
    else:
        target_firm = env.ElfToBin(
            join("$BUILD_DIR", "${PROGNAME}"), target_elf)

env.AddPlatformTarget("buildfs", target_firm, None, "Build Filesystem Image")
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

target_size = env.AddPlatformTarget(
    "size",
    target_elf,
    env.VerboseAction("$SIZEPRINTCMD", "Calculating size $SOURCE"),
    "Program Size",
    "Calculate program size",
)

#
# Target: Upload firmware or filesystem image
#

upload_protocol = env.subst("$UPLOAD_PROTOCOL")
upload_actions = []

# Compatibility with old OTA configurations
if (upload_protocol != "espota"
        and re.match(r"\"?((([0-9]{1,3}\.){3}[0-9]{1,3})|[^\\/]+\.local)\"?$",
                     env.get("UPLOAD_PORT", ""))):
    upload_protocol = "espota"
    sys.stderr.write(
        "Warning! We have just detected `upload_port` as IP address or host "
        "name of ESP device. `upload_protocol` is switched to `espota`.\n"
        "Please specify `upload_protocol = espota` in `platformio.ini` "
        "project configuration file.\n")

if upload_protocol == "espota":
    if not env.subst("$UPLOAD_PORT"):
        sys.stderr.write(
            "Error: Please specify IP address or host name of ESP device "
            "using `upload_port` for build environment or use "
            "global `--upload-port` option.\n"
            "See https://docs.platformio.org/page/platforms/"
            "espressif8266.html#over-the-air-ota-update\n")
    env.Replace(
        UPLOADER=join(
            platform.get_package_dir("framework-arduinoespressif8266") or "",
            "tools", "espota.py"),
        UPLOADERFLAGS=["--debug", "--progress", "-i", "$UPLOAD_PORT"],
        UPLOADCMD='"$PYTHONEXE" "$UPLOADER" $UPLOADERFLAGS -f $SOURCE'
    )
    if "uploadfs" in COMMAND_LINE_TARGETS:
        env.Append(UPLOADERFLAGS=["-s"])
    upload_actions = [env.VerboseAction("$UPLOADCMD", "Uploading $SOURCE")]

elif upload_protocol == "esptool":
    env.Replace(
        UPLOADER=join(
            platform.get_package_dir("tool-esptoolpy") or "", "esptool.py"),
        UPLOADERFLAGS=[
            "--chip", "esp8266",
            "--port", '"$UPLOAD_PORT"',
            "--baud", "$UPLOAD_SPEED",
            "write_flash"
        ],
        UPLOADCMD='"$PYTHONEXE" "$UPLOADER" $UPLOADERFLAGS 0x0 $SOURCE'
    )
    for image in env.get("FLASH_EXTRA_IMAGES", []):
        env.Append(UPLOADERFLAGS=[image[0], env.subst(image[1])])

    if "uploadfs" in COMMAND_LINE_TARGETS:
        env.Replace(
            UPLOADERFLAGS=[
                "--chip", "esp8266",
                "--port", '"$UPLOAD_PORT"',
                "--baud", "$UPLOAD_SPEED",
                "write_flash",
                "$FS_START"
            ],
            UPLOADCMD='"$PYTHONEXE" "$UPLOADER" $UPLOADERFLAGS $SOURCE',
        )

    env.Prepend(
        UPLOADERFLAGS=get_esptoolpy_reset_flags(env.subst("$UPLOAD_RESETMETHOD"))
    )

    upload_actions = [
        env.VerboseAction(env.AutodetectUploadPort,
                          "Looking for upload port..."),
        env.VerboseAction("$UPLOADCMD", "Uploading $SOURCE")
    ]

# custom upload tool
elif upload_protocol == "custom":
    upload_actions = [env.VerboseAction("$UPLOADCMD", "Uploading $SOURCE")]

else:
    sys.stderr.write("Warning! Unknown upload protocol %s\n" % upload_protocol)

env.AddPlatformTarget("upload", target_firm, upload_actions, "Upload")
env.AddPlatformTarget("uploadfs", target_firm, upload_actions, "Upload Filesystem Image")
env.AddPlatformTarget(
    "uploadfsota", target_firm, upload_actions, "Upload Filesystem Image OTA")

#
# Target: Erase Flash
#

env.AddPlatformTarget(
    "erase",
    None,
    [
        env.VerboseAction(env.AutodetectUploadPort, "Looking for serial port..."),
        env.VerboseAction("$ERASECMD", "Erasing...")
    ],
    "Erase Flash",
)

#
# Information about obsolete method of specifying linker scripts
#

if any("-Wl,-T" in f for f in env.get("LINKFLAGS", [])):
    print("Warning! '-Wl,-T' option for specifying linker scripts is deprecated. "
          "Please use 'board_build.ldscript' option in your 'platformio.ini' file.")

#
# Default targets
#

Default([target_buildprog, target_size])

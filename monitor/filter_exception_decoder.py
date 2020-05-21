# Copyright (c) 2014-present PlatformIO <contact@platformio.org>
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

import os
import re
import subprocess
import sys

from platformio.commands.device import DeviceMonitorFilter
from platformio.compat import path_to_unicode, WINDOWS, PY2
from platformio.project.exception import PlatformioException
from platformio.project.helpers import load_project_ide_data


# By design, __init__ is called inside miniterm and we can't pass context to it.
# pylint: disable=attribute-defined-outside-init


class Esp8266ExceptionDecoder(
    DeviceMonitorFilter
):  # pylint: disable=too-many-instance-attributes
    NAME = "esp8266_exception_decoder"

    # https://github.com/esp8266/esp8266-wiki/wiki/Memory-Map
    ADDR_MIN = 0x40000000
    ADDR_MAX = 0x40300000

    STATE_DEFAULT = 0
    STATE_IN_STACK = 1

    EXCEPTION_MARKER = "Exception ("

    # https://github.com/me-no-dev/EspExceptionDecoder/blob/a78672da204151cc93979a96ed9f89139a73893f/src/EspExceptionDecoder.java#L59
    EXCEPTION_CODES = (
        "Illegal instruction",
        "SYSCALL instruction",
        "InstructionFetchError: Processor internal physical address or data error during "
        "instruction fetch",
        "LoadStoreError: Processor internal physical address or data error during load or store",
        "Level1Interrupt: Level-1 interrupt as indicated by set level-1 bits in "
        "the INTERRUPT register",
        "Alloca: MOVSP instruction, if caller's registers are not in the register file",
        "IntegerDivideByZero: QUOS, QUOU, REMS, or REMU divisor operand is zero",
        "reserved",
        "Privileged: Attempt to execute a privileged operation when CRING ? 0",
        "LoadStoreAlignmentCause: Load or store to an unaligned address",
        "reserved",
        "reserved",
        "InstrPIFDataError: PIF data error during instruction fetch",
        "LoadStorePIFDataError: Synchronous PIF data error during LoadStore access",
        "InstrPIFAddrError: PIF address error during instruction fetch",
        "LoadStorePIFAddrError: Synchronous PIF address error during LoadStore access",
        "InstTLBMiss: Error during Instruction TLB refill",
        "InstTLBMultiHit: Multiple instruction TLB entries matched",
        "InstFetchPrivilege: An instruction fetch referenced a virtual address at a ring level "
        "less than CRING",
        "reserved",
        "InstFetchProhibited: An instruction fetch referenced a page mapped with an attribute "
        "that does not permit instruction fetch",
        "reserved",
        "reserved",
        "reserved",
        "LoadStoreTLBMiss: Error during TLB refill for a load or store",
        "LoadStoreTLBMultiHit: Multiple TLB entries matched for a load or store",
        "LoadStorePrivilege: A load or store referenced a virtual address at a ring level "
        "less than CRING",
        "reserved",
        "LoadProhibited: A load referenced a page mapped with an attribute that does not "
        "permit loads",
        "StoreProhibited: A store referenced a page mapped with an attribute that does not "
        "permit stores",
    )

    def __call__(self):
        self.buffer = ""
        self.previous_line = ""
        self.state = self.STATE_DEFAULT
        self.no_match_counter = 0
        self.stack_lines = []

        self.exception_re = re.compile(
            r"^([0-9]{1,2})\):\n([a-z0-9]+=0x[0-9a-f]{8} ?)+$"
        )
        self.stack_re = re.compile(r"^[0-9a-f]{8}:\s+([0-9a-f]{8} ?)+ *$")

        self.firmware_path = None
        self.addr2line_path = None
        self.enabled = self.setup_paths()

        if self.config.get("env:" + self.environment, "build_type") != "debug":
            print(
                """
Please build project in debug configuration to get more details about an exception.
See https://docs.platformio.org/page/projectconf/build_configurations.html

"""
            )

        return self

    def setup_paths(self):
        self.project_dir = path_to_unicode(os.path.abspath(self.project_dir))
        try:
            data = load_project_ide_data(self.project_dir, self.environment)
            self.firmware_path = data["prog_path"]
            if not os.path.isfile(self.firmware_path):
                sys.stderr.write(
                    "%s: firmware at %s does not exist, rebuild the project?\n"
                    % (self.__class__.__name__, self.firmware_path)
                )
                return False

            cc_path = data.get("cc_path", "")
            if "-gcc" in cc_path:
                path = cc_path.replace("-gcc", "-addr2line")
                if os.path.isfile(path):
                    self.addr2line_path = path
                    return True
        except PlatformioException as e:
            sys.stderr.write(
                "%s: disabling, exception while looking for addr2line: %s\n"
                % (self.__class__.__name__, e)
            )
            return False
        sys.stderr.write(
            "%s: disabling, failed to find addr2line.\n" % self.__class__.__name__
        )
        return False

    def rx(self, text):
        if not self.enabled:
            return text

        last = 0
        while True:
            idx = text.find("\n", last)
            if idx == -1:
                if len(self.buffer) < 4096:
                    self.buffer += text[last:]
                break

            line = text[last:idx]
            if self.buffer:
                line = self.buffer + line
                self.buffer = ""
            last = idx + 1

            if line and line[-1] == "\r":
                line = line[:-1]

            extra = self.process_line(line)
            self.previous_line = line
            if extra is not None:
                text = text[: idx + 1] + extra + text[idx + 1 :]
                last += len(extra)
        return text

    def advance_state(self):
        self.state += 1
        self.no_match_counter = 0

    def is_addr_ok(self, hex_addr):
        try:
            addr = int(hex_addr, 16)
            return addr >= self.ADDR_MIN and addr < self.ADDR_MAX
        except ValueError:
            return False

    def process_line(self, line):  # pylint: disable=too-many-return-statements
        if self.state == self.STATE_DEFAULT:
            extra = None
            if self.previous_line.startswith(self.EXCEPTION_MARKER):
                two_lines = (
                    self.previous_line[len(self.EXCEPTION_MARKER) :] + "\n" + line
                )
                match = self.exception_re.match(two_lines)
                if match is not None:
                    extra = self.process_exception_match(match)

            if line == ">>>stack>>>":
                self.advance_state()
            return extra
        elif self.state == self.STATE_IN_STACK:
            if line == "<<<stack<<<":
                self.state = self.STATE_DEFAULT
                return self.take_stack_lines()

            match = self.stack_re.match(line)
            if match is not None:
                self.process_stack_match(line)
                return None

        self.no_match_counter += 1
        if self.no_match_counter > 4:
            self.state = self.STATE_DEFAULT
            results = [self.take_stack_lines(), self.process_line(line)]
            results = [r for r in results if r is not None]
            if results:
                return "\n".join(results)
        return None

    def process_exception_match(self, match):
        extra = "\n"
        try:
            code = int(match.group(1))
            if code >= 0 and code < len(self.EXCEPTION_CODES):
                extra += "%s\n" % self.EXCEPTION_CODES[code]
        except ValueError:
            pass

        header = match.group(0)
        registers = header[header.index("\n") + 1 :].split()
        pairs = [reg.split("=", 2) for reg in registers]

        lines = self.get_lines([p[1] for p in pairs])

        for i, p in enumerate(pairs):
            if lines[i] is not None:
                l = lines[i].replace(
                    "\n", "\n    "
                )  # newlines happen with inlined methods
                extra += "  %s=%s in %s\n" % (p[0], p[1], l)
        return extra

    def process_stack_match(self, line):
        if len(self.stack_lines) > 128:
            return

        addresses = line[line.index(":") + 1 :].split()
        lines = self.get_lines(addresses)
        for i, l in enumerate(lines):
            if l is not None:
                self.stack_lines.append("0x%s in %s" % (addresses[i], l))

    def take_stack_lines(self):
        if self.stack_lines:
            res = "\n%s\n\n" % "\n".join(self.stack_lines)
            self.stack_lines = []
            return res
        return None

    def get_lines(self, addresses):
        result = []

        enc = "mbcs" if WINDOWS else "utf-8"
        args = [self.addr2line_path, u"-fipC", u"-e", self.firmware_path]
        if PY2:
            args = [a.encode(enc) for a in args]

        for addr in addresses:
            if not self.is_addr_ok(addr):
                result.append(None)
                continue

            if PY2:
                addr = addr.encode(enc)

            to_append = None
            try:
                output = (
                    subprocess.check_output(args + [addr])
                    .decode(enc)
                    .strip()
                )
                if output != "?? ??:0":
                    to_append = self.strip_project_dir(output)
            except subprocess.CalledProcessError as e:
                sys.stderr.write(
                    "%s: failed to call %s: %s\n"
                    % (self.__class__.__name__, self.addr2line_path, e)
                )
            result.append(to_append)
        return result

    def strip_project_dir(self, trace):
        while True:
            idx = trace.find(self.project_dir)
            if idx == -1:
                break
            trace = trace[:idx] + trace[idx + len(self.project_dir) + 1 :]
        return trace

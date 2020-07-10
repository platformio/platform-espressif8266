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

from platformio.managers.platform import PlatformBase


class Espressif8266Platform(PlatformBase):

    def configure_default_packages(self, variables, targets):
        framework = variables.get("pioframework", [])
        if "arduino" not in framework:
            self.packages['toolchain-xtensa']['version'] = "~1.40802.0"
        if "buildfs" in targets:
            self.packages['tool-mkspiffs']['optional'] = False
            self.packages['tool-mklittlefs']['optional'] = False
        return PlatformBase.configure_default_packages(
            self, variables, targets)

    def get_boards(self, id_=None):
        result = PlatformBase.get_boards(self, id_)
        if not result:
            return result
        if id_:
            return self._add_upload_protocols(result)
        else:
            for key, value in result.items():
                result[key] = self._add_upload_protocols(result[key])
        return result

    def _add_upload_protocols(self, board):
        if not board.get("upload.protocols", []):
            board.manifest['upload']['protocols'] = ["esptool", "espota"]
        if not board.get("upload.protocol", ""):
            board.manifest['upload']['protocol'] = "esptool"
        return board

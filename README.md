# Espressif 8266: development platform for [PlatformIO](http://platformio.org)

[![Build Status](https://github.com/platformio/platform-espressif8266/workflows/Examples/badge.svg)](https://github.com/platformio/platform-espressif8266/actions)

Espressif Systems is a privately held fabless semiconductor company. They provide wireless communications and Wi-Fi chips which are widely used in mobile devices and the Internet of Things applications.

* [Home](http://platformio.org/platforms/espressif8266) (home page in PlatformIO Platform Registry)
* [Documentation](http://docs.platformio.org/page/platforms/espressif8266.html) (advanced usage, packages, boards, frameworks, etc.)

# Usage

1. [Install PlatformIO](http://platformio.org)
2. Create PlatformIO project and configure a platform option in [platformio.ini](http://docs.platformio.org/page/projectconf.html) file:

## Stable version

```ini
[env:stable]
platform = espressif8266
board = ...
...
```

## Development version

```ini
[env:development]
platform = https://github.com/platformio/platform-espressif8266.git
board = ...
...
```

# Configuration

Please navigate to [documentation](http://docs.platformio.org/page/platforms/espressif8266.html).

# 小米空调伴侣 2

这是一个用于 Home Assistant 的自定义组件，用于接入小米米家空调伴侣 2，原版来自于[EugeneLiu的xiaomi_airconditioningcompanionMCN02项目](https://github.com/EugeneLiu/xiaomi_airconditioningcompanionMCN02)，我这里重新调整修改，并实现兼容Home Assistant 2026.10.4：

| 型号 ID               | 型号编号   | 产品名称                     | 外形   |
|-----------------------|-----------|------------------------------|--------|
| `lumi.acpartner.mcn02` | KTBL03LM  | 小米米家空调伴侣 2            | 方形   |

请按照 [获取访问令牌](https://www.home-assistant.io/components/vacuum.xiaomi_miio/#retrieving-the-access-token) 的说明来获取 API 令牌，用于 `configuration.yaml` 文件中。

致谢：感谢[EugeneLiu](https://github.com/EugeneLiu)、 [Rytilahti](https://github.com/rytilahti/python-miio) 所做的全部工作。

## 功能
* 电源（开、关）
* 运行模式（制热、制冷、自动、除湿、送风）
* 风速（低、中、高、自动）
* 摆风模式（开、关）
* 目标温度
* 捕获并重放红外指令
* 属性
  - ac_model
  - ac_power（开、关）
  - load_power（瓦时 Wh）
  - operation_mode
  - fan_speed
  - swing_mode

## 安装

你可以先在 HACS 的设置菜单中，将这个仓库（[https://github.com/EugeneLiu/xiaomi_airconditioningcompanionMCN02](https://github.com/EugeneLiu/xiaomi_airconditioningcompanionMCN02/)）添加到 [HACS](https://hacs.xyz/)，即可安装此自定义组件。之后你会在集成菜单中找到该自定义组件，名称为「Xiaomi Mi and Aqara Air Conditioning Companion Integration」。或者，你也可以手动安装：将 `custom_component` 文件夹复制到你的 Home Assistant 配置文件夹中。

## 配置

```yaml
# configuration.yaml

climate:
  - platform: xiaomi_miio_airconditioningcompanionmcn02
    name: xiaomi Air Conditioning Companion 2
    host: 
    token: 
    target_sensor: sensor.temperature_158d0001f53706
    scan_interval: 60
```

![climate entity](climate.png "climate entity")

## 调试

如果此自定义组件在你的设备上无法开箱即用，请更新你的配置以启用更高的日志级别：

```yaml
# configuration.yaml

logger:
  default: debug
  logs:
    custom_components.xiaomi_miio_airconditioningcompanionmcn02.climate: debug
    miio: debug
```

---

# Xiaomi Air Conditioning Companion 2

This is a custom component for Home Assistant to integrate the Xiaomi Mi Air Conditioning Companion 2. The original version comes from [EugeneLiu's xiaomi_airconditioningcompanionMCN02 project](https://github.com/EugeneLiu/xiaomi_airconditioningcompanionMCN02). I have re-adjusted and modified it to be compatible with Home Assistant 2026.10.4:

| Model ID              | Model number | Product name                      | Shape  |
|-----------------------|--------------|-----------------------------------|--------|
| `lumi.acpartner.mcn02` | KTBL03LM     | Xiaomi Mi Air Conditioner Companion 2 | square |

Please follow the instructions on [Retrieving the Access Token](https://www.home-assistant.io/components/vacuum.xiaomi_miio/#retrieving-the-access-token) to get the API token to use in the `configuration.yaml` file.

Credits: Thanks to [EugeneLiu](https://github.com/EugeneLiu) and [Rytilahti](https://github.com/rytilahti/python-miio) for all the work.

## Features
* Power (on, off)
* Operation Mode (Heat, Cool, Auto, Dehumidify, Ventilate)
* Fan Speed (Low, Medium, High, Auto)
* Swing Mode (On, Off)
* Target Temperature
* Capture and replay infrared commands
* Attributes
  - ac_model
  - ac_power (on, off)
  - load_power (Wh)
  - operation_mode
  - fan_speed
  - swing_mode

## Install

You can install this custom component by adding this repository ([https://github.com/EugeneLiu/xiaomi_airconditioningcompanionMCN02](https://github.com/EugeneLiu/xiaomi_airconditioningcompanionMCN02/)) to [HACS](https://hacs.xyz/) in the settings menu of HACS first. You will find the custom component in the integration menu afterwards, look for 'Xiaomi Mi and Aqara Air Conditioning Companion Integration'. Alternatively, you can install it manually by copying the `custom_component` folder to your Home Assistant configuration folder.

## Setup

```yaml
# configuration.yaml

climate:
  - platform: xiaomi_miio_airconditioningcompanionmcn02
    name: xiaomi Air Conditioning Companion 2
    host: 
    token: 
    target_sensor: sensor.temperature_158d0001f53706
    scan_interval: 60
```

![climate entity](climate.png "climate entity")

## Debugging

If the custom component doesn't work out of the box for your device, please update your configuration to enable a higher log level:

```yaml
# configuration.yaml

logger:
  default: debug
  logs:
    custom_components.xiaomi_miio_airconditioningcompanionmcn02.climate: debug
    miio: debug
```

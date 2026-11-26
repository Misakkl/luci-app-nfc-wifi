# luci-app-nfc-wifi

[English](README.md) | **简体中文**

把路由器的 WiFi 名称和密码自动写入机身 NFC 标签，手机碰一下就能连上 WiFi。

针对 **小米 AX3000T**（RD03 / AN8855，复旦微电子 FM11NT082C NFC 芯片）开发，
其他使用同款芯片的设备只需改 I2C 总线号和地址。

```
LuCI 里改 WiFi 名称/密码  ──►  路由器自动重写 NFC 标签  ──►  手机碰一下连上
```

---

## 目录

- [为什么要做这个](#为什么要做这个)
- [支持的设备](#支持的设备)
- [安装](#安装)
- [使用](#使用)
- [工作原理](#工作原理)
- [协议详解](#协议详解)
- [故障排查](#故障排查)
- [已知限制](#已知限制)
- [二次开发](#二次开发)
- [许可](#许可)

---

## 为什么要做这个

小米 AX3000T 机身顶部有一颗 NFC 标签，出厂时烧录了「碰一下连 WiFi」的配置。

问题在于：**手机写不进去，小米 App 也改不了。**

原因是出厂时用 **RF 侧静态锁位**（EEPROM `0x0A/0x0B` = `FF FF`）把 NDEF 区锁死了，
所以任何通过 NFC 射频侧的写入都会被芯片拒绝——App 显示"可写"是误报。

但 **I2C（接触）侧是另一套权限**，受 `CT Lock Bits`（EEPROM Block `0xF0/0xF1`）控制，
实测**没有被锁定**。也就是说：

| 路径 | 能不能改 |
|---|---|
| 手机（RF 侧） | ❌ 被静态锁位挡住 |
| 路由器 CPU（I2C 侧） | ✅ 可以改 |

这正是原厂的设计意图——只允许设备自身更新标签内容。

本插件就利用这个 I2C 通道，让标签内容跟着 WiFi 配置自动走。

---

## 支持的设备

| 设备 | 状态 | 说明 |
|---|---|---|
| 小米 AX3000T（RD03 / AN8855） | ✅ 已验证 | 默认配置直接可用 |
| 其他 FM11NT082C 设备 | ⚠️ 需调整 | 改 `/etc/config/nfc_wifi` 里的 `bus` / `address` |

**硬件要求**

- NFC 芯片型号 **FM11NT082C**（复旦微电子）
- 芯片挂在 CPU 的 I2C 总线上（AX3000T 是 bus 0，地址 `0x57`）
- 系统里能跑 `i2ctransfer`

> ⚠️ **版本提醒**：AX3000T 有多个版本。RD03V2/V3 是**高通 IPQ5018**，和 MTK 版结构完全不同，
> 不要把本插件当作通用方案。只有社区所称的「V2」（MT7981B + Airoha AN8855 交换芯片）
> 才是本插件适用的机型。

---

## 安装

### 方式一：直接装 ipk（推荐）

```sh
scp luci-app-nfc-wifi_1.0.0-1_all.ipk root@192.168.1.1:/tmp/
ssh root@192.168.1.1 'opkg install /tmp/luci-app-nfc-wifi_1.0.0-1_all.ipk'
```

如果提示缺少依赖：

```sh
opkg update
opkg install luci-base i2c-tools
```

### 方式二：从源码装

```sh
git clone https://github.com/<your-name>/luci-app-nfc-wifi.git
cd luci-app-nfc-wifi

python3 build-ipk.py          # 生成 dist/*.ipk，不需要 SDK
scp dist/luci-app-nfc-wifi_1.0.0-1_all.ipk root@192.168.1.1:/tmp/
ssh root@192.168.1.1 'opkg install /tmp/luci-app-nfc-wifi_1.0.0-1_all.ipk'
```

### 方式三：OpenWrt SDK 编译

```sh
cp -r luci-app-nfc-wifi ~/openwrt-sdk/package/
cd ~/openwrt-sdk
make package/luci-app-nfc-wifi/compile V=s
```

产物在 `bin/packages/*/base/`。

### 安装后

- 菜单出现在 **系统 → NFC 标签同步**
- 开机自动同步已自动启用
- 首次安装会立刻写一次标签

---

## 使用

### LuCI 界面

**系统 → NFC 标签同步**

| 选项 | 说明 |
|---|---|
| 启用自动同步 | 总开关。关闭后自动同步失效，但「立即同步」仍可用 |
| I2C 总线 | 留空用默认值 `0` |
| 标签地址 | 留空用默认值 `0x57` |
| 立即同步 | 强制写一次（忽略总开关） |

改完 WiFi 名称或密码后点「保存并应用」，标签会自动更新。

### 命令行

```sh
/usr/sbin/nfc-wifi-sync            # 按配置执行（受总开关约束）
/usr/sbin/nfc-wifi-sync --force    # 强制同步，忽略总开关
/etc/init.d/nfc-wifi-sync reload   # 通过 init 脚本

logread | grep nfc-wifi-sync       # 查看结果
```

### 验证标签内容

```sh
# 读 NDEF 头（期望 03 55 d2 17）
i2ctransfer -y 0 w2@0x57 0x00 0x10 r16@0x57

# 读 SSID 区
i2ctransfer -y 0 w2@0x57 0x00 0x39 r16@0x57
```

手机贴一下，Android 会弹出「加入网络 xxx」。

### 自动同步触发时机

1. **开机** —— `/etc/init.d/nfc-wifi-sync`（`S95`）
2. **WiFi 接口 up** —— `/etc/hotplug.d/iface/99-nfc-wifi`
   （用 `/tmp/nfc-wifi.fp` 指纹去重，配置没变就不重写，省 EEPROM 寿命）
3. **手动** —— LuCI 按钮或命令行

---

## 工作原理

```
┌──────────────┐
│  UCI 配置     │  wireless.<sec>.ssid / .key
└──────┬───────┘
       │  读取
       ▼
┌──────────────┐
│ NDEF 构造     │  WSC Credential → 字节序列
└──────┬───────┘
       │  16 字节/页
       ▼
┌──────────────┐
│ I2C 写入      │  i2ctransfer → FM11NT082C EEPROM
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ NFC 标签      │  手机碰一下读走
└──────────────┘
```

---

## 协议详解

这部分是踩坑踩出来的，写下来省得后来人重走一遍。

### ⚠️ 核心陷阱：EEPROM 必须用「两字节大端地址」

```
写一页: i2ctransfer -y 0 w18@0x57 0x00 <addrH> <addrL> <16 个数据字节>
读一页: i2ctransfer -y 0 w2@0x57  0x00 <addrH> <addrL> r16@0x57
```

**为什么容易搞错**：`i2ctransfer -y 0 w1@0x57 0x10` 看起来像"读地址 0x10"，
实际上进的是**内部寄存器空间**，窗口只有 128 字节，行为和 EEPROM 完全不同。

误用一字节地址的症状（开发时全部踩过）：

| 症状 | 原因 |
|---|---|
| 读 `0x00` 有数据，读 `0x10`/`0x20` 全 0 | 走的是寄存器区，不是 EEPROM |
| 写入收到 ACK 但内容不变 | 同上 |
| 写入落点乱飘，每次不一样 | 指针寄存器 `0x03` 被误当 EEPROM 地址 |
| **误判成「OTP 锁死、物理无解」** | 最大的坑，差点放弃 |

### 内部寄存器（仅在用一字节地址时可见）

| 寄存器 | 作用 |
|---|---|
| `0x00` | 数据端口 |
| `0x03` | 读指针（写完自动清零） |
| `0x08` 及以上 | 无效（NAK） |

### EEPROM 布局

```
0x0000  UID（7 字节）+ BCC
0x0008  锁位（AX3000T 实测 6F B0 FF FF）
0x000C  CC = E1 10 6D 00      ← 容量 880 字节，可读写
0x0010  NDEF 起点
```

### 页写规则

- EEPROM 按 **16 字节/页** 组织
- 单次写入**不能跨页**，跨页会被 NAK 或绕回页首
- 写入时把地址设成页对齐最稳

### NDEF / WSC 格式

用的是标准 **WSC（WiFi Simple Configuration）**，iOS 和 Android 都认这套：

```
03 <TLV长度>                       NDEF TLV
  d2 17 <载荷长度>                 MIME 记录（类型 23 字节）
  "application/vnd.wfa.wsc"
  10 0e <Cred长度>                 Credential
    10 26 00 01 01                  Network Index
    10 45 <SSID长度> <SSID>         SSID
    10 03 00 02 00 20               WPA2-PSK
    10 0f 00 02 00 08               AES
    10 27 <密码长度> <密码>         Network Key
    10 20 00 06 ff ff ff ff ff fe   MAC（通配）
```

**长度计算**（设 SSID 长 `s`、密码长 `k`）：

```
Cred  = 35 + s + k
载荷  = 4 + Cred
TLV   = 3 + 23 + 载荷
```

### 关于 WPA2/WPA3

WSC 规范里**没有 WPA3 字段**（WPA3 的 SAE 不属于这套老规范）。所以即使路由器是
WPA2/WPA3 混合模式，标签里也必须写 **WPA2-PSK / AES**。

这是**正确且兼容性最好**的选择：混合模式的 AP 同时接受 WPA2 和 WPA3 客户端。
只有当路由器被设成 **WPA3 单模式**时，标签才会连不上。

---

## 故障排查

### 现象：同步失败，日志显示 write failed

```sh
logread | grep nfc-wifi-sync
```

| 日志 | 原因 | 解决 |
|---|---|---|
| `i2ctransfer missing` | 没装 i2c-tools | `opkg install i2c-tools` |
| `no enabled AP with ssid found` | 没找到启用的 AP | 检查 `/etc/config/wireless` |
| `write failed at addr 0x0010` | I2C 通信失败 | 见下方排查 |
| `verify mismatch` | 写入后校验不一致 | 见下方排查 |
| `record too large` | SSID+密码太长 | 缩短到 42 字符以内 |

### I2C 通信失败排查

```sh
# 1. 芯片是否在总线上
i2cdetect -y 0
# 期望在 0x57 看到一个地址

# 2. 能不能读 UID
i2ctransfer -y 0 w2@0x57 0x00 0x00 r8@0x57
# 期望返回 8 个非全零字节

# 3. 内核是否加载了 I2C 控制器
ls /sys/bus/i2c/devices/
```

如果 `i2cdetect` 看不到 `0x57`：

- 确认机型和芯片型号确实是 FM11NT082C
- 确认 NFC 芯片没被硬件禁用
- 部分固件默认不加载 I2C 控制器驱动，需要装 `kmod-i2c-*`

### 现象：手机贴上去没反应

| 平台 | 说明 |
|---|---|
| **Android** | 应弹出「加入网络」。若没有，检查 NDEF 是否完整 |
| **iOS** | ⚠️ **系统级 NFC 只认 URL 记录**，WiFi 记录不会弹出加入提示 |

**iOS 上这是硬限制**，不是本插件的问题。替代方案：

1. 用「NFC Tools」等 App 读取（手动连）
2. **用 WiFi 二维码**（iPhone 相机原生支持扫码加入）
3. 苹果设备间用「共享密码」

建议在机器上同时贴一个二维码，安卓碰 NFC、苹果扫码。

### 现象：写入成功但内容是旧的

- LuCI 有缓存，**强制刷新**（`Ctrl+Shift+R`）
- 或者确认改的是**已启用**的 AP 段（脚本只读 `mode='ap'` 且 `disabled!='1'` 的段）

---

## 已知限制

| 限制 | 说明 |
|---|---|
| **仅 ASCII** | 中文 SSID 会算错长度。需要的话可扩展成 UTF-8 按字节拆分 |
| **SSID+密码 ≤ 42 字符** | TLV 长度是单字节，且受 CC 声明的容量限制 |
| **只同步第一个已启用的 AP** | 多 SSID 场景只取第一个 |
| **iOS 不弹加入提示** | 见上方说明，是系统限制 |
| **写擦寿命** | EEPROM 约 100 万次，hotplug 已做指纹去重，正常使用无影响 |

---

## 二次开发

### 目录结构

```
luci-app-nfc-wifi/
├── build-ipk.py                          # 独立打包脚本（无需 SDK）
├── Makefile                              # OpenWrt SDK 构建用
├── README.md                             # 英文
├── README.zh-CN.md                       # 中文
├── LICENSE
├── root/                                 # 安装到路由器根目录的内容
│   ├── etc/
│   │   ├── config/nfc_wifi               # UCI 配置（conffile）
│   │   ├── init.d/nfc-wifi-sync          # 开机同步
│   │   ├── hotplug.d/iface/99-nfc-wifi   # WiFi up 触发
│   │   └── uci-defaults/90-nfc-wifi      # 首装启用服务
│   └── usr/
│       ├── sbin/nfc-wifi-sync            # 主脚本
│       └── share/
│           ├── luci/menu.d/              # 菜单
│           └── rpcd/acl.d/               # 权限
└── htdocs/                               # Web 资源
    └── luci-static/resources/view/nfc-wifi/nfc-wifi.js
```

### 适配新硬件

改 `/etc/config/nfc_wifi`：

```uci
config nfc_wifi 'main'
	option enabled '1'
	option bus '1'        # 换成你的 I2C 总线号
	option address '0x57' # 换成你的芯片地址
```

如果 NDEF 起点或 CC 容量不同，需要改 `root/usr/sbin/nfc-wifi-sync` 里的
`BASE` 和 `END` 两个常量。

### 打包

```sh
python3 build-ipk.py            # 默认 1.0.0-1
python3 build-ipk.py 1.1.0      # 指定版本
```

产物在 `dist/`。构建可重复（固定 mtime 与 gzip OS 字节）。

> 注意：`build-ipk.py` 生成的是 `gzip(tar(...))` 格式，
> 这是实测目标 opkg 能解析的格式。传统 `ar` 格式在部分新版 opkg 上会报
> `Malformed package file`。

---

## 许可

[MIT](LICENSE)

---

## 致谢

- 复旦微电子 FM11NT082C 数据手册（`XCY2020_1656501739000.pdf`）
- OpenWrt / LuCI 项目
- 恩山无线论坛社区的 AX3000T 刷机资料

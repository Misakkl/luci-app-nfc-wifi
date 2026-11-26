#
# 用于 OpenWrt SDK 构建
#
# 把本目录放到 SDK 的 package/ 下：
#   cp -r luci-app-nfc-wifi ~/openwrt-sdk/package/
#   cd ~/openwrt-sdk && make package/luci-app-nfc-wifi/compile V=s
#
# 若不想用 SDK，直接跑 python3 build-ipk.py 也能出 ipk。
#

include $(TOPDIR)/rules.mk

PKG_NAME:=luci-app-nfc-wifi
PKG_VERSION:=1.0.0
PKG_RELEASE:=1
PKG_LICENSE:=MIT
PKG_MAINTAINER:=Misakkl

LUCI_TITLE:=LuCI app for syncing WiFi credentials to NFC tag
LUCI_DEPENDS:=+luci-base +i2c-tools
LUCI_PKGARCH:=all
LUCI_DESCRIPTION:=把当前 WiFi 的 SSID 与密码写入 FM11NT082C NFC 标签，手机碰一下即可连接。

include $(TOPDIR)/feeds/luci/luci.mk

# 若刷新后 luci.mk 的行为不符预期，可改用下面的通用打包方式：
# include $(INCLUDE_DIR)/package.mk
# define Package/$(PKG_NAME)
#   SECTION:=luci
#   CATEGORY:=LuCI
#   SUBMENU:=3. Applications
#   TITLE:=$(LUCI_TITLE)
#   DEPENDS:=$(LUCI_DEPENDS)
#   PKGARCH:=all
# endef
# define Package/$(PKG_NAME)/install
#   $(INSTALL_DIR) $(1)/etc/config $(1)/etc/init.d $(1)/etc/hotplug.d/iface
#   $(INSTALL_DIR) $(1)/etc/uci-defaults $(1)/usr/sbin
#   $(INSTALL_DIR) $(1)/usr/share/luci/menu.d $(1)/usr/share/rpcd/acl.d
#   $(INSTALL_DIR) $(1)/www/luci-static/resources/view/nfc-wifi
#   $(INSTALL_CONF) ./root/etc/config/nfc_wifi $(1)/etc/config/nfc_wifi
#   $(INSTALL_BIN) ./root/etc/init.d/nfc-wifi-sync $(1)/etc/init.d/nfc-wifi-sync
#   $(INSTALL_BIN) ./root/etc/hotplug.d/iface/99-nfc-wifi $(1)/etc/hotplug.d/iface/99-nfc-wifi
#   $(INSTALL_BIN) ./root/etc/uci-defaults/90-nfc-wifi $(1)/etc/uci-defaults/90-nfc-wifi
#   $(INSTALL_BIN) ./root/usr/sbin/nfc-wifi-sync $(1)/usr/sbin/nfc-wifi-sync
#   $(INSTALL_DATA) ./root/usr/share/luci/menu.d/luci-app-nfc-wifi.json $(1)/usr/share/luci/menu.d/
#   $(INSTALL_DATA) ./root/usr/share/rpcd/acl.d/luci-app-nfc-wifi.json $(1)/usr/share/rpcd/acl.d/
#   $(INSTALL_DATA) ./htdocs/luci-static/resources/view/nfc-wifi/nfc-wifi.js \
#       $(1)/www/luci-static/resources/view/nfc-wifi/nfc-wifi.js
# endef
# $(eval $(call BuildPackage,$(PKG_NAME)))

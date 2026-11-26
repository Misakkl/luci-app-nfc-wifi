#!/usr/bin/env python3
"""把本目录打包成 OpenWrt .ipk（无需 OpenWrt SDK）。

包结构（与本机 opkg 实际解析的格式一致）：

    gzip( tar( debian-binary, data.tar.gz, control.tar.gz ) )

其中 debian-binary 内容是 "2.0\\n"。

用法:
    python3 build-ipk.py [版本号]

产物: dist/luci-app-nfc-wifi_<版本>_all.ipk
"""

import gzip
import io
import os
import sys
import tarfile

ROOT = os.path.dirname(os.path.abspath(__file__))
PKG = "luci-app-nfc-wifi"
DEFAULT_VERSION = "1.0.0"
MAINTAINER = "Misakkl"
DESCRIPTION = (
    "把当前 WiFi(AP) 的 SSID 与密码写入 FM11NT082C NFC 标签，"
    "手机碰一下即可自动连接。含 LuCI 页面与开机/hotplug 自动同步。"
)
EXTRA_DESC = [
    "支持硬件: 小米 AX3000T (RD03/AN8855), 芯片 FM11NT082C (I2C 0x57)。",
    "其他机型可改 /etc/config/nfc_wifi 里的 bus / address。",
]

# (源目录, 目标前缀)
TREES = [
    ("root", ""),
    ("htdocs", "www"),
]

EXEC_SUFFIX = ("usr/sbin/", "etc/init.d/", "etc/hotplug.d/", "etc/uci-defaults/")

MTIME = 1700000000


def iter_tree():
    """遍历要打包的文件，返回 (目标路径, 绝对路径, 权限)。"""
    out = []
    for src, prefix in TREES:
        base = os.path.join(ROOT, src)
        if not os.path.isdir(base):
            continue
        for dirpath, _dirnames, filenames in os.walk(base):
            for name in sorted(filenames):
                ap = os.path.join(dirpath, name)
                rel = os.path.relpath(ap, base).replace(os.sep, "/")
                dst = "/".join(p for p in (prefix, rel) if p)
                mode = 0o755 if rel.startswith(EXEC_SUFFIX) else 0o644
                out.append((dst, ap, mode))
    out.sort(key=lambda x: x[0])
    return out


def _add_file(tar, name, data, mode):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = mode
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    info.mtime = MTIME
    tar.addfile(info, io.BytesIO(data))


def _add_dir(tar, name):
    info = tarfile.TarInfo(name)
    info.type = tarfile.DIRTYPE
    info.mode = 0o755
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    info.mtime = MTIME
    tar.addfile(info)


def _gz(tar_bytes):
    # mtime=0 + 固定 OS 字节，保证可重复构建
    return gzip.compress(tar_bytes, 9, mtime=0)


def build_data_tar(files):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.GNU_FORMAT) as tar:
        dirs = set()
        for dst, _ap, _m in files:
            parts = dst.split("/")[:-1]
            for i in range(1, len(parts) + 1):
                dirs.add("/".join(parts[:i]))
        for d in sorted(dirs):
            _add_dir(tar, "./" + d)
        for dst, ap, mode in files:
            with open(ap, "rb") as f:
                _add_file(tar, "./" + dst, f.read(), mode)
    return _gz(buf.getvalue())


def build_control_tar(version, installed_kb):
    control = [
        "Package: %s" % PKG,
        "Version: %s" % version,
        "Depends: luci-base, i2c-tools",
        "Source: %s" % PKG,
        "SourceName: %s" % PKG,
        "License: MIT",
        "Section: luci",
        "Priority: optional",
        "Architecture: all",
        "Installed-Size: %d" % installed_kb,
        "Maintainer: %s" % MAINTAINER,
        "Description: %s" % DESCRIPTION,
    ]
    for line in EXTRA_DESC:
        control.append(" " + line)
    control_txt = ("\n".join(control) + "\n").encode()

    conffiles = "/etc/config/nfc_wifi\n".encode()

    postinst = b"""#!/bin/sh
[ -n "${IPKG_INSTROOT}" ] && exit 0
[ -x /etc/init.d/nfc-wifi-sync ] && /etc/init.d/nfc-wifi-sync enable
/etc/init.d/rpcd restart >/dev/null 2>&1
exit 0
"""

    prerm = b"""#!/bin/sh
[ -n "${IPKG_INSTROOT}" ] && exit 0
[ -x /etc/init.d/nfc-wifi-sync ] && /etc/init.d/nfc-wifi-sync disable
exit 0
"""

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.GNU_FORMAT) as tar:
        _add_dir(tar, "./")
        _add_file(tar, "./control", control_txt, 0o644)
        _add_file(tar, "./conffiles", conffiles, 0o644)
        _add_file(tar, "./postinst", postinst, 0o755)
        _add_file(tar, "./prerm", prerm, 0o755)
    return _gz(buf.getvalue())


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_VERSION
    full_version = version if "-" in version else version + "-1"

    files = iter_tree()
    if not files:
        sys.exit("没有找到要打包的文件")

    installed_kb = sum(os.path.getsize(ap) for _d, ap, _m in files) // 1024 + 1

    data_tar = build_data_tar(files)
    control_tar = build_control_tar(full_version, installed_kb)

    # 外层: gzip(tar(debian-binary, data.tar.gz, control.tar.gz))
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.GNU_FORMAT) as tar:
        _add_file(tar, "./debian-binary", b"2.0\n", 0o644)
        _add_file(tar, "./data.tar.gz", data_tar, 0o644)
        _add_file(tar, "./control.tar.gz", control_tar, 0o644)
    ipk = _gz(buf.getvalue())

    dist = os.path.join(ROOT, "dist")
    os.makedirs(dist, exist_ok=True)
    out = os.path.join(dist, "%s_%s_all.ipk" % (PKG, full_version))
    with open(out, "wb") as f:
        f.write(ipk)

    print("打包完成: %s" % out)
    print("大小: %d 字节" % len(ipk))
    print("版本: %s  架构: all  安装大小: %d KB" % (full_version, installed_kb))
    print("文件数: %d" % len(files))
    for dst, _ap, mode in files:
        print("  %s  %s" % (oct(mode)[2:], dst))


if __name__ == "__main__":
    main()

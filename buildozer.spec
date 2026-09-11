[app]

title = 句子俱乐部

package.name = englishclub

package.domain = org.sentenceclub

source.dir = .

source.include_exts = py,png,jpg,jpeg,kv,atlas,ttf,otf,json,md,txt

# 打包内置课程需要的业务模块（core 目录）与界面（ui 目录）已随 source.dir 全部包含；
# 下面显式排除开发/测试相关文件，减小 APK 体积。
source.exclude_exts = spec,sh,yml,yaml
source.exclude_dirs = tools,.github,__pycache__,.git,build,.buildozer,bin,p4a-recipes

version = 1.0.0

# 依赖：Python3 + Kivy + requests（AI 与在线发音）；sqlite3 由 Python 内置提供
# 必须锁定 Python 3.11：
#   1) 不锁会拉到最新的 Python 3.14，其 Python/remote_debugging.c 用了 preadv/pwritev，
#      在 minapi<24 时头文件里未声明，编译直接失败（p4a 自带的 3.14 补丁没覆盖这里）；
#   2) Kivy 2.3.0 官方只支持到 Python 3.12，用 3.14 大概率在编译 Kivy 时因 C-API 变更再崩。
#   4) kivy 用 2.3.1（p4a 官方验证组合）：2.3.0 的 cgl_gl.pyx 中 glShaderSource
#      函数指针签名是 const GLchar**，与 SDL2 头文件的 const GLchar* const*
#      不兼容，NDK r28c 的 clang 18 把「函数指针类型不兼容」默认升级为错误；
#      2.3.1 已改为精确匹配签名。
requirements = python3==3.11.9,hostpython3==3.11.9,kivy==2.3.1,requests,chardet==4.0.0
# chardet 必须锁 4.0.0（纯 Python）：requests 会 import chardet，而 PyPI 没有
# Android 平台的 chardet 7.x wheel，pip 会错装 x86_64 Linux 版（内含 mypyc C 扩展），
# arm64 设备上 import 即 SIGILL 闪退（chardet 5.0+ 才引入 mypyc 编译）。

# 屏幕方向：跟随系统重力感应四向自由旋转（手机竖屏、平板横屏都适配）
# 合法值仅：landscape / portrait / landscape-reverse / portrait-reverse / all
# 注意：不可写 fullSensor 或 fullsensor，buildozer 会校验失败
orientation = all

# 状态栏可见（不隐藏，避免打字时看不到时间与通知）
fullscreen = 0

android.permissions = INTERNET

android.api = 34
# minapi 必须 >= 24：Android 的 preadv/pwritev 自 API 24 才提供（= Android 7.0，2016 年），
# 低于 24 时头文件不声明这两个函数，编译 Python 会报 implicit function declaration。
# 24 仍覆盖 99% 以上的在役设备。
android.minapi = 24

# 显式锁定 NDK r28c（p4a 推荐上限，日志中 buildozer 亦提示 28c）。
# 关键原因：Android 15+/16 的 16KB 内存页设备要求 .so 按 16KB 对齐，
# NDK r27 起默认开启（-Wl,-z,max-page-size=16384）；r25b 产出 4KB 对齐，
# 在 16KB 设备上 dlopen libpython 即失败 → 启动闪退。
# （历史教训：曾因误判「clang 严格化导致 Kivy 编译失败」降级到 r25b，
#  真实根因是 grp 函数缺失，与 NDK 版本无关。）
android.ndk = 28c

# 默认只编 arm64-v8a（覆盖 2016 年后的绝大多数手机，构建快一倍）。
# 需要兼容老设备时，在 Actions 手动运行时选择 "arm64-v8a, armeabi-v7a"。
android.archs = arm64-v8a

android.allow_backup = True
android.accept_sdk_license = True

# 软键盘：不强制弹出，由用户点击输入框唤起（避免遮挡打字板）
android.soft_input_mode = resize

# 用本地 recipe 覆盖官方 python3 recipe，禁用 Android 不提供的 grp 函数
# （详见 p4a-recipes/python3/__init__.py 中的说明）。这是构建必需项，勿删。
p4a.local_recipes = p4a-recipes

# 图标与启动图（可自行放入 assets/ 后取消注释）
# icon.filename = assets/icon.png
# presplash.filename = assets/presplash.png
# presplash.color = #0e1116

[buildozer]

log_level = 2

warn_on_root = 1

build_dir = ./.buildozer

bin_dir = ./bin

# 启动入口：main.py 位于项目根目录，buildozer 默认即使用它（无需额外配置）

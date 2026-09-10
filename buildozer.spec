[app]

title = 句子俱乐部

package.name = englishclub

package.domain = org.sentenceclub

source.dir = .

source.include_exts = py,png,jpg,jpeg,kv,atlas,ttf,otf,json,md,txt

# 打包内置课程需要的业务模块（core 目录）与界面（ui 目录）已随 source.dir 全部包含；
# 下面显式排除开发/测试相关文件，减小 APK 体积。
source.exclude_exts = spec,sh,yml,yaml
source.exclude_dirs = tools,.github,__pycache__,.git,build,.buildozer,bin

version = 1.0.0

# 依赖：Python3 + Kivy + requests（AI 与在线发音）；sqlite3 由 Python 内置提供
requirements = python3,kivy==2.3.0,requests

# 屏幕方向：跟随系统重力感应四向自由旋转（手机竖屏、平板横屏都适配）
# 合法值仅：landscape / portrait / landscape-reverse / portrait-reverse / all
# 注意：不可写 fullSensor 或 fullsensor，buildozer 会校验失败
orientation = all

# 状态栏可见（不隐藏，避免打字时看不到时间与通知）
fullscreen = 0

android.permissions = INTERNET

android.api = 34
android.minapi = 23
android.archs = arm64-v8a, armeabi-v7a

android.allow_backup = True
android.accept_sdk_license = True

# 软键盘：不强制弹出，由用户点击输入框唤起（避免遮挡打字板）
android.soft_input_mode = resize

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

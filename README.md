# 句子俱乐部 · 安卓版

桌面版的安卓移植：**业务逻辑 100% 复用，界面用 Kivy 重写**，支持手机与平板。
玩法不变——不是背单词，而是把单词放回句子里，用键盘打出来。

```
python main.py            # 桌面按手机尺寸(420x880)预览
python main.py --tablet   # 桌面全屏/平板比例预览
python smoke_test.py      # 无头冒烟测试
```

---

## 一、技术选择说明

| 候选方案 | 结论 |
| --- | --- |
| **Kivy + Buildozer** | ✅ 采用。纯 Python，可复用现有 `core/`；Buildozer 是最成熟的 Python→APK 工具链 |
| PySide6 for Android | 需 Qt 6.5+ 与 NDK，Python 3.9 下轮子不全 |
| Flutter / RN 重写 | 体验最好，但要丢弃全部 Python 业务逻辑，工程量数倍 |
| Web App + Capacitor | 需 Node/Gradle 工具链，同样要重写界面 |

界面层用 Kivy 重写，但 **数据库、SM-2 复习算法、打字引擎、AI 客户端、课程与拼读内容
全部沿用桌面版代码**（`core/` 目录），因此两边功能保持一致。

## 二、针对手机的适配

| 项 | 做法 |
| --- | --- |
| **输入** | 不做自绘键盘，而是**唤起系统软键盘**：一个不可见 `TextInput` 负责接收文本，打字板负责逐字符着色。这样支持滑行输入、语音输入与第三方输入法 |
| **布局** | 底部 5 个导航标签（练习 / 拼读 / 课程 / 复习 / 我的），触摸目标 ≥ 44dp；平板横竖屏自适应（`fullsensor`） |
| **数据目录** | 使用 `App.user_data_dir`（应用私有目录），卸载随应用清除 |
| **生命周期** | `on_pause` 返回 True，切后台不丢进度 |
| **音量键 / 返回键** | 系统默认；AI 面板改为浮层，返回键关闭 |
| **中文字体** | Kivy 默认 Roboto **不含中文**，APK 内置 1.8MB 简体字体子集 |
| **音标显示** | Noto CJK 不含 IPA 字符（/ʃ/ /θ/ /ɪ/ 会变方块），故安卓版改用**教材常用的 ASCII 简易音标**（/sh/ /th/ /ae/），更适合入门且 100% 可显示 |

## 三、目录结构

```
main.py                 入口：底部导航 + 屏幕管理 + 安卓生命周期
core/                   业务逻辑（与桌面版一致，去掉 Qt 依赖）
  config.py  db.py  srs.py  engine.py  ai_client.py
  courses_builtin.py  phonics_data.py     内置课程 + 自然拼读
  media.py                                 朗读与音效（Kivy SoundLoader）
  context.py  worker.py                    全局上下文 / 后台线程
ui/
  theme.py              颜色、中文字体解析、通用控件
  widgets.py            自绘打字板、连击徽章、统计卡片、柱状图
  practice_screen.py    练习页（软键盘输入、AI 浮层）
  phonics_screen.py     自然拼读音素速查
  library_screens.py    课程库 / 复习 / 统计 / 导入
  settings_screen.py    设置 与「我的」
assets/fonts/           打包用的字体子集
tools/build_font.py     生成字体子集
buildozer.spec          APK 打包配置
build.sh                一键打包脚本
```

## 四、功能清单

与桌面版一致：逐字符校验、连击 Combo、Perfect 评分、句子/单词/默写/**拼读** 四种模式、
SM-2 间隔复习、9 套分级课程、9 组自然拼读、AI 讲解翻译、自定义导入、学习统计、在线发音。

## 五、打包 APK

### 方式 A：本机打包（需 JDK 17 + 约 6GB 磁盘）

```bash
pip install -r requirements.txt
chmod +x build.sh && ./build.sh
```

首次运行会自动下载 Android SDK / NDK，约 20~40 分钟；产物在 `bin/`。
当前机器条件（磁盘仅剩约 2GB、JDK 8）不满足，故未在本机实际打包。

### 方式 B：GitHub Actions 云端打包（推荐，绕开本机限制）

仓库推送后，在 Actions 页手动运行 **Build Android APK**（或推送 `v*` 标签自动触发），
约 20~30 分钟后在 Artifacts 下载 APK。

### 方式 C：手动

```bash
pip install buildozer cython
python tools/build_font.py      # 可选，生成中文字体子集
buildozer -v android debug      # 调试版
buildozer -v android release    # 发布版（需签名配置）
```

## 六、常见问题

**APK 里中文显示为方块？**
未执行 `tools/build_font.py`。执行后 `assets/fonts/NotoSansSC-Subset.otf` 会被打进 APK；
若仍缺字，说明该字不在 GB2312 一级字库内，可编辑 `tools/build_font.py` 扩大字符集。

**为什么音标是 /sh/ 而不是 /ʃ/？**
安卓字体不含 IPA 扩展字符，显示会是方块。桌面版仍使用标准国际音标。

**软键盘遮挡打字板？**
`android.soft_input_mode = resize`，窗口会上移。若机型异常，可改为 `pan`。

**数据存在哪？会不会丢？**
`/data/data/org.sentenceclub.englishclub/files`（应用私有目录）。
卸载即清除，重要进度请从设置页导出数据库。

## 七、打包踩坑记录（重要，改 spec 前先看）

| 报错 | 根因 | 解法 |
| --- | --- | --- |
| `"fullsensor" is not a valid value for "orientation"` | buildozer 合法值仅 `landscape`/`portrait`/`landscape-reverse`/`portrait-reverse`/`all` | 写 `all`（四向自由旋转） |
| `call to undeclared function 'preadv' / 'pwritev'` | 这两个函数 Android **API 24+** 才提供，`minapi=23` 时头文件不声明 | `android.minapi = 24` |
| （预期会出现）Kivy 编译期 C-API 报错 | 默认拉最新 Python 3.14，而 Kivy 2.3.0 只支持到 3.12 | `python3==3.11.9` 锁定版本 |

两个硬约束已写进 `.github/workflows/build-apk.yml` 的 **Validate spec** 步骤，
改坏配置会在几秒内失败，不用等半小时才发现。

## 八、与桌面版的差异

| | 桌面版（PyQt5） | 安卓版（Kivy） |
| --- | --- | --- |
| 输入 | 物理键盘 | 系统软键盘（也支持外接键盘） |
| 音标 | 标准 IPA | ASCII 简易音标 |
| 布局 | 左侧导航 | 底部导航 |
| 音效/朗读 | QtMultimedia | Kivy SoundLoader |
| 数据 | `~/.english_club/` | 应用私有目录 |

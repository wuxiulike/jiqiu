# 吉球 · 双色球数据实验室

本地桌面程序，支持 Windows 和 macOS。提供中国福彩网历史数据同步、21 类走势图、随机/热号/冷号/混合选号、滚动回测以及 OpenAI 兼容模型走势分析和候选号码。号码和统计仅供娱乐；历史数据不能证明未来的中奖概率更高。

首页「今日选号」可用滑杆选择 1–5 注。点击开始后，程序先生成混合策略初选，再把该批号码和「走势图」选定范围的历史数据发送至已配置的模型；模型返回有效结果后号码球依次停下。AI 调整的号码显示为黄色，选号完成后显示印章并播放提示音。模型未配置、联网失败或结果无效时，页面保留初选记录并标记 AI 未完成。

「选号记录」保存程序初选、AI 最终号码以及高级页面产生的号码。程序初选仅作为过程记录，最终号码才参与自动核对。每次打开时先同步官网最新期次，再核验每组号码基准期之后的紧接一期；发现命中奖级时显示 5 秒庆祝动画。福运奖是否启用按对应期官方公告确认，公告无法读取时保持待核对。记录是选号参考，并不证明实际购票，请以中奖彩票及官方公告核实。选号前须先完成官方数据同步，以确保基准期准确。

## 运行

安装 Python 3.10 或更新版本，在项目目录执行：

```bash
python -m venv .venv
```

Windows：

```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python main.py
```

macOS：

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

首次启动会将随项目提供的历史数据复制到系统应用数据目录；每次打开会从中国福彩网同步最新数据。首页展示实际数据范围和同步状态。网络失败可使用本地数据，并手动重试。导入 CSV 列名为 `code,date,red,blue`，示例：

```csv
code,date,red,blue
2024001,2024-01-02,"01,02,03,04,05,06",07
```

导入数据不会自动核验来源；如与已有期号重复，会用导入内容更新本地记录。请只导入可信数据。

## 模型配置

在模型设置页输入兼容 OpenAI 的 Base URL、模型名和 API Key。DeepSeek 可使用 `https://api.deepseek.com/v1` 和 `deepseek-chat`；其他服务商以其文档为准。密钥存储在系统凭据管理器，留空保存会保留原密钥；需要更换时输入新密钥并保存。

“走势图”页面可选择走势类别和期数。“AI 预测”页面先选择注数，可通过“查看发送摘要”检查数据，再点击“分析走势并生成候选号”发送到配置的模型服务。摘要含所选范围的历史开奖、走势指标与已有程序算法结果；选择“全部”会显著增加请求量。连接测试和 AI 分析可能产生费用。请仅使用可信服务地址，服务商会收到用于鉴权的 API Key。

## 测试及打包

安装 `requirements-dev.txt` 后执行：

```bash
python -m pytest -q
python -m compileall -q lottery main.py
```

在各目标系统分别打包。Windows 使用脚本隔离 DLL 搜索路径，避免误打包其他软件的 ICU 库：

```powershell
.\build-windows.ps1
```

```bash
python -m PyInstaller --noconfirm --clean --windowed --name 吉球 --icon assets/jiqiu.icns --add-data "assets/jiqiu.png:assets" --add-data "data/history.sqlite3:data" --add-data "assets/celebration.wav:assets" --add-data "assets/rolling.wav:assets" --add-data "assets/complete.wav:assets" main.py
```

Windows 构建产物为 `dist/吉球.exe`；macOS 使用该系统上构建的应用。凭据存储依赖可用的系统密钥链。

## 数据范围

项目随附数据取自中国福彩网接口，实际起止期号显示在历史开奖页面。官网默认查询不一定覆盖双色球发行以来所有期次；若获取更早的可信数据，可通过 CSV 补充。数据查询接口可能变化或暂时不可用。

庆祝音效由 [Amada44 的掌声](https://commons.wikimedia.org/wiki/File:Sound_Effects_-_Applause_after_a_concert.ogg)和 [Almanta 的鞭炮声](https://commons.wikimedia.org/wiki/File:Firecracker_sounds_2022-12-31T23-25-40.ogg)裁剪混合而成，原作品均为 CC0。

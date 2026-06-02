# 二手图书自助回收售卖一体机原型

这个原型使用 MySQL 数据库和一个摄像头识别脚本。识别流程优先读取书籍 ISBN 条码；如果没有识别到条码，则尝试 OCR 识别封面文字，并和数据库中的书名、作者、出版社做模糊匹配。

## 安装依赖

```powershell
pip install -r requirements.txt
```

OCR 需要本机安装 Tesseract，并安装中文语言包 `chi_sim`。如果只使用 ISBN 条码识别，可以不配置 OCR。

## 初始化数据库

确保本机已经安装并启动 MySQL Server，然后执行：

```powershell
python init_mysql_database.py --user root --password "123456"
```

脚本会创建 `used_book_recycle` 数据库，并导入少量书籍样例数据、品相估价规则和回收记录表。

也可以直接用 MySQL 客户端执行 SQL 文件：

```powershell
mysql -u root -p < mysql_schema.sql
```

## 运行摄像头识别

```powershell
python camera_book_recognition.py --db-user root --db-password "123456"
```

打开摄像头后，将书籍 ISBN 条码或封面对准摄像头，按空格识别，按 `q` 退出。识别成功后，程序会输出书籍信息、品相等级、破损评分、完整度评分和建议回收价，并把记录写入 `recycle_records` 表。

## Ollama 本地 AI 辅助识别

程序会先使用本地 ISBN 条码和 OCR 识别；如果本地识别没有匹配到数据库，会调用本机 Ollama 视觉模型辅助识别书名、作者、出版社和 ISBN，再回到 MySQL 中匹配书籍。

安装 Ollama 后拉取视觉模型：

```powershell
$env:OLLAMA_MODELS="D:\code\Used_book_recycle\ollama_models"
ollama pull qwen2.5vl:3b
```

如果电脑没有 `ollama` 命令，请先安装 Windows 版 Ollama：

```text
https://ollama.com/download/windows
```

安装完成后重新打开 PowerShell，再执行模型下载命令。

如需手动启动 Ollama 服务：

```powershell
.\start_ollama_model.ps1
```

Windows 用户名包含中文或特殊字符时，Ollama 底层模型加载可能会把默认模型路径解析错误。当前项目已使用纯英文模型目录：

```text
D:\code\Used_book_recycle\ollama_models
```

如果重装 Ollama 或换电脑部署，请先设置：

```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_MODELS", "D:\code\Used_book_recycle\ollama_models", "User")
```

运行识别程序：

```powershell
python camera_book_recognition.py --db-user root --db-password "123456"
```

指定 Ollama 地址或模型：

```powershell
python camera_book_recognition.py --db-user root --db-password "123456" --ollama-host "http://127.0.0.1:11434" --ollama-model qwen2.5vl:3b
```

关闭本地 AI 辅助识别：

```powershell
python camera_book_recognition.py --db-user root --db-password "123456" --disable-ai
```

如果默认摄像头不可用，可以指定编号：

```powershell
python camera_book_recognition.py --camera 1
```

如果封面识别不到，使用调试模式查看 OCR 原文和匹配分数：

```powershell
python camera_book_recognition.py --db-user root --db-password "123456" --debug-ocr
```

数据库连接也可以用环境变量配置：

```powershell
$env:MYSQL_HOST="127.0.0.1"
$env:MYSQL_PORT="3306"
$env:MYSQL_USER="root"
$env:MYSQL_PASSWORD="123456"
$env:MYSQL_DATABASE="used_book_recycle"
python camera_book_recognition.py
```

## 数据库表

- `books`：书籍基础信息和市场参考价。
- `condition_rules`：品相等级与估价系数。
- `recycle_records`：每次识别和估价记录。

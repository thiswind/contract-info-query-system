# 合同信息查询系统

合同信息查询系统是一个面向合同台账、合同 PDF 原文和日常检索场景的轻量级原型系统。项目提供命令行工具和 Web 页面，用于导入授权范围内的合同台账、建立本地 SQLite 索引、查询合同元数据，并查看或下载本地保存的合同 PDF 文件。

本仓库是 public 代码仓库，只包含系统源码和使用说明，不包含任何真实合同 Excel、PDF、SQLite 索引或派生数据。

## 为什么开发

在日常合同管理中，合同资料常见于采购平台下载文件、学院业务文件夹、人工整理台账等多个位置。Excel 台账记录了合同编号、项目名称、供应商、金额、签订日期等结构化信息，而合同 PDF 原文通常单独存放，二者分离后会带来几个问题：

- 人工在 Excel 和文件夹之间来回查找，效率低且容易漏查；
- 合同编号、序号、文件名和 PDF 原文之间缺少统一索引；
- 日常管理、审查、统计和原文查阅需要稳定入口；
- 真实合同资料不适合进入代码仓库，系统必须支持本地数据目录和外置部署。

本项目的目标是先提供一个可运行、可部署、可扩展的原型：把授权数据放在本地或服务器指定目录，系统只把元数据和文件路径写入本地 SQLite 数据库，代码仓库保持干净。

## 功能模块

### 1. 数据目录与配置模块

系统通过环境变量配置运行目录、数据目录、数据库路径、监听地址和二级访问路径。默认以当前工作目录为 workspace，并使用：

- `data/raw/`：原始授权数据目录；
- `data/raw/采购合同细节.xlsx`：合同台账 Excel；
- `data/raw/合同文件/`：合同 PDF 文件目录；
- `data/processed/contracts.sqlite3`：本地 SQLite 索引；
- `/contract-query/`：默认 Web 二级路径。

### 2. Excel 导入模块

读取合同台账 Excel，校验必要表头，解析合同元数据，并可通过 `--dry-run` 先查看导入报告。导入内容包括合同编号、项目名称、采购人、供应商、金额、采购方式、签订日期、备注等台账字段。

### 3. PDF 文件映射模块

扫描 `合同文件/` 目录中的 PDF 文件，按合同编号或序号前缀建立合同记录与 PDF 文件记录之间的关联。系统保存的是相对路径和文件元数据，不把 PDF 内容写入 Git。

### 4. SQLite 索引模块

使用 SQLite 保存合同记录、文件记录和查询所需索引。可以在没有真实数据的情况下初始化空数据库，便于验证程序安装和基础入口。

### 5. CLI 命令行模块

安装后提供 `contract-query` 命令，支持：

- `inventory`：盘点 `data/raw` 下的 Excel 和 PDF 文件；
- `import-excel`：导入 Excel 台账并映射 PDF；
- `import-excel --dry-run`：只扫描和报告，不写数据库；
- `build-index`：初始化 SQLite 数据库；
- `search "关键词"`：按关键字查询合同元数据；
- `check-files`：检查数据库中的文件引用是否仍存在；
- `serve`：启动 FastAPI Web 服务。

### 6. Web 查询模块

基于 FastAPI 和 Jinja2 提供 Web 页面，包括首页、合同列表、筛选查询和合同详情。可按关键词、年份、供应商、采购方式、金额区间等条件查询合同元数据。

### 7. 文件查看模块

在合同详情页中查看已关联的 PDF 文件，支持浏览器内联查看和下载。文件读取被限制在配置的原始数据目录内，避免任意路径访问。

### 8. 新增合同模块

提供 Web 表单新增合同记录，可上传 PDF 或引用已在原始数据目录中的 PDF 文件。新增记录写入本地 SQLite 数据库和本地数据目录，不进入 Git 仓库。

### 9. 导入与健康检查模块

提供导入页面、统计信息、文件检查接口和健康检查接口，便于部署后确认服务、数据目录和数据库状态。

## 环境要求

- Python 3.9 或更高版本；
- 支持 Linux、macOS、Windows/WSL 等常见 Python 运行环境；
- 依赖安装方式支持 `requirements.txt` 和 editable install。

## 安装方法

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

如果只需要安装项目和依赖，也可以直接执行：

```bash
python -m pip install -e .
```

安装完成后检查命令行入口：

```bash
contract-query --help
```

## 数据目录准备

本仓库不提供真实合同数据。使用者需要在授权范围内自行准备数据，例如：

```text
data/
  raw/
    采购合同细节.xlsx
    合同文件/
      示例合同文件-001.pdf
      示例合同文件-002.pdf
  processed/
```

请不要把真实合同、Excel、PDF、SQLite 数据库或派生文件提交到 Git。项目 `.gitignore` 已默认排除 `data/`、Office 文档、PDF、压缩包、虚拟环境、日志、缓存和本地 AI 工作区。

## 配置项

系统会自动读取 `.env` 文件，也可以直接设置环境变量。常用配置如下：

```bash
export CONTRACT_QUERY_WORKSPACE=/path/to/contract-info-query-system
export CONTRACT_QUERY_DATA_DIR=/path/to/contract-info-query-system/data
export CONTRACT_QUERY_RAW_DIR=/path/to/contract-info-query-system/data/raw
export CONTRACT_QUERY_PROCESSED_DIR=/path/to/contract-info-query-system/data/processed
export CONTRACT_QUERY_DB=/path/to/contract-info-query-system/data/processed/contracts.sqlite3
export CONTRACT_QUERY_HOST=127.0.0.1
export CONTRACT_QUERY_PORT=8000
export CONTRACT_QUERY_ROOT_PATH=/contract-query
```

默认健康检查接口位于根路径：

```text
/health
```

业务 Web 默认挂载在二级路径：

```text
/contract-query/
```

## 命令行使用

### 盘点原始数据

```bash
contract-query inventory
```

### 预检查 Excel 导入

```bash
contract-query import-excel --dry-run
```

### 导入 Excel 并映射 PDF

```bash
contract-query import-excel
```

### 初始化空数据库

```bash
contract-query build-index
```

### 查询合同

```bash
contract-query search "关键词"
```

### 检查文件引用

```bash
contract-query check-files
```

## Web 服务使用

启动本地服务：

```bash
contract-query serve --host 127.0.0.1 --port 8000
```

访问：

```text
http://127.0.0.1:8000/contract-query/
http://127.0.0.1:8000/health
```

如果部署在服务器上，建议让应用继续监听本机端口，再通过 Nginx 等反向代理发布到二级路径，例如 `/contract-query/`。真实合同数据应放在服务器本地授权目录中，不应打包进镜像、发布包或 Git 仓库。

## 无真实数据的基础验证

可以用临时 workspace 验证安装和基础入口，不污染当前项目目录：

```bash
export CONTRACT_QUERY_WORKSPACE=/tmp/contract-query-demo
contract-query build-index
contract-query search "test"
```

以上命令会在临时目录下创建空数据库，并返回空查询结果或基础状态。

## 数据安全说明

- public 仓库不包含真实合同 Excel、PDF、SQLite 索引或任何派生数据；
- `.gitignore` 已排除 `data/`、`*.xlsx`、`*.xls`、`*.pdf`、`*.sqlite3`、虚拟环境、发布包、日志、`.claude/`、`cursor-agent-team/` 等本地内容；
- README 中只使用示例路径和示例文件名，不披露真实合同名称、供应商、金额、文件名或合同正文；
- 使用者必须自行准备具备合法授权的数据文件；
- 部署时建议把真实数据目录与代码仓库、发布包、备份脚本明确隔离。

## 当前限制

- 当前原型主要基于 Excel 字段、文件名和备注查询；
- 扫描版 PDF 暂不做 OCR 正文全文检索；
- 尚未内置用户登录、权限控制、审计日志和细粒度访问控制；
- 批量统计导出、OCR、全文检索、审批流程等能力可在后续版本扩展。

## 项目结构

```text
src/contract_query/
  api.py            # FastAPI Web 服务
  cli.py            # 命令行入口
  config.py         # 环境变量和路径配置
  db.py             # SQLite 表结构初始化
  excel_importer.py # Excel 导入和 PDF 映射
  file_store.py     # PDF 保存和路径解析
  indexer.py        # 原始数据盘点
  search.py         # 查询、新增和统计
  templates/        # Jinja2 页面模板
  static/           # Web 静态资源
```

## 许可证

当前仓库未声明开源许可证。如需对外复用、二次分发或商业使用，请先补充明确的许可证文件。
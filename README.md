# ACL Anthology 论文提取器

从 ACL Anthology 自动提取论文题目、作者与摘要，导出为 Markdown 文件，支持 Typora 流畅打开。

## 功能

- 支持 6 个会议：ACL、EMNLP、NAACL、EACL、COLING、Findings
- 年份可选（1963–2026）
- 按卷自动拆分（Long Papers、Short Papers、System Demos 等）
- 单文件超过 1MB 自动进一步拆分，确保 Typora 可流畅打开
- 紧凑模式：仅导出题目 + 作者
- **多翻译服务集成**（详见下方翻译服务说明）
- **按卷/部分灵活选择翻译范围**
- **翻译进度实时显示 + 停止翻译功能**
- 数据来源：ACL Anthology 官方 XML（GitHub 仓库）

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 启动应用
streamlit run app.py --server.headless true
```

浏览器打开 http://localhost:8501

## 使用流程

1. 选择会议（ACL / EMNLP / NAACL 等）
2. 选择年份
3. 勾选"紧凑模式"（可选，仅题目+作者）
4. 点击"获取论文列表"
5. 展开"翻译设置"，选择翻译服务和配置参数（可选）
6. 选择要翻译的部分（按卷/按拆分部分）
7. 点击"开始翻译"，等待翻译完成
8. 下载原文 Markdown 文件和翻译对照版本

## 文件命名规则

```
{会议}_{年份}_{卷类型}_{卷ID}_{部分}.md
```

示例：
- `ACL_2026_Long_Papers_long.md`
- `ACL_2026_Long_Papers_long_第1部分.md`
- `EMNLP_2024_Short_Papers_short_紧凑.md`

## 输出内容

每篇论文包含：
- 题目
- 作者
- 摘要（紧凑模式不含摘要）

翻译版本额外包含：
- 题目标题翻译
- 摘要翻译（紧跟在原文下方）

## 翻译服务

支持 5 种翻译服务，可按需选择：

### 1. OpenAI 兼容接口
- 支持 OpenAI、DeepSeek、智谱、Gemini 等兼容接口
- 需配置 API Base URL、API Key、模型名称

### 2. DeepL
- 注册地址：https://www.deepl.com/pro-api
- 免费版每月 50 万字符额度
- 支持实时查询本月用量（进度条显示）
- 翻译质量高，适合学术文本

### 3. 百度翻译（通用版）
- 注册地址：https://fanyi-api.baidu.com/
- 标准版每月 5 万字符免费额度
- 需配置 APP ID 和密钥

### 4. 百度大模型翻译
- 文档：https://fanyi-api.baidu.com/doc/21
- 支持两种认证方式：
  - **API Key 认证**：填写 APP ID + API Key
  - **签名认证**：填写 APP ID + 密钥（与通用版相同）
- **额度用尽自动降级**：当大模型翻译额度耗尽时，自动切换到百度通用翻译
- 支持点击"检测大模型翻译额度"按钮查询可用状态
- 翻译质量优于通用版，适合复杂学术文本

### 5. LibreTranslate
- 开源免费翻译服务
- 可使用公共实例 https://libretranslate.com 或自建
- 无字符限制

### 翻译功能特性
- **按部分选择**：可针对每个卷/拆分部分独立选择是否翻译
- **翻译内容可选**：仅题目 / 仅摘要 / 题目+摘要
- **实时进度显示**：进度条 + 百分比
- **停止翻译**：翻译过程中可随时停止，已翻译部分保留

## 技术栈

- Python
- Streamlit（Web 界面）
- requests（HTTP 请求）
- XML 解析（标准库）

## 数据来源

[ACL Anthology](https://aclanthology.org/) — 计算语言学领域的官方论文存档，涵盖 ACL、EMNLP、NAACL、EACL、COLING、Findings 等主要会议，数据以 XML 格式托管在 [GitHub](https://github.com/acl-org/acl-anthology)。

## 许可证

MIT

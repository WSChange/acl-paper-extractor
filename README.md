# ACL Anthology 论文提取器

从 ACL Anthology 自动提取论文题目、作者与摘要，导出为 Markdown 文件，支持 Typora 流畅打开。

## 功能

- 支持 6 个会议：ACL、EMNLP、NAACL、EACL、COLING、Findings
- 年份可选（1963–2026）
- 按卷自动拆分（Long Papers、Short Papers、System Demos 等）
- 单文件超过 1MB 自动进一步拆分，确保 Typora 可流畅打开
- 紧凑模式：仅导出题目 + 作者
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
5. 按卷下载 Markdown 文件

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

## 技术栈

- Python
- Streamlit（Web 界面）
- requests（HTTP 请求）
- XML 解析（标准库）

## 数据来源

[ACL Anthology](https://aclanthology.org/) — 计算语言学领域的官方论文存档，数据以 XML 格式托管在 [GitHub](https://github.com/acl-org/acl-anthology)。

## 许可证

MIT

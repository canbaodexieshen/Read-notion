# 阅读热力图

从 Notion 数据库的 `日期` 与 `总阅读时长`（公式数字，单位秒）生成 GitHub 风格阅读热力图。同一天的记录累加，悬停显示日期和精确时长。

网页：https://canbaodexieshen.github.io/Study-notion-heatmap/

保留原项目布局、年份切换和主题按钮。GitHub 原生绿色：0 为灰色；0–60 分钟为 #9be9a8；60–120 分钟为 #40c463；120–240 分钟为 #30a14e；超过 240 分钟为 #216e39。

## 更新与发布

- 仓库 Secret `NOTION_TOKEN` 保存 Notion 集成密钥，数据库 ID 在 workflows 中配置。密钥不会输出到网站。
- `Study Heatmap Engine` 每天北京时间 23:00 更新，也可手动运行。
- 所有有数据的年份会一起重新生成，年份清单位于 `study_heatmap/years.json`。
- `Publish Reading Heatmap` 在代码推送或数据更新完成后通过 GitHub Actions 发布 Pages。Settings → Pages 的 Source 选择 GitHub Actions。
- `study.html` 和首页均可直接打开，无需 image 参数；兼容原有 image 参数和 theme=dark。

本地运行：安装 requirements.txt 后，设置 NOTION_TOKEN 和 NOTION_DATABASE_ID，再执行 `python update_study_heatmap.py`。不要把 token 写入代码或提交到 Git。

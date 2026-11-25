import os
import subprocess
import datetime
import re
import sys
import urllib.request
import json


def get_notion_data(token, database_id):
    """从 Notion 日计划数据库拉取所有页面，提取日期和总学习时长（分钟）"""
    print("🔍 正在连接 Notion 数据库并抓取学习时长数据...")
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    data_dict = {}
    has_more = True
    next_cursor = None

    while has_more:
        body = {}
        if next_cursor:
            body["start_cursor"] = next_cursor
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                res = json.loads(response.read())
                for result in res.get("results", []):
                    props = result.get("properties", {})

                    # 读取"日期"属性（date 类型）
                    date_val = None
                    if props.get("日期") and props["日期"].get("date"):
                        date_val = props["日期"]["date"].get("start")

                    # 读取"总阅读时长"属性，兼容 formula / number / rollup 三种类型
                    val = 0
                    val_prop = props.get("总阅读时长")
                    if val_prop:
                        ptype = val_prop.get("type")
                        if ptype == "formula":
                            f_data = val_prop.get("formula", {})
                            if f_data.get("type") == "number":
                                val = f_data.get("number") or 0
                            elif f_data.get("type") == "string":
                                match = re.search(
                                    r"(\d+(\.\d+)?)",
                                    str(f_data.get("string", "0")),
                                )
                                val = float(match.group(1)) if match else 0
                        elif ptype == "number":
                            val = val_prop.get("number") or 0
                        elif ptype == "rollup":
                            r_data = val_prop.get("rollup", {})
                            if r_data.get("type") == "number":
                                val = r_data.get("number") or 0

                    if date_val and val > 0:
                        date_str = str(date_val).split("T")[0]
                        data_dict[date_str] = data_dict.get(date_str, 0) + val / 60.0

                has_more = res.get("has_more", False)
                next_cursor = res.get("next_cursor")
        except Exception as e:
            print(f"❌ 获取 Notion 数据失败: {e}")
            sys.exit(1)

    total = int(sum(data_dict.values()))
    print(f"✅ 共读取到 {len(data_dict)} 天的学习记录，累计 {total} 分钟")
    return data_dict


def interpolate_color(color1, color2, factor):
    """根据 factor (0.0~1.0) 在两个十六进制颜色之间线性插值"""
    factor = max(0.0, min(1.0, factor))
    c1 = [int(color1[i : i + 2], 16) for i in (1, 3, 5)]
    c2 = [int(color2[i : i + 2], 16) for i in (1, 3, 5)]
    res = [int(c1[i] + (c2[i] - c1[i]) * factor) for i in range(3)]
    return f"#{res[0]:02x}{res[1]:02x}{res[2]:02x}"


def get_color_for_minutes(val):
    """GitHub 原生绿色：0、≤1h、≤2h、≤4h、>4h。"""
    if val <= 0:
        return "#ebedf0"
    if val <= 60:
        return "#9be9a8"
    if val <= 120:
        return "#40c463"
    if val <= 240:
        return "#30a14e"
    return "#216e39"


def format_duration(minutes):
    """将分钟数格式化为 'X小时Y分钟'（不足1小时只显示分钟）"""
    seconds = round(minutes * 60)
    h, remainder = divmod(seconds, 3600)
    m, sec = divmod(remainder, 60)
    suffix = f"{sec}秒" if sec else ""
    if h > 0:
        return f"{h}小时{m}分钟{suffix}"
    else:
        return f"{m}分钟{suffix}"


def process_svg_styling(file_path, data_dict, current_year, total_override=None):
    """对底稿 SVG 执行渐变着色，并修正年度统计文字。
    若提供 total_override，则用它覆盖左上角统计值（用于年度归档场景）。
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. 修正统计文字：将 "2026: 0 分钟" 替换为真实总和的时分格式
    total_minutes = total_override if total_override is not None else sum(v for d, v in data_dict.items() if d.startswith(str(current_year) + "-"))
    total_time_str = format_duration(total_minutes)
    content = re.sub(
        rf"({current_year}:\s*)[0-9\.]+\s*分钟",
        rf"\g<1>{total_time_str}",
        content,
    )

    # 2. 对每个日期格子应用渐变颜色，同时更新 title 显示"日期 + 时长"
    # 注意：github_heatmap 生成的日期格子格式为：
    #   <rect fill="..." ...><title>YYYY-MM-DD</title></rect>
    # 背景矩形是自闭合的 <rect ... />，不会被下面的正则匹配到，安全。
    def rect_replacer(match):
        rect_tag = match.group(0)
        # 从 <title> 子标签中提取日期
        date_match = re.search(r"<title>(\d{4}-\d{2}-\d{2})", rect_tag)
        if not date_match:
            return rect_tag  # 没有日期的格子（理论上不会出现）保持不变

        date_str = date_match.group(1)
        val = float(data_dict.get(date_str, 0))
        color = get_color_for_minutes(val)
        
        # 更新 <title> 标签，显示"日期 - X小时Y分钟"（不足1小时只显示分钟）
        if val > 0:
            minutes_text = format_duration(val)
        else:
            minutes_text = "无记录"
        rect_tag = re.sub(
            r"<title>\d{4}-\d{2}-\d{2}</title>",
            f"<title>{date_str} - {minutes_text}</title>",
            rect_tag,
            count=1
        )
        
        # 只替换第一个 fill 属性（格子本身的颜色）
        return re.sub(r'fill="[^"]+"', f'fill="{color}"', rect_tag, count=1)

    # 精确匹配：只处理包含 <title> 子标签的日期格子 rect
    content = re.sub(
        r'<rect\b[^>]*><title>.*?</title></rect>',
        rect_replacer,
        content,
        flags=re.DOTALL,
    )

    # 3. 补充白色背景（若 SVG 本身没有背景矩形）
    if 'id="background"' not in content:
        content = content.replace("<svg ", '<svg style="background-color:white;" ', 1)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"🎨 着色完成：总计 {total_minutes} 分钟 / {len(data_dict)} 天")


def generate_heatmap(notion_token, database_id, year, me_name=None):
    """调用 github_heatmap CLI 生成底稿 SVG，返回输出路径"""
    if me_name is None:
        me_name = os.getenv("HEATMAP_NAME", "阅读热力图")

    command = [
        "github_heatmap",
        "notion",
        "--notion_token", notion_token,
        "--database_id", database_id,
        "--date_prop_name", "日期",
        "--value_prop_name", "总阅读时长",
        "--unit", "分钟",
        "--year", str(year),
        "--me", me_name,
        "--without-type-name",
        "--background-color", "#FFFFFF",
        "--track-color", "#ebedf0",
        "--dom-color", "#ebedf0",
        "--text-color", "#000000",
    ]

    print(f"🚀 正在调用热力图引擎生成 {year} 年底稿...")
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("热力图引擎生成失败，请检查 Notion 授权及字段")

    return "OUT_FOLDER/notion.svg"


def main():
    notion_token = os.getenv("NOTION_TOKEN")
    database_id = os.getenv("NOTION_DATABASE_ID")

    if not notion_token or not database_id:
        print("❌ 缺少必要的环境变量：NOTION_TOKEN 或 NOTION_DATABASE_ID")
        sys.exit(1)

    current_year = datetime.datetime.now().year
    target_year = int(os.getenv("YEAR", current_year))

    # ① 拉取 Notion 数据
    real_data = get_notion_data(notion_token, database_id)

    years = sorted({int(d[:4]) for d in real_data} | {target_year})
    os.makedirs("study_heatmap", exist_ok=True)
    os.makedirs("old_heatmap", exist_ok=True)
    for year in years:
        svg_path = generate_heatmap(notion_token, database_id, year)
        process_svg_styling(svg_path, real_data, year)
        dest = "study_heatmap/main.svg" if year == target_year else f"old_heatmap/{year}.svg"
        os.replace(svg_path, dest)
    with open("study_heatmap/years.json", "w") as f:
        json.dump({"current": target_year, "years": sorted(years, reverse=True)}, f)


if __name__ == "__main__":
    main()

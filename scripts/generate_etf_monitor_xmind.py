from __future__ import annotations

import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "ETF监控思维导图.xmind"

CONTENT_NS = "urn:xmind:xmap:xmlns:content:2.0"
STYLE_NS = "urn:xmind:xmap:xmlns:style:2.0"
MANIFEST_NS = "urn:xmind:xmap:xmlns:manifest:1.0"
META_NS = "urn:xmind:xmap:xmlns:meta:2.0"
FO_NS = "http://www.w3.org/1999/XSL/Format"
SVG_NS = "http://www.w3.org/2000/svg"

ET.register_namespace("", CONTENT_NS)
ET.register_namespace("fo", FO_NS)
ET.register_namespace("svg", SVG_NS)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


BRANCHES = [
    (
        "监控标的",
        "blue",
        [
            ("588000.SH｜科创50ETF华夏", []),
            ("159915.SZ｜创业板ETF易方达", []),
            ("510300.SH｜沪深300ETF华泰柏瑞", []),
            ("513310.SH｜中韩半导体ETF华泰柏瑞", ["首个就绪时间：10:45"]),
            ("配置入口：ETF_SYMBOLS", ["格式：代码:名称,代码:名称", "支持扩展或替换标的"]),
        ],
    ),
    (
        "监控指标与周期",
        "cyan",
        [
            ("核心指标：K线成交额 amount", ["不以成交量 volume 作为触发口径"]),
            ("常规时段：15分钟K线", ["覆盖至 14:30（含）"]),
            ("尾盘时段：5分钟K线", ["14:30 后至 15:00"]),
            ("仅评估已完成K线", ["完成确认延迟：60秒"]),
            ("附带展示", ["OHLC价格", "成交量与成交额", "最新K线/最后更新"]),
        ],
    ),
    (
        "异动判定规则",
        "orange",
        [
            ("放大倍数 = 当前成交额 ÷ 对比成交额", []),
            (
                "对比基准",
                [
                    "09:45、13:15：上一交易日同一时点",
                    "其他时点：优先日内前一根同周期K线",
                    "未触发/前一根缺失：回退上一交易日同一时点",
                ],
            ),
            (
                "09:45 开盘规则",
                ["提醒：≥ 1.15×", "严重：≥ 3.00×"],
            ),
            (
                "常规规则（含13:15、截至14:30）",
                ["提醒：≥ 1.30×", "严重：≥ 5.00×"],
            ),
            (
                "尾盘规则（14:30后）",
                ["提醒：≥ 1.30×", "严重：≥ 4.50×"],
            ),
            ("不触发情形", ["倍数低于阈值", "对比成交额缺失或≤0", "成交额缩小：不告警"]),
        ],
    ),
    (
        "告警与通知",
        "red",
        [
            ("级别", ["warning｜提醒", "critical｜严重"]),
            ("告警内容", ["标的与K线时间", "当前/对比成交额", "放大倍数与阈值", "对比基准说明"]),
            ("去重键：symbol + candle_time", ["避免重复入库与重复邮件"]),
            ("批量邮件", ["同一时点多标的合并", "SMTP默认关闭，可配置启用"]),
            ("无异动通知", ["K线完成后再确认90秒", "全标的就绪后合并发送"]),
            ("收盘日报：15:00", ["汇总当日异动", "无异动也发送状态", "同一交易日仅一次"]),
        ],
    ),
    (
        "数据源与容错",
        "green",
        [
            ("主数据源：AkShare / 东方财富ETF分钟行情", []),
            ("回退链路", ["腾讯分钟行情", "AkShare / 新浪A股分钟行情"]),
            ("本地持久化：SQLite", ["K线缓存", "告警日志", "通知事件"]),
            ("数据源失败", ["页面回退本地缓存", "状态标记 cached / degraded", "不阻断历史查看"]),
            ("数据修正", ["按标的+时间+周期更新", "以更完整成交额覆盖", "同步修正关联告警"]),
        ],
    ),
    (
        "运行机制",
        "purple",
        [
            ("后台轮询：每60秒", ["多标的并行拉取", "支持手动单标的/全量轮询"]),
            ("检测范围", ["回扫最新交易日未告警K线", "避免晚启动或数据恢复后漏报"]),
            ("批次时效", ["通知最大滞后：900秒", "等待应就绪标的保持同一K线时点"]),
            ("时区：Asia/Shanghai", []),
            ("调度开关：SCHEDULER_ENABLED", []),
        ],
    ),
    (
        "监控看板与接口",
        "teal",
        [
            ("看板", ["切换ETF标的", "成交额/价格K线", "实时/缓存/异常/等待状态", "当前异动与历史日志"]),
            ("GET /api/monitor/symbols", ["监控标的列表"]),
            ("GET /api/monitor/snapshot", ["最新快照与当日K线"]),
            ("GET /api/alerts", ["按标的查询告警"]),
            ("POST /api/monitor/poll", ["手动轮询单标的"]),
            ("POST /api/monitor/poll-all", ["手动轮询全部标的"]),
            ("GET /api/health", ["服务与数据状态"]),
        ],
    ),
]


def qname(namespace: str, tag: str) -> str:
    return f"{{{namespace}}}{tag}"


def add_topic(parent: ET.Element, title: str, style_id: str) -> ET.Element:
    topic = ET.SubElement(
        parent,
        qname(CONTENT_NS, "topic"),
        {"id": new_id("topic"), "style-id": style_id},
    )
    ET.SubElement(topic, qname(CONTENT_NS, "title")).text = title
    return topic


def add_children(topic: ET.Element, items, branch_style: str) -> None:
    if not items:
        return
    children = ET.SubElement(topic, qname(CONTENT_NS, "children"))
    topics = ET.SubElement(children, qname(CONTENT_NS, "topics"), {"type": "attached"})
    for title, leaves in items:
        child = add_topic(topics, title, f"{branch_style}-level2")
        if leaves:
            child_children = ET.SubElement(child, qname(CONTENT_NS, "children"))
            child_topics = ET.SubElement(
                child_children, qname(CONTENT_NS, "topics"), {"type": "attached"}
            )
            for leaf in leaves:
                add_topic(child_topics, leaf, f"{branch_style}-level3")


def build_content() -> bytes:
    root = ET.Element(qname(CONTENT_NS, "xmap-content"), {"version": "2.0"})
    sheet = ET.SubElement(root, qname(CONTENT_NS, "sheet"), {"id": new_id("sheet")})
    ET.SubElement(sheet, qname(CONTENT_NS, "title")).text = "ETF监控思维导图"
    root_topic = ET.SubElement(
        sheet,
        qname(CONTENT_NS, "topic"),
        {
            "id": new_id("root"),
            "style-id": "root-topic",
            "structure-class": "org.xmind.ui.map.clockwise",
        },
    )
    ET.SubElement(root_topic, qname(CONTENT_NS, "title")).text = "ETF成交额异动监控"
    children = ET.SubElement(root_topic, qname(CONTENT_NS, "children"))
    topics = ET.SubElement(children, qname(CONTENT_NS, "topics"), {"type": "attached"})
    for title, color, items in BRANCHES:
        branch = add_topic(topics, title, f"{color}-level1")
        add_children(branch, items, color)

    notes = ET.SubElement(root_topic, qname(CONTENT_NS, "notes"))
    plain = ET.SubElement(notes, qname(CONTENT_NS, "plain"))
    plain.text = "依据当前项目代码与默认配置整理；阈值均可通过环境变量调整。"
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


COLORS = {
    "blue": ("#2563EB", "#EFF6FF", "#1E3A8A"),
    "cyan": ("#0891B2", "#ECFEFF", "#164E63"),
    "orange": ("#EA580C", "#FFF7ED", "#7C2D12"),
    "red": ("#DC2626", "#FEF2F2", "#7F1D1D"),
    "green": ("#16A34A", "#F0FDF4", "#14532D"),
    "purple": ("#7C3AED", "#F5F3FF", "#4C1D95"),
    "teal": ("#0D9488", "#F0FDFA", "#134E4A"),
}


def topic_style(parent: ET.Element, style_id: str, properties: dict[str, str]) -> None:
    style = ET.SubElement(
        parent, qname(STYLE_NS, "style"), {"id": style_id, "type": "topic"}
    )
    ET.SubElement(style, qname(STYLE_NS, "topic-properties"), properties)


def build_styles() -> bytes:
    ET.register_namespace("", STYLE_NS)
    root = ET.Element(qname(STYLE_NS, "xmap-styles"), {"version": "2.0"})
    styles = ET.SubElement(root, qname(STYLE_NS, "automatic-styles"))
    topic_style(
        styles,
        "root-topic",
        {
            qname(SVG_NS, "fill"): "#0F172A",
            qname(FO_NS, "color"): "#FFFFFF",
            qname(FO_NS, "font-size"): "24pt",
            qname(FO_NS, "font-weight"): "bold",
            "shape-class": "org.xmind.topicShape.roundedRect",
            "border-line-color": "#0F172A",
            "line-width": "3pt",
        },
    )
    for name, (accent, tint, dark) in COLORS.items():
        topic_style(
            styles,
            f"{name}-level1",
            {
                qname(SVG_NS, "fill"): accent,
                qname(FO_NS, "color"): "#FFFFFF",
                qname(FO_NS, "font-size"): "16pt",
                qname(FO_NS, "font-weight"): "bold",
                "shape-class": "org.xmind.topicShape.roundedRect",
                "border-line-color": accent,
                "line-color": accent,
                "line-width": "2pt",
            },
        )
        topic_style(
            styles,
            f"{name}-level2",
            {
                qname(SVG_NS, "fill"): tint,
                qname(FO_NS, "color"): dark,
                qname(FO_NS, "font-size"): "12pt",
                qname(FO_NS, "font-weight"): "bold",
                "shape-class": "org.xmind.topicShape.roundedRect",
                "border-line-color": accent,
                "line-color": accent,
                "line-width": "1pt",
            },
        )
        topic_style(
            styles,
            f"{name}-level3",
            {
                qname(FO_NS, "color"): "#334155",
                qname(FO_NS, "font-size"): "10pt",
                "shape-class": "org.xmind.topicShape.noBorder",
                "line-color": accent,
                "line-width": "1pt",
            },
        )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def build_manifest() -> bytes:
    ET.register_namespace("", MANIFEST_NS)
    root = ET.Element(qname(MANIFEST_NS, "manifest"))
    entries = [
        ("content.xml", "text/xml"),
        ("styles.xml", "text/xml"),
        ("meta.xml", "text/xml"),
    ]
    for path, media_type in entries:
        ET.SubElement(
            root,
            qname(MANIFEST_NS, "file-entry"),
            {"full-path": path, "media-type": media_type},
        )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def build_meta() -> bytes:
    ET.register_namespace("", META_NS)
    root = ET.Element(qname(META_NS, "xmap-meta"), {"version": "2.0"})
    creator = ET.SubElement(root, qname(META_NS, "Creator"))
    ET.SubElement(creator, qname(META_NS, "Name")).text = "Codex"
    ET.SubElement(creator, qname(META_NS, "Version")).text = "1.0"
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def main() -> None:
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as workbook:
        workbook.writestr("content.xml", build_content())
        workbook.writestr("styles.xml", build_styles())
        workbook.writestr("meta.xml", build_meta())
        workbook.writestr("META-INF/manifest.xml", build_manifest())
    print(OUTPUT)


if __name__ == "__main__":
    main()

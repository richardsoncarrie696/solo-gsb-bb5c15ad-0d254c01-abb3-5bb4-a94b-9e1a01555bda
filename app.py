"""编织说明逐行针数校验 —— Flask 后端。

POST /api/validate        单尺码校验
  请求: {"cast_on": 12, "pattern": "(k2tog yo)*6\np*12\n..."}
  响应: {
    "ok": true/false,
    "rows": [{"line", "instruction", "in", "consume", "produce", "out"}, ...],
    "error": null | {"line", "type": "parse"|"count"|"cast_on", "message",
                     "char"?, "available"?, "consume"?, "diff"?},
    "final": 全部通过时的最终针数
  }

POST /api/validate-sizes  多尺码校验（可附带线材用量估算）
  请求: {"sizes": [{"name": "S", "cast_on": 12}, ...], "pattern": "...",
         "yarn": {"k": 0.5, "p": 0.5, "yo": 0.2, "k2tog": 1.0,
                  "waste_percent": 10, "grams_per_ball": 50}}
  响应: {
    "ok": true/false,
    "sizes": [{"name", "cast_on", "ok", "rows", "error", "final", "yarn"?}, ...],
    "suggestion": null | {"line", "char", "old", "new", "instruction", "produces"}
  }
  提供 yarn 时，每行额外返回该尺码截至该行的累计克重 "weight"，尺码结果
  额外包含:
    "yarn": {"raw_total", "with_waste", "balls", "partial", "complete"}
  尺码列表或线材参数非法时:
    {"ok": false, "sizes": [], "error": {"type": "sizes"|"yarn", ...}}

POST /api/move-size       尺码上移/下移，并同步重排指令中的按尺码倍数
  请求: {"sizes": [...], "pattern": "...", "index": 0, "direction": "up"|"down"}
  成功: {"ok": true, "sizes": 重排后的尺码列表, "pattern": 重排后的指令原文}
    每行的 *{a|b|...} 按新尺码顺序重排（嵌套重复与同一行多处均处理），普通
    *n 与其他原文保持不变。
  失败: {"ok": false, "error": {"type": "sizes"|"move"|"reorder", ...}}
    任一处按尺码倍数项数或数值不合法时整次移动不生效，reorder 错误带原文
    行号 "line" 与字符位置 "char"（均从 1 计）。

POST /api/preview-row    单行针位预览（不展开重复项，可直接看十亿次重复尾段）
  请求: {"sizes": [...], "pattern": "...", "line": 1, "size_index": 0,
         "start": 1}
    line 为图解原文行号（1 起，空行计入行号），size_index 为尺码下标（0 起），
    start 为起始操作序号（1 起）。嵌套重复与按尺码倍数均按所选尺码定位，
    每一页最多返回 50 个实际针法，可凭 prev_start/next_start 前后翻页。
  成功: {"ok": true, "line", "instruction", "size", "size_index",
         "total", "start", "limit", "consume", "produce",
         "items": [{"seq", "stitch", "consume_before", "in_from",
                    "in_to", "out"}, ...],
         "prev_start", "next_start"}
    挂线等零入针针法的 in_from/in_to 为 null；非法行返回现有解析错误（原文
    行号与字符位置），不返回部分预览。
  失败: {"ok": false, "error": {"type": "sizes"|"line"|"start"|"size_index"
         |"parse", ...}}

POST /api/track-stitch   跨行针位追踪（不展开重复项）
  请求: {"sizes": [...], "pattern": "...", "size_index": 0,
         "needle": 1}
    needle 为第 1 行开始前所选尺码起针中的一枚针序号（1 起）。复用同一套
    解析与逐行校验规则：逐行解析（嵌套重复与 *{...} 按所选尺码算术定位），
    仅在该行消耗恰好等于当前可用针数时继续，定位这枚针被哪个针法消耗、
    该操作的入针范围与产出针位，并以产出针位作为下一行的入针序号；
    k2tog 标出与之合并的相邻针，yo 不消耗入针、只把之后的产出位置推后。
  成功: {"ok": true, "size", "size_index", "cast_on", "needle",
         "tracks": [{"line", "instruction", "in", "needle_in",
                     "stitch", "in_from", "in_to", "merged_with",
                     "yos_before", "seq", "out_needle",
                     "consume", "produce", "available_out"}, ...],
         "final_needle"}
    tracks 按原文行号只列有效行（空行计入行号但不列出）；针数不符或指令
    非法时停在首个错误行，tracks 保留此前轨迹，error 给出原文行号
    （解析错误另带字符位置 char）。
  失败: {"ok": false, "error": {"type": "sizes"|"size_index"|"needle"
         |"parse"|"count", ...}, "tracks"?: [...]}
    needle 超出所选尺码起针数时 type 为 "needle"（在解析任何行之前报错）。

POST /api/pattern-layout  多尺码对称花样排针
  请求: {"gauge": 22, "sizes": [{"name": "S", "target": 41}, ...],
         "edge": 2, "center": 6, "pattern_width": 8, "tolerance": 1}
    gauge 为每10厘米针数（正数）；sizes 按目标片幅（厘米，正数）从小到大
    排列；edge 为单侧边针数、center 为中央针数（非负整数）；
    pattern_width 为花样宽度（正整数，针）；tolerance 为允许宽差
    （厘米，非负）。每侧使用相同且至少一次的完整花样重复：
    起针数 = 2×边针 + 中央针 + 2×花样宽度×单侧重复数，
    实际片幅 = 起针数 × 10 ÷ 每10厘米针数。
  成功: {"ok": true, "base", "step", "total_deviation",
         "sizes": [{"index", "name", "target", "repeats", "cast_on",
                    "width", "deviation"}, ...]}
    为全部尺码选择严格递增的单侧重复数（repeats ≥ 1），各尺码实际片幅
    与目标差不超过允许宽差；在可行组合中最小化宽差绝对值之和
    （total_deviation），同分取按尺码顺序字典序最小的重复数组。
    寻优全程用分数精确计算，width/deviation/total_deviation 保留两位小数。
  无可行组合: {"ok": false, "error": {"type": "infeasible", "message"},
               "base", "step", "fail_index",
               "sizes": [{"index", "name", "target",
                          "min_repeats", "max_repeats"}, ...]}
    message 说明无法同时满足约束；sizes 给出各尺码在允许宽差内的可行
    重复数范围（min_repeats > max_repeats 表示该尺码单独即无可行重复）。
  参数非法: {"ok": false, "error": {"type": "params"|"sizes", "message"}}

POST /api/shaping-plan  对称减针行程（左右相同减针数的逐行安排）
  请求: {"cast_on": 70, "target": 40, "rows": 15, "max_decrease": 2}
    cast_on 为起针数、target 为目标针数（末行余针）、rows 为总行数
    （均为正整数）；max_decrease 为每个减针行单侧最多减针数（1 或 2）。
    逐行安排左右相同的减针数（每行单侧 0~max_decrease 针，0 为平织行），
    减针行之间至少隔一行平织，末行余针须等于目标针数。在满足约束的
    方案中最小化各行累计减针数与线性目标进度（D×行号/总行数）的平方
    偏差之和，同分取逐行单侧减针数组字典序最小的方案；求解由
    shaping_plan.solve_shaping 完成（动态规划，分数精确计算）。
  成功: {"ok": true, "cast_on", "target", "rows", "max_decrease",
         "total_decrease", "per_side", "decrease_rows", "cost",
         "plan": [{"row", "left", "right", "decrease", "decreased",
                   "remaining", "progress"}, ...]}
    cost 为最小平方偏差和（保留四位小数）；plan 逐行给出左右减针数、
    本行共减、截至本行累计减针（双侧）、行末余针与线性目标进度
    （progress 保留两位小数）。
  无解: {"ok": false, "error": {"type": "infeasible", "message"},
         "total_decrease", "max_decrease_rows", "max_total_decrease", ...}
    message 说明原因（目标针数比起针数多 / 差为奇数 / 行数不够），
    max_total_decrease 为约束下最多可减针数（双侧合计）。
  参数非法: {"ok": false, "error": {"type": "params", "message"}}

POST /api/stripe-schedule  条纹用线排程（连续异色条纹恰好覆盖总行数）
  请求: {"total_rows": 20,
         "colors": [{"name": "米白", "rows": 12}, {"name": "藏青", "rows": 10}],
         "min_len": 2, "max_len": 4, "preferred": 3}
    total_rows 为总行数（1~40 的整数）；colors 按输入顺序给出 2~3 种颜色，
    每个为 {"name", "rows"}：名称非空且互不重复，rows 为该色可编织行数
    （非负整数，即库存）；min_len/max_len 为最短、最长条纹行数（1~6 的
    整数且 min_len ≤ max_len）；preferred 为偏好段长（正数）。
  成功: {"ok": true, "total_rows", "preferred", "min_len", "max_len",
         "cost", "segment_count", "total_stock",
         "segments": [{"index", "start", "end", "color_index", "color",
                       "length"}, ...],
         "colors": [{"index", "name", "stock", "used", "remaining"}, ...]}
    每段长度在 [min_len, max_len] 内、相邻段异色、各色用量不超库存，且
    各段长度之和恰好等于 total_rows；在可行方案中最小化各段长度与偏好段长
    绝对差之和（cost，保留四位小数），同分按颜色输入顺序（颜色下标小者
    优先）及段长升序取段序列字典序最小的方案。start/end 为该段起止行
    （1 起，含两端）；求解由 stripe_schedule.solve_stripes 完成（动态规划，
    Fraction 精确计算）。
  无解: {"ok": false, "error": {"type": "infeasible", "message"}, ...}
    不返回任何部分安排；message 说明原因（可行段数区间无法容纳总行数 /
    库存合计不足 / 相邻异色与各色库存限制下无法恰好覆盖，后者另给出
    约束下最多可连续覆盖的行数）。
  参数非法: {"ok": false, "error": {"type": "params"|"colors", "message"}}

POST /api/seam-align     两片织物边缘缝合对位（逐步配对的行号对位表）
  请求: {"rows_a": 8, "rows_b": 7, "markers": [{"a": 3, "b": 2}, ...]}
    rows_a/rows_b 为 A、B 两侧行数（1~60 的整数）；markers 可省略或为空，
    每项为 {"a", "b"} 或 [a, b]，起终点自动视为 (0,0)、(rows_a,rows_b)，
    标记坐标必须是严格内部点且在两侧都严格递增。
    每次缝合前进 (1,1)、(1,2) 或 (2,1)（表示该步 A/B 两侧各吃的行数），
    路径须经过全部标记并恰好到终点；以每个标记区间内两侧累计进度比例
    （x/da 与 y/db）之差的平方和最小为目标，同分按整条步进序列
    (1,1)＜(1,2)＜(2,1) 的字典序取解；求解由 seam_align.solve_seam
    完成（动态规划，Fraction/整数精确计算）。
  成功: {"ok": true, "rows_a", "rows_b", "step_count", "cost",
         "markers": [{"index", "a", "b", "type"}, ...],
         "intervals": [{"index", "from_index", "to_index", "a_from",
                        "b_from", "a_to", "b_to", "a_rows", "b_rows",
                        "steps", "cost"}, ...],
         "steps": [{"seq", "interval", "move", "move_label", "move_a",
                    "move_b", "a_from", "a_to", "b_from", "b_to",
                    "a_pos", "b_pos", "progress_a", "progress_b",
                    "markers"}, ...]}
    markers 为含起终点（type 为 start/end/mark）的完整标记链；steps 给出
    逐步配对的行号范围（1 起含两端）、累计行号、区间内累计进度与经过的
    标记；cost/progress 保留四位小数。
  某区间无法衔接: {"ok": false, "error": {"type": "infeasible", "message"},
                   "interval_index", "from_index", "to_index", "a_from",
                   "b_from", "a_to", "b_to", "a_rows", "b_rows"}
    区间两侧行数之比超过 2，任何步进序列都无法衔接两端；指出该区间，
    响应不含 steps/intervals，不返回部分路线。
  参数非法: {"ok": false, "error": {"type": "params"|"markers", "message"}}

POST /api/board-layout  定型板排片（水平层排布，枚举分层与 90° 旋转）
  请求: {"board_width": 90, "board_height": 60, "gap": 3,
         "pieces": [{"name": "后片", "width": 40, "height": 32,
                     "rotate": false}, ...]}
    board_width/board_height 为定型板宽高（正整数厘米）；gap 为片间距
    （非负整数厘米，相邻片与相邻层之间都保留该间距）；pieces 为 2~6 片
    编织片，每片 {"name", "width", "height", "rotate"}：名称非空，宽高
    为正整数厘米，rotate 为是否允许旋转 90°（布尔）。
    按水平层排布：每层可放多片（层内按输入顺序自左向右、顶端对齐），
    层高取本层最大片高；相邻片、相邻层均保留片间距，所有片须完整落在
    板内。枚举全部有序分层与允许的 90° 旋转，求占用高度最小的完整
    方案；同高时取层数最少，再取各片所属层序号字典序最小、未旋转优先。
    求解由 board_layout.solve_board_layout 完成（整数精确计算）。
  成功: {"ok": true, "board_width", "board_height", "gap",
         "used_height", "layer_count",
         "layers": [{"index", "y", "height", "width", "pieces"}, ...],
         "pieces": [{"index", "name", "layer", "x", "y", "width",
                     "height", "rotated"}, ...]}
    x/y 为各片左上角坐标（板左上角为 (0,0)，x 向右、y 向下），
    width/height 为最终朝向下的尺寸，rotated 为是否已旋转 90°；
    used_height 为占用高度（各层层高之和 + 片间距×(层数−1)）。
  无解: {"ok": false, "error": {"type": "infeasible", "message"},
         "reason": "width"|"height"|"both", ...}
    不返回任何部分摆放。有片任何朝向都放不进时另带 "unfit_pieces"
    逐片诊断（width_ok/height_ok/min_width/min_height），message 说明
    板宽或板高不足；每片单独都能放进但最优排法仍超高时 reason 为
    "height"，另带 "min_height" 与 "layer_count"。
  参数非法: {"ok": false, "error": {"type": "params"|"pieces", "message"}}

逐行推算规则：每个尺码独立地以上一行的产出作为下一行的可用针数；某尺码
消耗与可用针数不一致（不足或超出）时，仅该尺码停止并记录行号与差额，
其余尺码继续推算。指令本身无法解析（含 *{a|b} 项数与尺码数不符、倍数
非法）时所有尺码一并停止，错误中给出原文行号与字符位置。每个尺码的
final 为最后一行有效推算后的针数（全部通过时即最终针数）。

线材用量按每个尺码每行各记号的实际出现次数（嵌套与按尺码重复均计入）
乘以单记号克重累计，全程十进制精确运算（Decimal，不用浮点）；遇针数错误
的尺码停止后续行，其用量为部分估算（partial=true）；语法错误同样导致全部
尺码的用量为部分估算。含损耗总量 = 原始总量 ×(1+waste_percent/100)，
线团数按未舍入的含损耗用量除以每团克重后严格向上取整（不减任何容差）；
逐行与汇总克重仅在输出时四舍五入保留两位小数。

倍数修正建议：某行可解析但至少一个尚在推算的尺码针数不符时，针对首个
这样的行逐一尝试“仅改该行一个现有的 *n 或 *{...} 倍数”（嵌套重复只按
算术推导，不展开）。建议行须让本行所有尚在推算的尺码消耗恰好等于各自
可用针数，倍数保持正整数，原本正确的尺码不受影响。候选按（改动的尺码
项数, 倍数变化总量, 原文位置）升序排列，首条放入响应顶层的 "suggestion"
（不改变原有结果字段）；无解或没有针数差额时 suggestion 为 null。
"""

import math
import os
import re
from decimal import Decimal, ROUND_HALF_UP, localcontext
from fractions import Fraction

from flask import Flask, jsonify, render_template, request

from board_layout import solve_board_layout
from pattern_layout import solve_layout
from seam_align import solve_seam
from shaping_plan import solve_shaping
from stripe_schedule import solve_stripes
from stitch_parser import (
    STITCH_NAMES,
    ParseError,
    PreviewStartError,
    StitchOutOfRangeError,
    locate_row_input,
    parse_row,
    parse_row_details,
    preview_row_stitches,
    reorder_size_multipliers,
    suggest_row_fix,
)

app = Flask(__name__)


def _parse_cast_on(raw):
    """校验起针数，返回 (数值, 错误消息)。只接受正整数。"""
    if isinstance(raw, bool):  # bool 是 int 的子类，需先排除
        return None, "起针数必须为正整数"
    if isinstance(raw, int):
        value = raw
    elif isinstance(raw, str):
        s = raw.strip()
        if not s.isdigit():
            return None, "起针数必须为正整数"
        value = int(s)
    else:
        return None, "起针数必须为正整数"
    if value <= 0:
        return None, "起针数必须为正整数（大于 0）"
    return value, None


def _parse_sizes(raw):
    """校验尺码列表，返回 ([{"name", "cast_on"}, ...], 错误消息)。"""
    if not isinstance(raw, list) or not raw:
        return None, "尺码列表不能为空"
    sizes = []
    for idx, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            return None, "第 {} 个尺码格式错误，应为 {{\"name\", \"cast_on\"}}".format(idx)
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            return None, "第 {} 个尺码的名称不能为空".format(idx)
        cast_on, err = _parse_cast_on(item.get("cast_on"))
        if err:
            return None, "尺码 {} 的起针数无效：{}".format(name.strip(), err)
        sizes.append({"name": name.strip(), "cast_on": cast_on})
    return sizes, None


# 线材参数字段 -> 中文标签
_YARN_FIELDS = {
    'k': '下针 k',
    'p': '上针 p',
    'yo': '挂线 yo',
    'k2tog': '两针并一针 k2tog',
    'waste_percent': '损耗百分比',
    'grams_per_ball': '每团克重',
}

_NUMBER_RE = re.compile(r'^[+-]?(\d+(?:\.\d*)?|\.\d+)$')


def _parse_decimal(raw, label, positive=False):
    """解析非负（positive=True 时必须严格为正）十进制数，返回 (Decimal, 错误消息)。

    接受数字或纯数字字符串，拒绝布尔值、指数记法（如 1e2）与无法解析的
    内容。十进制输入按字面转为 Decimal，线材参数解析、逐行克重累计、损耗
    与线团数计算全程不使用浮点。
    """
    if isinstance(raw, bool):
        return None, "{}必须为数值".format(label)
    if isinstance(raw, int):
        value = Decimal(raw)
    elif isinstance(raw, float):
        if not math.isfinite(raw):
            return None, "{}必须为数值".format(label)
        # 先经 str 再转 Decimal，按最短可读的十进制字面取值
        value = Decimal(str(raw))
    elif isinstance(raw, str) and _NUMBER_RE.match(raw.strip()):
        value = Decimal(raw.strip())
    else:
        return None, "{}必须为数值".format(label)
    if not value.is_finite() or value < 0:
        return None, "{}不能为负数".format(label)
    if positive and value <= 0:
        return None, "{}必须大于 0".format(label)
    return value, None


def _parse_yarn(raw):
    """校验线材用量参数，返回 (dict 或 None, 错误消息)。

    缺省（不传 yarn）时返回 (None, None)，表示不做用量估算。
    """
    if raw is None:
        return None, None
    if not isinstance(raw, dict):
        return None, "线材参数格式错误，应为对象 {\"k\", \"p\", ...}"
    yarn = {}
    for key in ('k', 'p', 'yo', 'k2tog', 'waste_percent'):
        if key not in raw:
            return None, "缺少{}参数".format(_YARN_FIELDS[key])
        value, err = _parse_decimal(raw[key], _YARN_FIELDS[key])
        if err:
            return None, err
        yarn[key] = value
    if 'grams_per_ball' not in raw:
        return None, "缺少{}参数".format(_YARN_FIELDS['grams_per_ball'])
    value, err = _parse_decimal(
        raw['grams_per_ball'], _YARN_FIELDS['grams_per_ball'], positive=True)
    if err:
        return None, err
    yarn['grams_per_ball'] = value
    return yarn, None


def _parse_fraction(raw, label, positive=False):
    """解析非负（positive=True 时必须严格为正）数值为精确分数。

    接受数字或纯数字字符串，拒绝布尔值、指数记法与无法解析的内容。
    十进制输入按字面经 Decimal 转为 Fraction，宽差比较全程不用浮点。
    """
    if isinstance(raw, bool):
        return None, "{}必须为数值".format(label)
    if isinstance(raw, int):
        value = Fraction(raw)
    elif isinstance(raw, float):
        if not math.isfinite(raw):
            return None, "{}必须为数值".format(label)
        value = Fraction(Decimal(str(raw)))
    elif isinstance(raw, str) and _NUMBER_RE.match(raw.strip()):
        value = Fraction(Decimal(raw.strip()))
    else:
        return None, "{}必须为数值".format(label)
    if value < 0:
        return None, "{}不能为负数".format(label)
    if positive and value <= 0:
        return None, "{}必须大于 0".format(label)
    return value, None


def _parse_nonneg_int(raw, label, positive=False):
    """校验非负整数（positive=True 时必须为正整数），返回 (数值, 错误消息)。"""
    if isinstance(raw, bool):  # bool 是 int 的子类，需先排除
        return None, "{}必须为整数".format(label)
    if isinstance(raw, int):
        value = raw
    elif isinstance(raw, str):
        s = raw.strip()
        if not s.isdigit():
            return None, "{}必须为整数".format(label)
        value = int(s)
    else:
        return None, "{}必须为整数".format(label)
    if value < 0:
        return None, "{}不能为负数".format(label)
    if positive and value <= 0:
        return None, "{}必须大于 0".format(label)
    return value, None


def _parse_layout_sizes(raw):
    """校验排针尺码列表，返回 ([{"name", "target"}], 错误消息)。

    每个尺码为 {"name", "target"}：target 为目标片幅（厘米，正数，精确
    分数）；各尺码目标片幅必须按从小到大排列（单调不减）。
    """
    if not isinstance(raw, list) or not raw:
        return None, "尺码列表不能为空"
    sizes = []
    for idx, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            return None, "第 {} 个尺码格式错误，应为 {{\"name\", \"target\"}}".format(idx)
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            return None, "第 {} 个尺码的名称不能为空".format(idx)
        target, err = _parse_fraction(
            item.get("target"),
            "尺码 {} 的目标片幅".format(name.strip()), positive=True)
        if err:
            return None, err
        sizes.append({"name": name.strip(), "target": target})
    for i in range(1, len(sizes)):
        if sizes[i]["target"] < sizes[i - 1]["target"]:
            return None, "各尺码目标片幅需按从小到大排列：{}（{}）小于 {}（{}）".format(
                sizes[i]["name"], sizes[i]["target"],
                sizes[i - 1]["name"], sizes[i - 1]["target"])
    return sizes, None


def _cm(frac):
    """精确分数转厘米显示值（保留两位小数）。"""
    return round(float(frac), 2)


def _grams(value):
    """精确 Decimal 克重转显示值：仅在输出时四舍五入保留两位小数。"""
    return float(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def _parse_stripe_colors(raw):
    """校验条纹颜色列表，返回 ([{"name", "rows"}], 错误消息)。

    需要恰好 2~3 种颜色，按输入顺序保留；名称非空且互不重复，rows 为该色
    可编织行数（非负整数，即库存）。
    """
    if not isinstance(raw, list):
        return None, "颜色列表应为 2~3 个 {\"name\", \"rows\"} 对象"
    if not (2 <= len(raw) <= 3):
        return None, "需要填写 2~3 种颜色（当前 {} 种）".format(len(raw))
    colors = []
    seen = set()
    for idx, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            return None, "第 {} 个颜色格式错误，应为 {{\"name\", \"rows\"}}".format(idx)
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            return None, "第 {} 个颜色的名称不能为空".format(idx)
        name = name.strip()
        if name in seen:
            return None, "颜色名称重复：{}（相邻段异色与同分排序都按颜色区分）".format(name)
        rows, err = _parse_nonneg_int(item.get("rows"), "颜色 {} 的可编织行数".format(name))
        if err:
            return None, err
        seen.add(name)
        colors.append({"name": name, "rows": rows})
    return colors, None


def _parse_seam_markers(raw, rows_a, rows_b):
    """校验缝合对位标记对列表，返回 ([[a, b], ...], 错误消息)。

    起终点自动视为 (0,0) 与 (rows_a, rows_b)，无需也不允许在列表中重复；
    每个标记为 {"a", "b"} 或 [a, b]，坐标须为 1~rows_a-1 / 1~rows_b-1 的
    整数（即严格内部点），且所有标记在两侧都严格递增（后一个的 a、b 都
    大于前一个）。
    """
    if raw is None:
        return [], None
    if not isinstance(raw, list):
        return None, "标记对应为列表，每项写成 {\"a\", \"b\"} 或 [a, b]"
    markers = []
    prev_a = 0
    prev_b = 0
    for idx, item in enumerate(raw, 1):
        if isinstance(item, dict):
            raw_a, raw_b = item.get("a"), item.get("b")
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            raw_a, raw_b = item
        else:
            return None, "第 {} 个标记格式错误，应为 {{\"a\", \"b\"}} 或 [a, b]".format(idx)
        a, err = _parse_nonneg_int(raw_a, "第 {} 个标记的 A 侧行号".format(idx), positive=True)
        if err:
            return None, err
        b, err = _parse_nonneg_int(raw_b, "第 {} 个标记的 B 侧行号".format(idx), positive=True)
        if err:
            return None, err
        if not (a < rows_a and b < rows_b):
            return None, (
                "第 {} 个标记 ({},{}) 不是内部点：标记必须严格位于两侧行数之内"
                "（A 侧 1~{}，B 侧 1~{}）；起点 (0,0) 与终点 ({},{}) 无需填写"
                .format(idx, a, b, rows_a - 1, rows_b - 1, rows_a, rows_b))
        if a <= prev_a or b <= prev_b:
            if a == prev_a or b == prev_b:
                reason = "与上一个标记 ({},{}) 有一侧行号相同".format(prev_a, prev_b)
            else:
                reason = "相对上一个标记 ({},{}) 不是同时增大".format(prev_a, prev_b)
            return None, (
                "第 {} 个标记 ({},{}) 在两侧未严格递增：{}，标记必须按 A、B "
                "两侧行号都增大的顺序填写".format(idx, a, b, reason))
        markers.append([a, b])
        prev_a, prev_b = a, b
    return markers, None


def _parse_board_pieces(raw):
    """校验编织片列表，返回 ([{"name", "width", "height", "rotate"}], 错误消息)。

    需要 2~6 片，每片为 {"name", "width", "height", "rotate"}：名称非空，
    宽高为正整数（厘米），rotate 为是否允许旋转 90°（布尔）。
    """
    if not isinstance(raw, list):
        return None, "编织片列表应为 2~6 个 {\"name\", \"width\", \"height\", \"rotate\"} 对象"
    if not (2 <= len(raw) <= 6):
        return None, "需要填写 2~6 片编织片（当前 {} 片）".format(len(raw))
    pieces = []
    for idx, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            return None, "第 {} 片格式错误，应为 {{\"name\", \"width\", \"height\", \"rotate\"}}".format(idx)
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            return None, "第 {} 片的名称不能为空".format(idx)
        name = name.strip()
        width, err = _parse_nonneg_int(
            item.get("width"), "编织片 {} 的宽".format(name), positive=True)
        if err:
            return None, err
        height, err = _parse_nonneg_int(
            item.get("height"), "编织片 {} 的高".format(name), positive=True)
        if err:
            return None, err
        rotate = item.get("rotate")
        if not isinstance(rotate, bool):
            return None, "编织片 {} 的是否允许旋转必须为 true 或 false".format(name)
        pieces.append({"name": name, "width": width, "height": height,
                       "rotate": rotate})
    return pieces, None


def _parse_error_obj(lineno, text, exc):
    """构造解析错误对象，附带原文行号与字符位置（1 起）。"""
    err = {
        "line": lineno,
        "type": "parse",
        "instruction": text,
        "message": str(exc),
    }
    if getattr(exc, "pos", None) is not None:
        err["char"] = exc.pos + 1
    return err


def _count_error_obj(lineno, text, available, consume):
    """构造针数差额错误对象。"""
    diff = consume - available
    if diff > 0:
        message = "需要消耗 {} 针，但仅有 {} 针可用，缺少 {} 针".format(
            consume, available, diff)
    else:
        message = "只消耗了 {} 针，可用的 {} 针还剩 {} 针未使用".format(
            consume, available, -diff)
    return {
        "line": lineno,
        "type": "count",
        "instruction": text,
        "available": available,
        "consume": consume,
        "diff": diff,
        "message": message,
    }


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/validate")
def validate():
    data = request.get_json(silent=True) or {}

    cast_on, err = _parse_cast_on(data.get("cast_on"))
    if err:
        return jsonify({
            "ok": False,
            "rows": [],
            "error": {"line": None, "type": "cast_on", "message": err},
        })

    pattern = data.get("pattern", "")
    if not isinstance(pattern, str):
        pattern = str(pattern)

    rows = []
    error = None
    available = cast_on
    for lineno, raw_line in enumerate(pattern.splitlines(), 1):
        text = raw_line.strip()
        if not text:  # 跳过空行，行号仍按原始文本计算
            continue
        try:
            consume, produce = parse_row(text)
        except ParseError as exc:
            error = _parse_error_obj(lineno, text, exc)
            break
        if consume != available:
            error = _count_error_obj(lineno, text, available, consume)
            break
        rows.append({
            "line": lineno,
            "instruction": text,
            "in": available,
            "consume": consume,
            "produce": produce,
            "out": produce,
        })
        available = produce

    result = {"ok": error is None, "rows": rows, "error": error}
    if error is None:
        result["final"] = available
    return jsonify(result)


@app.post("/api/validate-sizes")
def validate_sizes():
    data = request.get_json(silent=True) or {}

    sizes, err = _parse_sizes(data.get("sizes"))
    if err:
        return jsonify({
            "ok": False,
            "sizes": [],
            "error": {"line": None, "type": "sizes", "message": err},
        })

    yarn, err = _parse_yarn(data.get("yarn"))
    if err:
        return jsonify({
            "ok": False,
            "sizes": [],
            "error": {"line": None, "type": "yarn", "message": err},
        })

    pattern = data.get("pattern", "")
    if not isinstance(pattern, str):
        pattern = str(pattern)

    num_sizes = len(sizes)
    states = [{
        "name": s["name"],
        "cast_on": s["cast_on"],
        "available": s["cast_on"],
        "rows": [],
        "error": None,
        "active": True,
        "raw_weight": Decimal(0) if yarn is not None else None,
    } for s in sizes]

    first_count_error = None  # (行号, 原文, 各尺码可用针数)：首个针数差额行
    # 逐行克重累计全程用十进制精确运算：提高上下文精度避免长链累计被截断，
    # 逐行与汇总克重仅在输出时保留两位小数。
    with localcontext() as ctx:
        ctx.prec = 50
        for lineno, raw_line in enumerate(pattern.splitlines(), 1):
            if not any(st["active"] for st in states):
                break  # 所有尺码都已停止，后续行不再推算
            text = raw_line.strip()
            if not text:  # 跳过空行，行号仍按原始文本计算
                continue
            try:
                consumes, produces, tallies = parse_row_details(text, num_sizes)
            except ParseError as exc:
                # 指令非法时任何尺码都无法继续，全部停止并记录同一错误
                error = _parse_error_obj(lineno, text, exc)
                for st in states:
                    if st["active"]:
                        st["error"] = error
                        st["active"] = False
                break
            if first_count_error is None and any(
                    st["active"] and consumes[i] != st["available"]
                    for i, st in enumerate(states)):
                # 记录首个针数差额行的现场，供事后推导倍数修正建议
                first_count_error = (lineno, text, [
                    st["available"] if st["active"] else None for st in states])
            for i, st in enumerate(states):
                if not st["active"]:
                    continue
                consume, produce = consumes[i], produces[i]
                if consume != st["available"]:
                    # 仅停止该尺码，其余尺码继续推算
                    st["error"] = _count_error_obj(lineno, text, st["available"], consume)
                    st["active"] = False
                    continue
                row = {
                    "line": lineno,
                    "instruction": text,
                    "in": st["available"],
                    "consume": consume,
                    "produce": produce,
                    "out": produce,
                }
                if yarn is not None:
                    # 按该尺码本行各记号的实际次数累计原始克重（含嵌套/按尺码重复）
                    st["raw_weight"] += sum(
                        (Decimal(tallies[name][i]) * yarn[name]
                         for name in STITCH_NAMES), Decimal(0))
                    row["weight"] = _grams(st["raw_weight"])
                st["rows"].append(row)
                st["available"] = produce

    suggestion = None
    if first_count_error is not None:
        err_line, err_text, availables = first_count_error
        fix = suggest_row_fix(err_text, availables)
        if fix is not None:
            suggestion = {
                "line": err_line,
                "char": fix["char"],
                "old": fix["old"],
                "new": fix["new"],
                "instruction": fix["instruction"],
                "produces": fix["produces"],
            }

    result_sizes = []
    for st in states:
        result = {
            "name": st["name"],
            "cast_on": st["cast_on"],
            "ok": st["error"] is None,
            "rows": st["rows"],
            "error": st["error"],
            "final": st["available"],
        }
        if yarn is not None:
            result["yarn"] = _yarn_summary(yarn, st)
        result_sizes.append(result)
    return jsonify({
        "ok": all(s["ok"] for s in result_sizes),
        "sizes": result_sizes,
        "suggestion": suggestion,
    })


@app.post("/api/move-size")
def move_size():
    """尺码上移/下移，并同步重排指令中所有 *{...} 的倍数项。

    请求: {"sizes": [...], "pattern": "...", "index": 0, "direction": "up"|"down"}
    成功: {"ok": true, "sizes": 重排后的尺码列表, "pattern": 重排后的指令原文}
    失败: {"ok": false, "error": {"type": "sizes"|"move"|"reorder", ...}}
      reorder 错误带 "line"（原文行号）与 "char"（字符位置，均从 1 计）；
      此时尺码列表与指令均不改动，整次移动不生效。
    """
    data = request.get_json(silent=True) or {}

    sizes, err = _parse_sizes(data.get("sizes"))
    if err:
        return jsonify({
            "ok": False,
            "error": {"line": None, "type": "sizes", "message": err},
        })

    index = data.get("index")
    direction = data.get("direction")
    if isinstance(index, bool) or not isinstance(index, int):
        return jsonify({
            "ok": False,
            "error": {"line": None, "type": "move", "message": "缺少要移动的尺码位置"},
        })
    if direction not in ("up", "down"):
        return jsonify({
            "ok": False,
            "error": {"line": None, "type": "move", "message": "移动方向必须是 up 或 down"},
        })

    target = index - 1 if direction == "up" else index + 1
    if not (0 <= index < len(sizes)) or not (0 <= target < len(sizes)):
        return jsonify({
            "ok": False,
            "error": {"line": None, "type": "move",
                      "message": "该尺码已在边界，无法继续{}".format(
                          "上移" if direction == "up" else "下移")},
        })

    pattern = data.get("pattern", "")
    if not isinstance(pattern, str):
        pattern = str(pattern)

    num_sizes = len(sizes)
    order = list(range(num_sizes))
    order[index], order[target] = order[target], order[index]

    line_ends = [(m.start(), m.end()) for m in re.finditer(r'\r\n|\r|\n', pattern)]
    line_starts = [0] + [end for _start, end in line_ends]

    new_lines = []
    for lineno, start in enumerate(line_starts, 1):
        end = line_ends[lineno - 1][0] if lineno - 1 < len(line_ends) else len(pattern)
        line_text = pattern[start:end]
        try:
            new_lines.append(reorder_size_multipliers(line_text, order))
        except ParseError as exc:
            error = {
                "line": lineno,
                "type": "reorder",
                "message": str(exc),
            }
            if getattr(exc, "pos", None) is not None:
                error["char"] = exc.pos + 1
            return jsonify({"ok": False, "error": error})

    # 逐行重排后用原换行符拼回，保留原文其余字节不变
    rebuilt = []
    for lineno, new_text in enumerate(new_lines):
        rebuilt.append(new_text)
        if lineno < len(line_ends):
            ls, le = line_ends[lineno]
            rebuilt.append(pattern[ls:le])
    new_pattern = "".join(rebuilt)

    new_sizes = [None] * num_sizes
    for new_idx, old_idx in enumerate(order):
        new_sizes[new_idx] = sizes[old_idx]
    return jsonify({"ok": True, "sizes": new_sizes, "pattern": new_pattern})


@app.post("/api/preview-row")
def preview_row():
    """单行针位预览：按图解原文行、尺码与起始操作序号返回一页实际针法。

    沿用多尺码校验的 sizes/pattern 输入与同一套解析语法：非法行返回现有
    解析错误（原文行号 "line" 与字符位置 "char"，均从 1 计），不返回部分
    预览。每页最多 50 个针法，响应中的 prev_start/next_start 供前后翻页；
    嵌套重复与按尺码倍数按所选尺码算术定位、跳过未显示的重复段，不展开
    整行，十亿次重复也能直接查看尾段。
    """
    data = request.get_json(silent=True) or {}

    sizes, err = _parse_sizes(data.get("sizes"))
    if err:
        return jsonify({
            "ok": False,
            "error": {"line": None, "type": "sizes", "message": err},
        })

    pattern = data.get("pattern", "")
    if not isinstance(pattern, str):
        pattern = str(pattern)

    raw_lines = pattern.splitlines()
    line = data.get("line")
    if isinstance(line, bool) or not isinstance(line, int) \
            or not (1 <= line <= len(raw_lines)):
        return jsonify({
            "ok": False,
            "error": {"line": None, "type": "line",
                      "message": "图解原文行号必须在 1~{} 之间".format(
                          max(len(raw_lines), 1))},
        })
    text = raw_lines[line - 1].strip()
    if not text:
        return jsonify({
            "ok": False,
            "error": {"line": line, "type": "line",
                      "message": "第 {} 行为空行，没有可预览的指令".format(line)},
        })

    num_sizes = len(sizes)
    size_index = data.get("size_index", 0)
    if isinstance(size_index, bool) or not isinstance(size_index, int) \
            or not (0 <= size_index < num_sizes):
        return jsonify({
            "ok": False,
            "error": {"line": line, "type": "size_index",
                      "message": "尺码下标必须在 0~{} 之间".format(num_sizes - 1)},
        })

    start = data.get("start", 1)
    if isinstance(start, bool) or not isinstance(start, int) or start < 1:
        return jsonify({
            "ok": False,
            "error": {"line": line, "type": "start",
                      "message": "起始操作序号必须为正整数"},
        })

    try:
        preview = preview_row_stitches(text, num_sizes, size_index, start)
    except PreviewStartError as exc:
        return jsonify({
            "ok": False,
            "error": {"line": line, "type": "start", "total": exc.total,
                      "message": str(exc)},
        })
    except ParseError as exc:
        # 与校验接口完全一致的语法错误对象（同一原文行号与字符位置）
        return jsonify({"ok": False, "error": _parse_error_obj(line, text, exc)})

    size = sizes[size_index]
    return jsonify({
        "ok": True,
        "line": line,
        "instruction": text,
        "size": size["name"],
        "size_index": size_index,
        "cast_on": size["cast_on"],
        "total": preview["total"],
        "start": preview["start"],
        "limit": preview["limit"],
        "consume": preview["consume"],
        "produce": preview["produce"],
        "items": preview["items"],
        "prev_start": preview["prev_start"],
        "next_start": preview["next_start"],
    })


@app.post("/api/track-stitch")
def track_stitch():
    """跨行针位追踪：按尺码与一枚起针序号，逐行列出它被哪种针法消耗。

    复用与 /api/validate-sizes 完全相同的解析与逐行校验规则：每行先按所选
    尺码解析（嵌套重复与 *{...} 由 stitch_parser 算术定位、绝不展开），只有
    该行消耗恰好等于当前可用针数时才把该枚针定位到具体针法，并把其产出针位
    作为下一行的入针序号。针数不符（type 为 count）或任一行语法错误（type
    为 parse，带 char）时停在首个错误行，tracks 保留此前各有效行轨迹。
    """
    data = request.get_json(silent=True) or {}

    sizes, err = _parse_sizes(data.get("sizes"))
    if err:
        return jsonify({
            "ok": False,
            "error": {"line": None, "type": "sizes", "message": err},
        })

    num_sizes = len(sizes)
    size_index = data.get("size_index", 0)
    if isinstance(size_index, bool) or not isinstance(size_index, int) \
            or not (0 <= size_index < num_sizes):
        return jsonify({
            "ok": False,
            "error": {"line": None, "type": "size_index",
                      "message": "尺码下标必须在 0~{} 之间".format(num_sizes - 1)},
        })

    needle, err = _parse_cast_on(data.get("needle"))
    if err:
        return jsonify({
            "ok": False,
            "error": {"line": None, "type": "needle",
                      "message": "起针序号必须为正整数"},
        })

    size = sizes[size_index]
    cast_on = size["cast_on"]
    if needle > cast_on:
        return jsonify({
            "ok": False,
            "error": {
                "line": None,
                "type": "needle",
                "cast_on": cast_on,
                "needle": needle,
                "message": "起针序号越界：尺码 {} 起针 {} 针，序号必须在 1~{} 之间".format(
                    size["name"], cast_on, cast_on),
            },
        })

    pattern = data.get("pattern", "")
    if not isinstance(pattern, str):
        pattern = str(pattern)

    tracks = []
    error = None
    available = cast_on   # 当前行开始前的可用（入针）针数
    current = needle      # 被追踪的针在当前入针序列中的序号
    for lineno, raw_line in enumerate(pattern.splitlines(), 1):
        text = raw_line.strip()
        if not text:  # 空行计入行号但不是有效行，跳过且不消耗针
            continue
        try:
            located = locate_row_input(text, num_sizes, size_index, current)
        except ParseError as exc:
            # 与校验接口完全一致的语法错误对象（同一原文行号与字符位置）
            error = _parse_error_obj(lineno, text, exc)
            break
        except StitchOutOfRangeError as exc:
            # 理论上只在“消耗 < 可用”时发生（current 落在未使用针上）；
            # “消耗 > 可用”会先在下面的针数校验处停止。统一按针数差额报错。
            error = _count_error_obj(lineno, text, available, exc.consume)
            break
        consume = located["consume"]
        produce = located["produce"]
        if consume != available:
            error = _count_error_obj(lineno, text, available, consume)
            break
        stitch = located["stitch"]
        in_from = located["in_from"]
        in_to = located["in_to"]
        # 每个针法（含 yo）恰好产出 1 针，产出按操作先后编号，故出针序号
        # 等于该针法在整行实际针法序列中的操作序号（与单行预览一致）；
        # yo 不消耗入针，却占一个出针序号，因而会把之后的产出位置推后。
        out_needle = located["seq"]
        # k2tog 与相邻针合并：标明被并入的另一枚针（追踪的可能是范围任一端）；
        # k/p 无合并，为 None
        if stitch == "k2tog":
            merged_with = in_to if current == in_from else in_from
        else:
            merged_with = None
        tracks.append({
            "line": lineno,
            "instruction": text,
            "in": available,
            "needle_in": current,
            "stitch": stitch,
            "in_from": in_from,
            "in_to": in_to,
            "merged_with": merged_with,
            "yos_before": located["yos_before"],
            "seq": located["seq"],
            "out_needle": out_needle,
            "consume": consume,
            "produce": produce,
            "available_out": produce,
        })
        current = out_needle
        available = produce

    result = {
        "ok": error is None,
        "size": size["name"],
        "size_index": size_index,
        "cast_on": cast_on,
        "needle": needle,
        "tracks": tracks,
        "error": error,
    }
    if error is None:
        result["final_needle"] = current
    return jsonify(result)


@app.post("/api/pattern-layout")
def pattern_layout():
    """多尺码对称花样排针：为全部尺码选择严格递增的单侧花样重复数。

    每侧使用相同且至少一次的完整花样重复：
      起针数 = 2×边针 + 中央针 + 2×花样宽度×单侧重复数
      实际片幅 = 起针数 × 10 ÷ 每10厘米针数
    各尺码实际片幅与目标片幅之差不得超过允许宽差；在可行组合中最小化
    宽差绝对值之和，同分取按尺码顺序字典序最小的重复数组。求解由
    pattern_layout.solve_layout 完成，全程分数精确计算。
    """
    data = request.get_json(silent=True) or {}

    gauge, err = _parse_fraction(data.get("gauge"), "每10厘米针数", positive=True)
    if err:
        return jsonify({"ok": False, "error": {"type": "params", "message": err}})

    edge, err = _parse_nonneg_int(data.get("edge"), "单侧边针数")
    if err:
        return jsonify({"ok": False, "error": {"type": "params", "message": err}})

    center, err = _parse_nonneg_int(data.get("center"), "中央针数")
    if err:
        return jsonify({"ok": False, "error": {"type": "params", "message": err}})

    pattern_width, err = _parse_nonneg_int(
        data.get("pattern_width"), "花样宽度", positive=True)
    if err:
        return jsonify({"ok": False, "error": {"type": "params", "message": err}})

    tolerance, err = _parse_fraction(data.get("tolerance"), "允许宽差")
    if err:
        return jsonify({"ok": False, "error": {"type": "params", "message": err}})

    sizes, err = _parse_layout_sizes(data.get("sizes"))
    if err:
        return jsonify({"ok": False, "error": {"type": "sizes", "message": err}})

    result = solve_layout(
        gauge, [s["target"] for s in sizes],
        edge, center, pattern_width, tolerance)

    if not result["ok"]:
        fail = result["fail_index"]
        lo, hi = result["ranges"][fail]
        if lo > hi:
            message = (
                "无法同时满足约束：尺码 {} 在允许宽差内没有任何可行的单侧重复数"
                "（任何不小于 1 的重复数换算的片幅都超出允许宽差）".format(
                    sizes[fail]["name"]))
        else:
            message = (
                "无法同时满足约束：尺码 {} 在允许宽差内单侧重复数只能取 {}~{}，"
                "但为满足各尺码严格递增，它至少需要取 {}".format(
                    sizes[fail]["name"], lo, hi, result["fail_need"]))
        return jsonify({
            "ok": False,
            "error": {"type": "infeasible", "message": message},
            "base": result["base"],
            "step": result["step"],
            "fail_index": fail,
            "sizes": [{
                "index": i,
                "name": s["name"],
                "target": _cm(s["target"]),
                "min_repeats": result["ranges"][i][0],
                "max_repeats": result["ranges"][i][1],
            } for i, s in enumerate(sizes)],
        })

    return jsonify({
        "ok": True,
        "base": result["base"],
        "step": result["step"],
        "total_deviation": _cm(result["total_deviation"]),
        "sizes": [{
            "index": i,
            "name": sizes[i]["name"],
            "target": _cm(sizes[i]["target"]),
            "repeats": s["repeats"],
            "cast_on": s["cast_on"],
            "width": _cm(s["width"]),
            "deviation": _cm(s["deviation"]),
        } for i, s in enumerate(result["sizes"])],
    })


@app.post("/api/shaping-plan")
def shaping_plan():
    """对称减针行程：逐行安排左右相同的减针数，末行余针恰好等于目标针数。

    每行单侧减 0~max_decrease 针（0 为平织行），左右两侧减针数相同；
    减针行之间至少隔一行平织。在满足约束的方案中最小化各行累计减针数
    与线性目标进度（总减针数×行号/总行数）的平方偏差之和，同分取逐行
    单侧减针数组字典序最小的方案。求解由 shaping_plan.solve_shaping
    完成（动态规划，分数精确计算）。
    """
    data = request.get_json(silent=True) or {}

    cast_on, err = _parse_cast_on(data.get("cast_on"))
    if err:
        return jsonify({"ok": False, "error": {"type": "params", "message": err}})

    target, err = _parse_nonneg_int(data.get("target"), "目标针数", positive=True)
    if err:
        return jsonify({"ok": False, "error": {"type": "params", "message": err}})

    rows, err = _parse_nonneg_int(data.get("rows"), "总行数", positive=True)
    if err:
        return jsonify({"ok": False, "error": {"type": "params", "message": err}})

    max_decrease, err = _parse_nonneg_int(
        data.get("max_decrease"), "每个减针行单侧最多减针数")
    if err:
        return jsonify({"ok": False, "error": {"type": "params", "message": err}})
    if max_decrease not in (1, 2):
        return jsonify({
            "ok": False,
            "error": {"type": "params",
                      "message": "每个减针行单侧最多减针数必须为 1 或 2"},
        })

    result = solve_shaping(cast_on, target, rows, max_decrease)

    if not result["ok"]:
        total = result["total_decrease"]
        max_total = result["max_total_decrease"]
        max_rows = result["max_decrease_rows"]
        reason = result["reason"]
        if reason == "target_exceeds":
            message = (
                "目标针数 {} 大于起针数 {}：对称减针行程只能减针、无法加针；"
                "按当前行数与减针上限，最多可减 {} 针".format(
                    target, cast_on, max_total))
        elif reason == "odd_decrease":
            message = (
                "起针数与目标针数相差 {} 针（奇数）：左右对称减针每次共减"
                "偶数针，无法恰好减到目标针数；按当前行数与减针上限，"
                "最多可减 {} 针".format(total, max_total))
        else:
            message = (
                "需要共减 {} 针（单侧 {} 针），但 {} 行内减针行两两至少隔"
                "一行平织，最多 {} 个减针行、每行单侧最多 {} 针，最多可减 "
                "{} 针，还差 {} 针".format(
                    total, total // 2, rows, max_rows, max_decrease,
                    max_total, total - max_total))
        return jsonify({
            "ok": False,
            "error": {"type": "infeasible", "message": message},
            "cast_on": cast_on,
            "target": target,
            "rows": rows,
            "max_decrease": max_decrease,
            "total_decrease": total,
            "max_decrease_rows": max_rows,
            "max_total_decrease": max_total,
        })

    return jsonify({
        "ok": True,
        "cast_on": cast_on,
        "target": target,
        "rows": rows,
        "max_decrease": max_decrease,
        "total_decrease": result["total_decrease"],
        "per_side": result["per_side"],
        "decrease_rows": result["decrease_rows"],
        "cost": round(float(result["cost"]), 4),
        "plan": [{
            "row": p["row"],
            "left": p["left"],
            "right": p["right"],
            "decrease": p["decrease"],
            "decreased": p["decreased"],
            "remaining": p["remaining"],
            "progress": round(float(p["progress"]), 2),
        } for p in result["plan"]],
    })


@app.post("/api/stripe-schedule")
def stripe_schedule():
    """条纹用线排程：连续异色条纹恰好覆盖总行数，最小化段长与偏好段长的
    绝对差之和。

    每段长度在最短~最长（1~6）之间，相邻段颜色不同，各色累计用量不超过
    其库存；同分按颜色输入顺序及段长升序取段序列字典序最小的方案。求解
    由 stripe_schedule.solve_stripes 完成（动态规划，Fraction 精确计算），
    无解时只报错、不返回任何部分安排。
    """
    data = request.get_json(silent=True) or {}

    total_rows, err = _parse_nonneg_int(data.get("total_rows"), "总行数", positive=True)
    if err:
        return jsonify({"ok": False, "error": {"type": "params", "message": err}})
    if not (1 <= total_rows <= 40):
        return jsonify({
            "ok": False,
            "error": {"type": "params", "message": "总行数必须在 1~40 之间"},
        })

    colors, err = _parse_stripe_colors(data.get("colors"))
    if err:
        return jsonify({"ok": False, "error": {"type": "colors", "message": err}})

    min_len, err = _parse_nonneg_int(data.get("min_len"), "最短条纹行数", positive=True)
    if err:
        return jsonify({"ok": False, "error": {"type": "params", "message": err}})
    max_len, err = _parse_nonneg_int(data.get("max_len"), "最长条纹行数", positive=True)
    if err:
        return jsonify({"ok": False, "error": {"type": "params", "message": err}})
    if not (1 <= min_len <= 6 and 1 <= max_len <= 6):
        return jsonify({
            "ok": False,
            "error": {"type": "params", "message": "最短与最长条纹行数必须在 1~6 之间"},
        })
    if min_len > max_len:
        return jsonify({
            "ok": False,
            "error": {"type": "params",
                      "message": "最短条纹行数不能大于最长条纹行数"},
        })

    preferred, err = _parse_fraction(data.get("preferred"), "偏好段长", positive=True)
    if err:
        return jsonify({"ok": False, "error": {"type": "params", "message": err}})

    stocks = [c["rows"] for c in colors]
    result = solve_stripes(total_rows, stocks, min_len, max_len, preferred)

    if not result["ok"]:
        reason = result["reason"]
        total_stock = result["total_stock"]
        if reason == "length_range":
            if result["segment_count_max"] == 0:
                message = (
                    "无法排程：总行数 {} 小于最短条纹行数 {}，连一段都放不下".format(
                        total_rows, min_len))
            else:
                message = (
                    "无法排程：每段长度限定在 {}~{} 行，k 段能覆盖的总行数只能是"
                    " {}×k~{}×k；总行数 {} 不在任何整数段数的可覆盖区间内"
                    "（可行段数需满足 {} ≤ k ≤ {}，该范围为空）".format(
                        min_len, max_len, min_len, max_len, total_rows,
                        result["segment_count_min"], result["segment_count_max"]))
        elif reason == "stock_shortage":
            message = (
                "无法排程：{} 种颜色库存合计仅 {} 行，少于需要覆盖的总行数 {}，"
                "还差 {} 行".format(len(colors), total_stock, total_rows,
                                    total_rows - total_stock))
        else:
            message = (
                "无法排程：在每段 {}~{} 行、相邻段异色、各色用量不超库存的条件下，"
                "没有恰好覆盖 {} 行的连续安排（不返回部分安排）；放松约束后最多可"
                "连续覆盖 {} 行，可尝试放宽条纹长度区间、增加库存或调整颜色".format(
                    min_len, max_len, total_rows, result["max_cover"]))
        payload = {
            "ok": False,
            "error": {"type": "infeasible", "message": message},
            "total_rows": total_rows,
            "min_len": min_len,
            "max_len": max_len,
            "total_stock": total_stock,
        }
        if reason == "length_range":
            payload["segment_count_min"] = result["segment_count_min"]
            payload["segment_count_max"] = result["segment_count_max"]
        if reason == "no_exact_cover":
            payload["max_cover"] = result["max_cover"]
        return jsonify(payload)

    return jsonify({
        "ok": True,
        "total_rows": total_rows,
        "min_len": min_len,
        "max_len": max_len,
        "preferred": round(float(preferred), 2),
        "cost": round(float(result["cost"]), 4),
        "segment_count": result["segment_count"],
        "total_stock": result["total_stock"],
        "segments": [{
            "index": s["index"],
            "start": s["start"],
            "end": s["end"],
            "color_index": s["color_index"],
            "color": colors[s["color_index"]]["name"],
            "length": s["length"],
        } for s in result["segments"]],
        "colors": [{
            "index": i,
            "name": colors[i]["name"],
            "stock": stocks[i],
            "used": result["used"][i],
            "remaining": result["remaining"][i],
        } for i in range(len(colors))],
    })


@app.post("/api/seam-align")
def seam_align():
    """两片织物边缘缝合对位：求逐步配对的行号对位表。

    输入 A、B 两侧行数（各 1~60）与可选标记对 (a,b)；起点 (0,0) 与终点
    (rows_a, rows_b) 自动视为标记，用户标记在两侧均须严格递增。每次缝合
    前进 (1,1)、(1,2) 或 (2,1)，路径须经过全部标记并恰好到终点。以每个
    标记区间内两侧累计进度比例差的平方和最小为目标，同分按整条步进序列
    (1,1)＜(1,2)＜(2,1) 的字典序取解。求解由 seam_align.solve_seam 完成
    （动态规划，Fraction/整数精确计算）。某区间无法衔接时指出该区间，
    不返回任何部分路线。
    """
    data = request.get_json(silent=True) or {}

    rows_a, err = _parse_nonneg_int(data.get("rows_a"), "A 侧行数", positive=True)
    if err:
        return jsonify({"ok": False, "error": {"type": "params", "message": err}})
    rows_b, err = _parse_nonneg_int(data.get("rows_b"), "B 侧行数", positive=True)
    if err:
        return jsonify({"ok": False, "error": {"type": "params", "message": err}})
    if not (1 <= rows_a <= 60 and 1 <= rows_b <= 60):
        return jsonify({
            "ok": False,
            "error": {"type": "params",
                      "message": "A、B 两侧行数都必须在 1~60 之间"},
        })

    markers, err = _parse_seam_markers(data.get("markers"), rows_a, rows_b)
    if err:
        return jsonify({"ok": False, "error": {"type": "markers", "message": err}})

    result = solve_seam(rows_a, rows_b, markers)

    if not result["ok"]:
        da, db = result["a_rows"], result["b_rows"]
        if da > db:
            message = (
                "第 {k} 个标记区间无法衔接：从 ({a0},{b0}) 到 ({a1},{b1})，A 侧需前进 "
                "{da} 行、B 侧仅前进 {db} 行（{da} > 2×{db}）；每次缝合单侧最多吃 2 行、"
                "最少吃 1 行，区间内两侧进度比不得超过 2，任何 (1,1)/(1,2)/(2,1) 步进"
                "序列都无法同时经过该区间两端。请调整该区间两端的标记行号，不返回部分路线。"
            ).format(k=result["interval_index"], a0=result["a_from"], b0=result["b_from"],
                     a1=result["a_to"], b1=result["b_to"], da=da, db=db)
        else:
            message = (
                "第 {k} 个标记区间无法衔接：从 ({a0},{b0}) 到 ({a1},{b1})，B 侧需前进 "
                "{db} 行、A 侧仅前进 {da} 行（{db} > 2×{da}）；每次缝合单侧最多吃 2 行、"
                "最少吃 1 行，区间内两侧进度比不得超过 2，任何 (1,1)/(1,2)/(2,1) 步进"
                "序列都无法同时经过该区间两端。请调整该区间两端的标记行号，不返回部分路线。"
            ).format(k=result["interval_index"], a0=result["a_from"], b0=result["b_from"],
                     a1=result["a_to"], b1=result["b_to"], da=da, db=db)
        return jsonify({
            "ok": False,
            "error": {"type": "infeasible", "message": message},
            "rows_a": rows_a,
            "rows_b": rows_b,
            "interval_index": result["interval_index"],
            "from_index": result["from_index"],
            "to_index": result["to_index"],
            "a_from": result["a_from"],
            "b_from": result["b_from"],
            "a_to": result["a_to"],
            "b_to": result["b_to"],
            "a_rows": da,
            "b_rows": db,
        })

    move_labels = {(1, 1): "(1,1)", (1, 2): "(1,2)", (2, 1): "(2,1)"}
    return jsonify({
        "ok": True,
        "rows_a": rows_a,
        "rows_b": rows_b,
        "step_count": result["step_count"],
        "cost": round(float(result["cost"]), 4),
        "markers": result["markers"],
        "intervals": [{
            "index": i["index"],
            "from_index": i["from_index"],
            "to_index": i["to_index"],
            "a_from": i["a_from"],
            "b_from": i["b_from"],
            "a_to": i["a_to"],
            "b_to": i["b_to"],
            "a_rows": i["a_rows"],
            "b_rows": i["b_rows"],
            "steps": i["steps"],
            "cost": round(float(i["cost"]), 4),
        } for i in result["intervals"]],
        "steps": [{
            "seq": s["seq"],
            "interval": s["interval"],
            "move": "mark_{}{}".format(s["move_a"], s["move_b"]),
            "move_label": move_labels[(s["move_a"], s["move_b"])],
            "move_a": s["move_a"],
            "move_b": s["move_b"],
            "a_from": s["a_from"],
            "a_to": s["a_to"],
            "b_from": s["b_from"],
            "b_to": s["b_to"],
            "a_pos": s["a_pos"],
            "b_pos": s["b_pos"],
            "progress_a": round(float(s["progress_a"]), 4),
            "progress_b": round(float(s["progress_b"]), 4),
            "markers": s["markers"],
        } for s in result["steps"]],
    })


@app.post("/api/board-layout")
def board_layout():
    """定型板排片：水平层排布，枚举分层与允许的 90° 旋转，求占用高度最小
    的完整方案。

    每层可放多片（层内按输入顺序自左向右、顶端对齐），层高取本层最大片高；
    相邻片、相邻层均保留片间距，所有片须完整落在板内。同高时取层数最少，
    再取各片所属层序号字典序最小、未旋转优先。求解由
    board_layout.solve_board_layout 完成（整数精确计算）。无解时说明板宽
    或板高不足，不返回任何部分摆放。
    """
    data = request.get_json(silent=True) or {}

    board_width, err = _parse_nonneg_int(
        data.get("board_width"), "定型板宽", positive=True)
    if err:
        return jsonify({"ok": False, "error": {"type": "params", "message": err}})

    board_height, err = _parse_nonneg_int(
        data.get("board_height"), "定型板高", positive=True)
    if err:
        return jsonify({"ok": False, "error": {"type": "params", "message": err}})

    gap, err = _parse_nonneg_int(data.get("gap"), "片间距")
    if err:
        return jsonify({"ok": False, "error": {"type": "params", "message": err}})

    pieces, err = _parse_board_pieces(data.get("pieces"))
    if err:
        return jsonify({"ok": False, "error": {"type": "pieces", "message": err}})

    result = solve_board_layout(board_width, board_height, gap, pieces)

    if not result["ok"]:
        reason = result["reason"]
        if "unfit_pieces" not in result:
            # 每片单独都能放进，但满足板宽限制的最优排法仍超过板高
            message = (
                "板高不足：每片单独都能放入板内，但满足板宽限制的最优排法"
                "占用高度为 {} 厘米（{} 层），超过板高 {} 厘米；"
                "不返回部分摆放".format(
                    result["min_height"], result["layer_count"], board_height))
            return jsonify({
                "ok": False,
                "error": {"type": "infeasible", "message": message},
                "board_width": board_width,
                "board_height": board_height,
                "gap": gap,
                "reason": reason,
                "min_height": result["min_height"],
                "layer_count": result["layer_count"],
            })
        # 有片任何朝向都放不进：逐片说明板宽或板高不足
        details = []
        unfit_pieces = []
        for u in result["unfit_pieces"]:
            p = pieces[u["index"]]
            rot_text = "允许旋转" if p["rotate"] else "不可旋转"
            if not u["width_ok"] and not u["height_ok"]:
                why = "任何朝向宽都超板宽 {}、高都超板高 {}（最窄 {} 厘米、最矮 {} 厘米）".format(
                    board_width, board_height, u["min_width"], u["min_height"])
            elif not u["width_ok"]:
                why = "任何朝向宽都超板宽 {}（最窄 {} 厘米）".format(
                    board_width, u["min_width"])
            elif not u["height_ok"]:
                why = "任何朝向高都超板高 {}（最矮 {} 厘米）".format(
                    board_height, u["min_height"])
            else:
                why = ("不旋转时 {}×{} 与旋转后 {}×{} 都无法同时满足板宽 {} "
                       "与板高 {}").format(
                    p["width"], p["height"], p["height"], p["width"],
                    board_width, board_height)
            details.append("「{}」{}×{}（{}）：{}".format(
                p["name"], p["width"], p["height"], rot_text, why))
            unfit_pieces.append({
                "index": u["index"],
                "name": p["name"],
                "width": p["width"],
                "height": p["height"],
                "rotate": p["rotate"],
                "width_ok": u["width_ok"],
                "height_ok": u["height_ok"],
                "min_width": u["min_width"],
                "min_height": u["min_height"],
            })
        if reason == "width":
            headline = "板宽不足"
        elif reason == "height":
            headline = "板高不足"
        else:
            headline = "板宽与板高不足"
        message = "{}：{}；不返回部分摆放".format(headline, "；".join(details))
        return jsonify({
            "ok": False,
            "error": {"type": "infeasible", "message": message},
            "board_width": board_width,
            "board_height": board_height,
            "gap": gap,
            "reason": reason,
            "unfit_pieces": unfit_pieces,
        })

    return jsonify({
        "ok": True,
        "board_width": board_width,
        "board_height": board_height,
        "gap": gap,
        "used_height": result["used_height"],
        "layer_count": result["layer_count"],
        "layers": result["layers"],
        "pieces": [{
            "index": p["index"],
            "name": pieces[p["index"]]["name"],
            "layer": p["layer"],
            "x": p["x"],
            "y": p["y"],
            "width": p["width"],
            "height": p["height"],
            "rotated": p["rotated"],
        } for p in result["pieces"]],
    })


def _yarn_summary(yarn, state):
    """按尺码累计结果构造线材用量汇总。

    含损耗总量与线团数均按未舍入的精确十进制用量计算：克重只在输出时保留
    两位小数；线团数为含损耗用量除以每团克重后严格向上取整，不减去任何
    容差（恰好整除不多算一团，任何正余数都要多算一团）。
    """
    with localcontext() as ctx:
        ctx.prec = 50
        raw_exact = state["raw_weight"]
        # 1 + waste_percent/100：有限十进制数的精确运算
        factor = Decimal(1) + yarn["waste_percent"] / Decimal(100)
        with_waste_exact = raw_exact * factor
        per_ball = yarn["grams_per_ball"]
        # 严格 ceil(with_waste_exact / per_ball)：把有限十进制量按各自指数
        # 放大成整数后做整除向上取整，避免除法舍入把微小正余数抹掉。
        scale = max(-with_waste_exact.as_tuple().exponent,
                    -per_ball.as_tuple().exponent, 0)
        num = int(with_waste_exact.scaleb(scale))
        den = int(per_ball.scaleb(scale))
        balls = (num + den - 1) // den if num > 0 else 0
    partial = state["error"] is not None
    return {
        "raw_total": _grams(raw_exact),
        "with_waste": _grams(with_waste_exact),
        "balls": balls,
        "partial": partial,
        "complete": not partial,
        "waste_percent": float(yarn["waste_percent"]),
        "grams_per_ball": float(yarn["grams_per_ball"]),
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)

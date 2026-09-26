"""定型板排片：把 2~6 片编织片按水平层排布放进定型板，求占用高度最小的
完整方案。

模型（尺寸均为整数厘米，比较全程整数计算）：
  定型板宽 board_width、高 board_height，片间距 gap（相邻片之间与相邻层
  之间都保留该间距）。每片编织片有宽 w、高 h 与是否允许旋转 90°；允许
  旋转时朝向为 (w,h) 或 (h,w)，正方形片旋转无新几何、只算未旋转一种。

  排布方式为水平层：每层可放多片，片在层内按输入顺序自左向右排列，相邻
  片之间间隔 gap；层高取本层最大片高，各片在层内顶端对齐。层自上而下
  堆叠，相邻层之间间隔 gap。占用高度 = 各层层高之和 + gap×(层数−1)。
  所有片须完整落在板内：每层的总宽（片宽之和 + gap×(片数−1)）不超过
  板宽，且占用高度不超过板高。

  枚举全部有序分层（每片所属层号，层号 1 起连续、自上而下）与全部允许
  朝向的组合，取占用高度最小的完整方案；同高时取层数最少，再取各片所属
  层序号（按输入顺序组成的元组）字典序最小，最后未旋转优先（按输入顺序
  逐片比较，0=未旋转 < 1=已旋转）。层内片的左右顺序不影响层宽与层高，
  故同层片固定按输入顺序自左向右定位，坐标随之确定。

无解诊断（不返回部分摆放）：
  逐片检查是否存在某个朝向同时满足宽 ≤ 板宽、高 ≤ 板高：
  - 有片任何朝向都放不进：按“任何朝向宽都超板宽 / 任何朝向高都超板高 /
    宽与高无法同时满足”逐片说明板宽或板高不足，reason 取
    "width"/"height"/"both"；
  - 每片单独都能放进，但满足板宽限制的最优排法占用高度仍超过板高：
    reason 为 "height"，另给出 min_height（最优排法的占用高度）与对应
    层数 layer_count。
"""

from itertools import product


def solve_board_layout(board_width, board_height, gap, pieces):
    """求解定型板排片。

    参数（调用方已完成校验）：
      board_width  定型板宽（厘米），int，> 0
      board_height 定型板高（厘米），int，> 0
      gap          片间距（厘米），int，≥ 0
      pieces       编织片列表 [{"name", "width", "height", "rotate"}, ...]，
                   2~6 片；width/height 为正整数（厘米），rotate 为是否
                   允许旋转 90°（bool）

    可行时返回：
      {"ok": True, "used_height", "layer_count",
       "layers": [{"index", "y", "height", "width", "pieces": [片下标, ...]}],
       "pieces": [{"index", "layer", "x", "y", "width", "height",
                   "rotated"}, ...]}
      坐标为片左上角（板左上角为 (0,0)，x 向右、y 向下）；width/height
      为最终朝向下的尺寸，rotated 为是否已旋转 90°。
    无解时返回：
      {"ok": False, "reason": "width"|"height"|"both", ...}
      有片任何朝向都放不进时另带 "unfit_pieces"（逐片诊断，含
      width_ok/height_ok/min_width/min_height）；每片都能放进但整体超高
      时 reason 为 "height"，另带 "min_height" 与 "layer_count"。
    """
    n = len(pieces)

    # 每片的可选朝向 (宽, 高, 是否旋转)；正方形旋转无新几何，只留未旋转
    orientations = []
    for p in pieces:
        opts = [(p["width"], p["height"], False)]
        if p["rotate"] and p["width"] != p["height"]:
            opts.append((p["height"], p["width"], True))
        orientations.append(opts)

    # 枚举全部有序分层：assignment[i] 为第 i 片（输入顺序）所属层号，
    # 层号 1 起连续（第 i 片可并入已有层 1..k，或新开第 k+1 层）
    assignments = []
    current = [0] * n

    def collect(i, layers):
        if i == n:
            assignments.append(tuple(current))
            return
        for layer in range(1, layers + 2):
            current[i] = layer
            collect(i + 1, max(layers, layer))
        current[i] = 0

    collect(0, 0)

    # 枚举分层 × 朝向，按 (占用高度, 层数, 层号元组, 旋转元组) 取最小
    best = None  # (key, assignment, 朝向组合)
    for assign in assignments:
        layer_count = max(assign)
        members = [[] for _ in range(layer_count)]
        for idx, layer in enumerate(assign):
            members[layer - 1].append(idx)
        for combo in product(*orientations):
            used_height = gap * (layer_count - 1)
            fits = True
            for group in members:
                layer_width = gap * (len(group) - 1)
                layer_height = 0
                for idx in group:
                    w, h, _rotated = combo[idx]
                    layer_width += w
                    if h > layer_height:
                        layer_height = h
                if layer_width > board_width:
                    fits = False
                    break
                used_height += layer_height
            if not fits:
                continue
            rotated_flags = tuple(1 if c[2] else 0 for c in combo)
            key = (used_height, layer_count, assign, rotated_flags)
            if best is None or key < best[0]:
                best = (key, assign, combo)

    # 逐片诊断：是否存在某个朝向同时满足宽 ≤ 板宽、高 ≤ 板高
    unfit = []
    for idx, opts in enumerate(orientations):
        width_ok = any(w <= board_width for w, _h, _r in opts)
        height_ok = any(h <= board_height for _w, h, _r in opts)
        if not any(w <= board_width and h <= board_height
                   for w, h, _r in opts):
            unfit.append({
                "index": idx,
                "width_ok": width_ok,
                "height_ok": height_ok,
                "min_width": min(w for w, _h, _r in opts),
                "min_height": min(h for _w, h, _r in opts),
            })

    if unfit:
        # 有片任何朝向都放不进（此时必无完整方案：该片所在层必超板宽）
        width_bad = any(not u["width_ok"] for u in unfit)
        height_bad = any(not u["height_ok"] for u in unfit)
        if width_bad and height_bad:
            reason = "both"
        elif width_bad:
            reason = "width"
        elif height_bad:
            reason = "height"
        else:
            # 每片都有朝向满足宽、也有朝向满足高，但没有同一朝向同时满足
            reason = "both"
        return {"ok": False, "reason": reason, "unfit_pieces": unfit}

    # 每片单独都能放进：最优排法必存在（每片独占一层总可满足板宽），
    # 剩下的唯一失败原因是其占用高度超过板高
    if best[0][0] > board_height:
        return {
            "ok": False,
            "reason": "height",
            "min_height": best[0][0],
            "layer_count": best[0][1],
        }

    key, assign, combo = best
    used_height, layer_count = key[0], key[1]
    members = [[] for _ in range(layer_count)]
    for idx, layer in enumerate(assign):
        members[layer - 1].append(idx)

    layers = []
    placed = [None] * n
    y = 0
    for layer_index, group in enumerate(members, 1):
        layer_height = max(combo[idx][1] for idx in group)
        layer_width = sum(combo[idx][0] for idx in group) + gap * (len(group) - 1)
        x = 0
        for idx in group:
            w, h, rotated = combo[idx]
            placed[idx] = {
                "index": idx,
                "layer": layer_index,
                "x": x,
                "y": y,
                "width": w,
                "height": h,
                "rotated": rotated,
            }
            x += w + gap
        layers.append({
            "index": layer_index,
            "y": y,
            "height": layer_height,
            "width": layer_width,
            "pieces": list(group),
        })
        y += layer_height + gap

    return {
        "ok": True,
        "used_height": used_height,
        "layer_count": layer_count,
        "layers": layers,
        "pieces": placed,
    }

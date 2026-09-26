"""缝合对位：为两片织物边缘求逐步配对的行号对位表。

模型（代价与比较全程用 Fraction/整数精确计算，不用浮点）：
  A、B 两侧各有 rows_a、rows_b 行（1~60），起终点自动视为标记 (0,0) 与
  (rows_a, rows_b)，用户还可给出若干中间标记 (a,b)，且标记在两侧均严格
  递增（0 < a < rows_a、0 < b < rows_b，后一个的 a、b 都大于前一个）。
  相邻两个标记之间构成一个独立区间，区间 k 由 (a0,b0) 到 (a1,b1)，两侧
  需前进 da = a1−a0、db = b1−b0 行。

  每次缝合从当前累计行号前进一个步进 (1,1)、(1,2) 或 (2,1)（分别表示
  A/B 两侧各吃 1 行、A 吃 1 行 B 吃 2 行、A 吃 2 行 B 吃 1 行）。设区间
  内某一步结束时两侧的区间内累计行为 x、y（0 ≤ x ≤ da，0 ≤ y ≤ db），
  则两侧累计进度比例分别为 x/da 与 y/db，优化目标为最小化区间内各步
  结束点（不含起点）的

      (x/da − y/db)² = (x·db − y·da)² / (da·db)²

  之和；起点与终点该项都是 0，计入不影响结果。各区间代价相互独立，全局
  最优即逐区间最优之和。同分（平方差之和相同）时按整条步进序列的字典序
  取最小，顺序固定为 (1,1) ＜ (1,2) ＜ (2,1)；逐区间正向按此顺序回溯，
  前缀逐位最小即保证整条序列字典序最小。

求解用反向动态规划：g[x][y] 为从区间内累计 (x,y) 走到 (da,db) 的最小
剩余代价分子（区间分母恒为 (da·db)²，表内只存整数分子 (x·db−y·da)²
之和），不可达为 None；g[da][db]=0，按 x、y 递减枚举三个步进取最小。

可行性：每个步进两坐标都至少 +1、至多 +2，故任何可达点两侧累计进度之
比不超过 2；区间可衔接当且仅当 max(da,db) ≤ 2·min(da,db)。不满足时
g[0][0] 为 None，由调用方指出该区间，不返回任何部分路线。
"""

from fractions import Fraction

# 同分字典序固定顺序：(1,1) 最小，(1,2) 次之，(2,1) 最大
MOVES = ((1, 1), (1, 2), (2, 1))


def solve_seam(rows_a, rows_b, markers):
    """求解缝合对位。

    参数（调用方已完成校验）：
      rows_a   A 侧总行数，int，1~60
      rows_b   B 侧总行数，int，1~60
      markers  中间标记列表 [(a, b), ...]，均为严格递增的内部整数对
               （0 < a < rows_a、0 < b < rows_b），可为空列表

    可行时返回：
      {"ok": True, "rows_a", "rows_b",
       "markers": [{"index", "a", "b", "type"}, ...],  # 含起终点的完整标记链
       "intervals": [{"index", "from_index", "to_index", "a_from", "b_from",
                      "a_to", "b_to", "a_rows", "b_rows", "steps", "cost"}, ...],
       "steps": [{"seq", "interval", "move_a", "move_b", "a_from", "a_to",
                  "b_from", "b_to", "a_pos", "b_pos",
                  "progress_a", "progress_b", "markers"}, ...],
       "step_count", "cost"}
      type ∈ {"start", "mark", "end"}；cost 为精确 Fraction（逐区间平方
      差之和），progress_a/progress_b 为区间内累计进度（精确 Fraction）；
      steps[].markers 列出该步结束时落在的标记（完整链中的标记描述）。
    无解时返回：
      {"ok": False, "reason": "infeasible_interval", "interval_index",
       "from_index", "to_index", "a_from", "b_from", "a_to", "b_to",
       "a_rows", "b_rows"}
      不含任何步骤或区间结果（不返回部分路线）。
    """
    chain = [(0, 0)] + [(int(a), int(b)) for a, b in markers] + \
        [(rows_a, rows_b)]

    full_markers = []
    for i, (a, b) in enumerate(chain):
        if i == 0:
            mtype = 'start'
        elif i == len(chain) - 1:
            mtype = 'end'
        else:
            mtype = 'mark'
        full_markers.append({"index": i, "a": a, "b": b, "type": mtype})
    # 坐标 -> 完整链下标，供逐步判断落在哪个标记
    at_coord = {coord: i for i, coord in enumerate(chain)}

    intervals = []
    steps = []
    total_cost = Fraction(0)
    seq = 0

    for k in range(len(chain) - 1):
        a0, b0 = chain[k]
        a1, b1 = chain[k + 1]
        da, db = a1 - a0, b1 - b0

        # 反向 DP：g[x][y] 为从区间内累计 (x,y) 到 (da,db) 的最小剩余代价
        # 分子；分母 (da·db)² 在整个区间恒定，故只存整数分子。
        g = [[None] * (db + 1) for _ in range(da + 1)]
        g[da][db] = 0
        for x in range(da, -1, -1):
            for y in range(db, -1, -1):
                if x == da and y == db:
                    continue
                best = None
                for mx, my in MOVES:
                    nx, ny = x + mx, y + my
                    if nx <= da and ny <= db:
                        tail = g[nx][ny]
                        if tail is not None:
                            diff = nx * db - ny * da
                            num = diff * diff + tail
                            if best is None or num < best:
                                best = num
                g[x][y] = best

        if g[0][0] is None:
            # 该区间无法衔接：指出区间，不返回任何部分路线
            return {
                "ok": False,
                "reason": "infeasible_interval",
                "interval_index": k + 1,
                "from_index": k,
                "to_index": k + 1,
                "a_from": a0,
                "b_from": b0,
                "a_to": a1,
                "b_to": b1,
                "a_rows": da,
                "b_rows": db,
            }

        denom = (da * db) ** 2
        interval_cost = Fraction(g[0][0], denom)
        total_cost += interval_cost

        # 正向贪心回溯：按 (1,1)、(1,2)、(2,1) 顺序取第一个仍能达成区间
        # 最优代价的步进，区间内步进序列即在同分方案中字典序最小
        vertices = [(0, 0)]
        x = y = 0
        remaining = g[0][0]
        while (x, y) != (da, db):
            for mx, my in MOVES:
                nx, ny = x + mx, y + my
                if nx <= da and ny <= db and g[nx][ny] is not None:
                    diff = nx * db - ny * da
                    if diff * diff + g[nx][ny] == remaining:
                        vertices.append((nx, ny))
                        remaining -= diff * diff
                        x, y = nx, ny
                        break

        interval_steps = len(vertices) - 1
        intervals.append({
            "index": k + 1,
            "from_index": k,
            "to_index": k + 1,
            "a_from": a0,
            "b_from": b0,
            "a_to": a1,
            "b_to": b1,
            "a_rows": da,
            "b_rows": db,
            "steps": interval_steps,
            "cost": interval_cost,
        })

        for (px, py), (x, y) in zip(vertices, vertices[1:]):
            seq += 1
            mx, my = x - px, y - py
            landed = []
            chain_idx = at_coord.get((a0 + x, b0 + y))
            if chain_idx is not None:
                landed.append(dict(full_markers[chain_idx]))
            steps.append({
                "seq": seq,
                "interval": k + 1,
                "move_a": mx,
                "move_b": my,
                "a_from": a0 + px + 1,
                "a_to": a0 + x,
                "b_from": b0 + py + 1,
                "b_to": b0 + y,
                "a_pos": a0 + x,
                "b_pos": b0 + y,
                "progress_a": Fraction(x, da),
                "progress_b": Fraction(y, db),
                "markers": landed,
            })

    return {
        "ok": True,
        "rows_a": rows_a,
        "rows_b": rows_b,
        "markers": full_markers,
        "intervals": intervals,
        "steps": steps,
        "step_count": len(steps),
        "cost": total_cost,
    }

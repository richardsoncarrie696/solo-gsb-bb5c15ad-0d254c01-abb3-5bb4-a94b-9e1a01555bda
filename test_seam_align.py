"""缝合对位求解器测试：与暴力枚举对照最优代价与同分字典序选择。"""

import random
import unittest
from fractions import Fraction

from seam_align import solve_seam

MOVES = ((1, 1), (1, 2), (2, 1))


def brute_interval(da, db):
    """枚举区间 (0,0)→(da,db) 的全部步进序列，返回 (最小代价, 序列) 或 None。

    序列记为 ((ma, mb), ...)；代价为各步结束点 (x/da − y/db)² 之和
    （Fraction 精确）；同分时按步进序列字典序 (1,1)＜(1,2)＜(2,1) 取最小。
    """
    best = None

    def walk(x, y, sequence, cost):
        nonlocal best
        if x == da and y == db:
            key = (cost, tuple(sequence))
            if best is None or key < best:
                best = key
            return
        for mx, my in MOVES:
            nx, ny = x + mx, y + my
            if nx <= da and ny <= db:
                walk(nx, ny, sequence + [(mx, my)],
                     cost + (Fraction(nx, da) - Fraction(ny, db)) ** 2)

    walk(0, 0, [], Fraction(0))
    return best


def brute_seam(rows_a, rows_b, markers):
    """按区间独立组合全路径的 (总代价, 整条步进序列)，无解返回 None。"""
    chain = [(0, 0)] + list(markers) + [(rows_a, rows_b)]
    total_cost = Fraction(0)
    full_sequence = ()
    for (a0, b0), (a1, b1) in zip(chain, chain[1:]):
        best = brute_interval(a1 - a0, b1 - b0)
        if best is None:
            return None
        total_cost += best[0]
        full_sequence += best[1]
    return total_cost, full_sequence


def step_tuple(result):
    """从求解结果中取出整条步进序列 ((ma, mb), ...)。"""
    return tuple((s['move_a'], s['move_b']) for s in result['steps'])


class TestSolveSeam(unittest.TestCase):
    def test_no_markers_even_rows(self):
        # A=B 时全部走 (1,1)，代价 0
        result = solve_seam(5, 5, [])
        self.assertTrue(result['ok'])
        self.assertEqual(step_tuple(result), ((1, 1),) * 5)
        self.assertEqual(result['cost'], 0)
        self.assertEqual(result['step_count'], 5)
        # 起终点自动加入标记链
        self.assertEqual([(m['a'], m['b'], m['type']) for m in result['markers']],
                         [(0, 0, 'start'), (5, 5, 'end')])

    def test_single_row_each(self):
        result = solve_seam(1, 1, [])
        self.assertTrue(result['ok'])
        self.assertEqual(step_tuple(result), ((1, 1),))
        step = result['steps'][0]
        self.assertEqual((step['a_from'], step['a_to']), (1, 1))
        self.assertEqual((step['b_from'], step['b_to']), (1, 1))
        self.assertEqual(step['progress_a'], 1)
        self.assertEqual(step['progress_b'], 1)

    def test_example_eight_seven(self):
        # A=8、B=7 无标记：代价 1/112，多吃的一行 A 落在区间最靠后的同分位置
        result = solve_seam(8, 7, [])
        self.assertTrue(result['ok'])
        self.assertEqual(result['cost'], Fraction(1, 112))
        self.assertEqual(step_tuple(result),
                         ((1, 1), (1, 1), (1, 1), (2, 1),
                          (1, 1), (1, 1), (1, 1)))
        last = result['steps'][-1]
        self.assertEqual(last['markers'],
                         [{'index': 1, 'a': 8, 'b': 7, 'type': 'end'}])

    def test_tie_break_lexicographic_prefers_11(self):
        # A=2、B=3 无标记：只能一个 (1,2) 配一个 (1,1)，两种顺序代价相同，
        # 字典序 (1,1) 最小，故 (1,1) 在前
        result = solve_seam(2, 3, [])
        self.assertTrue(result['ok'])
        self.assertEqual(step_tuple(result), ((1, 1), (1, 2)))

    def test_tie_break_lexicographic_order(self):
        # A=3、B=2：(1,1) 与 (2,1) 各一个，同分时 (1,1) 在前
        result = solve_seam(3, 2, [])
        self.assertTrue(result['ok'])
        self.assertEqual(step_tuple(result), ((1, 1), (2, 1)))

    def test_markers_split_independent_intervals(self):
        # 标记 (3,2) 把 (10,8) 切成 (3,2) 与 (7,6) 两个独立区间
        result = solve_seam(10, 8, [(3, 2)])
        self.assertTrue(result['ok'])
        self.assertEqual([m['a'] for m in result['markers']], [0, 3, 10])
        self.assertEqual(result['intervals'][0]['a_rows'], 3)
        self.assertEqual(result['intervals'][0]['b_rows'], 2)
        self.assertEqual(result['intervals'][1]['a_rows'], 7)
        self.assertEqual(result['intervals'][1]['b_rows'], 6)
        # 路径必须在标记点落脚
        self.assertTrue(any(s['a_pos'] == 3 and s['b_pos'] == 2
                            for s in result['steps']))
        # 区间费用之和等于总费用
        self.assertEqual(result['cost'],
                         sum(i['cost'] for i in result['intervals']))

    def test_step_row_ranges_partition_each_side(self):
        result = solve_seam(12, 9, [(4, 3), (9, 6)])
        self.assertTrue(result['ok'])
        for side, total in (('a', 12), ('b', 9)):
            covered = 0
            for step in result['steps']:
                self.assertEqual(step[side + '_from'], covered + 1)
                covered = step[side + '_to']
            self.assertEqual(covered, total)
        # 每步行号范围宽度等于该步进吃行数
        for step in result['steps']:
            self.assertEqual(step['a_to'] - step['a_from'] + 1, step['move_a'])
            self.assertEqual(step['b_to'] - step['b_from'] + 1, step['move_b'])

    def test_marker_landings_recorded(self):
        # 区间依次为 (2,3)、(3,2)、(1,1)，均可行
        result = solve_seam(6, 6, [(2, 3), (5, 5)])
        self.assertTrue(result['ok'])
        landed = {(m['a'], m['b'])
                  for s in result['steps'] for m in s['markers']}
        self.assertIn((2, 3), landed)
        self.assertIn((5, 5), landed)
        self.assertIn((6, 6), landed)
        self.assertNotIn((0, 0), landed)  # 起点不算“经过”的步

    def test_infeasible_without_markers(self):
        result = solve_seam(10, 3, [])
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'infeasible_interval')
        self.assertEqual(result['interval_index'], 1)
        self.assertEqual((result['a_rows'], result['b_rows']), (10, 3))
        self.assertNotIn('steps', result)

    def test_infeasible_interval_between_markers(self):
        # 总段 (10,10) 可行，但标记 (1,5) 使第 1 区间为 (1,5)，比例 5:1 无法衔接
        result = solve_seam(10, 10, [(1, 5)])
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'infeasible_interval')
        self.assertEqual(result['interval_index'], 1)
        self.assertEqual((result['a_from'], result['b_from']), (0, 0))
        self.assertEqual((result['a_to'], result['b_to']), (1, 5))
        # 指出区间，不返回任何部分路线
        self.assertNotIn('steps', result)
        self.assertNotIn('intervals', result)

    def test_infeasible_later_interval(self):
        # 第 1 区间 (3,2) 可行，第 2 区间 (2,5) 不可行
        result = solve_seam(5, 7, [(3, 2)])
        self.assertFalse(result['ok'])
        self.assertEqual(result['interval_index'], 2)
        self.assertEqual((result['a_rows'], result['b_rows']), (2, 5))

    def test_boundary_ratio_two_is_feasible(self):
        # 比例恰为 2:1 时全部走 (2,1) 仍可衔接
        result = solve_seam(10, 5, [])
        self.assertTrue(result['ok'])
        self.assertEqual(step_tuple(result), ((2, 1),) * 5)
        self.assertEqual(result['cost'], 0)

    def test_random_against_brute_force(self):
        rng = random.Random(20260925)
        for _ in range(400):
            rows_a = rng.randint(1, 12)
            rows_b = rng.randint(1, 12)
            markers = []
            a = b = 0
            while len(markers) < 3:
                if not rng.randint(0, 2):
                    break
                na = rng.randint(a + 1, rows_a - 1) if a + 1 <= rows_a - 1 else None
                nb = rng.randint(b + 1, rows_b - 1) if b + 1 <= rows_b - 1 else None
                if na is None or nb is None:
                    break
                markers.append((na, nb))
                a, b = na, nb
            result = solve_seam(rows_a, rows_b, markers)
            best = brute_seam(rows_a, rows_b, markers)
            msg = '参数 A={} B={} markers={}'.format(rows_a, rows_b, markers)
            if best is None:
                self.assertFalse(result['ok'], msg=msg)
            else:
                self.assertTrue(result['ok'], msg=msg)
                self.assertEqual(result['cost'], best[0], msg=msg)
                self.assertEqual(step_tuple(result), best[1], msg=msg)

    def test_max_rows_sixty_runs_fast(self):
        # 上限规模：60/59 无标记，DP 应瞬间完成且方案自洽
        result = solve_seam(60, 59, [])
        self.assertTrue(result['ok'])
        self.assertEqual(sum(s['move_a'] for s in result['steps']), 60)
        self.assertEqual(sum(s['move_b'] for s in result['steps']), 59)
        self.assertEqual(result['steps'][-1]['a_pos'], 60)
        self.assertEqual(result['steps'][-1]['b_pos'], 59)

    def test_progress_within_each_interval(self):
        result = solve_seam(10, 8, [(3, 2)])
        self.assertTrue(result['ok'])
        for interval in result['intervals']:
            pa = pb = Fraction(0)
            for s in result['steps']:
                if s['interval'] == interval['index']:
                    # 区间内进度单调不减，末步到 1
                    self.assertGreaterEqual(s['progress_a'], pa)
                    self.assertGreaterEqual(s['progress_b'], pb)
                    pa, pb = s['progress_a'], s['progress_b']
            self.assertEqual(pa, 1)
            self.assertEqual(pb, 1)
        # 每步进度都在 [0,1]
        for s in result['steps']:
            self.assertTrue(0 <= s['progress_a'] <= 1)
            self.assertTrue(0 <= s['progress_b'] <= 1)


if __name__ == '__main__':
    unittest.main()

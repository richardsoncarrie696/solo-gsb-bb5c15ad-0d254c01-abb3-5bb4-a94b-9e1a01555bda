"""条纹用线排程求解器测试：与暴力枚举对照最优代价与同分字典序选择。"""

import random
import unittest
from fractions import Fraction

from stripe_schedule import solve_stripes


def brute_force(total_rows, stocks, min_len, max_len, preferred):
    """枚举所有恰好覆盖总行数的连续段序列，返回 (最小代价, 段序列) 或 None。

    段序列记为 ((颜色下标, 段长), ...)；同分时按该元组字典序取最小，即先比
    颜色输入顺序，颜色相同再比段长升序。
    """
    num_colors = len(stocks)

    def extend(pos, last_color, used, sequence):
        if pos == total_rows:
            cost = sum(abs(Fraction(length) - preferred)
                       for _color, length in sequence)
            key = (cost, tuple(sequence))
            return key
        best = None
        for color in range(num_colors):
            if color == last_color:
                continue
            for length in range(min_len, max_len + 1):
                next_pos = pos + length
                if next_pos > total_rows:
                    break
                if used[color] + length > stocks[color]:
                    break
                used[color] += length
                candidate = extend(next_pos, color, used,
                                   sequence + [(color, length)])
                used[color] -= length
                if candidate is not None and (best is None or candidate < best):
                    best = candidate
        return best

    return extend(0, -1, [0] * num_colors, [])


def brute_cover(total_rows, stocks, min_len, max_len):
    """暴力求约束下最多可连续覆盖的行数（不要求恰好等于总行数）。"""
    num_colors = len(stocks)

    def extend(pos, last_color, used):
        farthest = pos
        for color in range(num_colors):
            if color == last_color:
                continue
            for length in range(min_len, max_len + 1):
                next_pos = pos + length
                if next_pos > total_rows or used[color] + length > stocks[color]:
                    break
                used[color] += length
                reached = extend(next_pos, color, used)
                used[color] -= length
                if reached > farthest:
                    farthest = reached
        return farthest

    return extend(0, -1, [0] * num_colors)


def segment_tuple(result):
    """从求解结果中取出 ((颜色下标, 段长), ...)。"""
    return tuple((s['color_index'], s['length']) for s in result['segments'])


class TestSolveStripes(unittest.TestCase):
    def test_example_two_colors_prefers_length_three(self):
        # 20 行、段长 2~4、偏好 3、米白库存 12 / 藏青库存 8：
        # 7 段各取 3 为 21 行，需把一段缩为 2（代价 1）；藏青只有 3 段，
        # 缩短段必须落在藏青段上（否则藏青用量 9 > 8）。可行位置为第 2、4、6
        # 段，字典序（先颜色后段长）最靠前的是第 2 段缩为 2
        result = solve_stripes(20, [12, 8], 2, 4, Fraction(3))
        self.assertTrue(result['ok'])
        self.assertEqual(result['segment_count'], 7)
        self.assertEqual(segment_tuple(result),
                         ((0, 3), (1, 2), (0, 3), (1, 3),
                          (0, 3), (1, 3), (0, 3)))
        self.assertEqual(result['cost'], 1)
        self.assertEqual(result['used'], [12, 8])
        self.assertEqual(result['remaining'], [0, 0])

    def test_segments_cover_every_row_with_start_end(self):
        result = solve_stripes(10, [6, 6], 1, 6, Fraction(2))
        self.assertTrue(result['ok'])
        segments = result['segments']
        # 起止行连续、恰好覆盖 1~10
        self.assertEqual(segments[0]['start'], 1)
        for prev, seg in zip(segments, segments[1:]):
            self.assertEqual(seg['start'], prev['end'] + 1)
        self.assertEqual(segments[-1]['end'], 10)
        # 相邻段异色
        for prev, seg in zip(segments, segments[1:]):
            self.assertNotEqual(prev['color_index'], seg['color_index'])
        # 用量不超库存
        for i, stock in enumerate([6, 6]):
            self.assertLessEqual(result['used'][i], stock)
        self.assertEqual(sum(s['length'] for s in segments), 10)

    def test_tie_break_color_order_before_length(self):
        # 8 行、段长 1~4、库存充足、偏好 2.5：最小代价 1.5（3 段两长 3 一长 2），
        # 以颜色 0 开头与以颜色 1 开头的序列同分（如 (0,2)(1,3)(0,3) 与
        # (1,2)(0,3)(1,3)），颜色输入顺序优先：取颜色 0 开头中段长最靠前者
        result = solve_stripes(8, [8, 8], 1, 4, Fraction(5, 2))
        self.assertTrue(result['ok'])
        self.assertEqual(result['cost'], Fraction(3, 2))
        self.assertEqual(segment_tuple(result), ((0, 2), (1, 3), (0, 3)))

    def test_tie_break_shorter_length_earlier(self):
        # 颜色顺序一致时，同分序列里靠前位置段长更短者优先。
        # 10 行、段长 2~4、库存 [10,10]、偏好 3：3+3+4 与 3+4+3、4+3+3
        # 同为 3 段且代价 1，段长升序使最短的非 3 段尽量靠后取 3,3,4；
        # 但颜色先于段长比较，首段颜色 0 相同后取首段最短——3 段方案首段
        # 可为 3（另两段 3+4），最靠前的段序列即 (0,3)(1,3)(0,4)
        result = solve_stripes(10, [10, 10], 2, 4, Fraction(3))
        self.assertTrue(result['ok'])
        self.assertEqual(segment_tuple(result),
                         ((0, 3), (1, 3), (0, 4)))

    def test_three_colors(self):
        result = solve_stripes(12, [5, 5, 5], 2, 3, Fraction(3))
        self.assertTrue(result['ok'])
        self.assertTrue(all(2 <= s['length'] <= 3 for s in result['segments']))
        self.assertEqual(result['segments'][-1]['end'], 12)
        self.assertEqual(sum(result['used']), 12)

    def test_single_segment_not_possible_when_min_len_gt_rows(self):
        result = solve_stripes(1, [1, 1], 2, 6, Fraction(2))
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'length_range')
        self.assertEqual(result['segment_count_min'], 1)
        self.assertEqual(result['segment_count_max'], 0)

    def test_length_range_gap(self):
        # 段长只能 4~6：k 段区间 [4k,6k]，1 段最多 6 行、2 段最少 8 行，
        # 7 行无法落在任何区间
        result = solve_stripes(7, [7, 7], 4, 6, Fraction(5))
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'length_range')
        self.assertEqual(result['segment_count_min'], 2)
        self.assertEqual(result['segment_count_max'], 1)

    def test_stock_shortage(self):
        result = solve_stripes(20, [8, 8], 1, 6, Fraction(4))
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'stock_shortage')
        self.assertEqual(result['total_stock'], 16)

    def test_no_exact_cover_due_to_color_stock(self):
        # 段长区间 3~5：6 行可由 1 段（3~5 放不下 6）或 2 段（区间 6~10）
        # 覆盖；两段须异色各 3 行，但颜色 0 库存只有 2，颜色 1 不能连续
        # 两段，故无法恰好覆盖。放松到“尽量多排”：可先排一段颜色 1 的
        # 5 行（首段颜色不限），最多连续覆盖 5 行
        result = solve_stripes(6, [2, 6], 3, 5, Fraction(3))
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'no_exact_cover')
        self.assertEqual(result['max_cover'], 5)

    def test_no_exact_cover_due_to_alternation_and_stock(self):
        # 段长固定 2：4 行需两种颜色各 1 段，库存 [2,3] 恰好可行；
        # 6 行需 3 段，开头颜色要出 2 段共 4 行，库存 [3,3] 时两种颜色
        # 都撑不起 2 段（库存合计 6 并不缺线），无法恰好覆盖；放松后
        # 最多连续覆盖 4 行（0,2)(1,2)
        feasible = solve_stripes(4, [2, 3], 2, 2, Fraction(2))
        self.assertTrue(feasible['ok'])
        self.assertEqual(segment_tuple(feasible), ((0, 2), (1, 2)))
        result = solve_stripes(6, [3, 3], 2, 2, Fraction(2))
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'no_exact_cover')
        self.assertEqual(result['total_stock'], 6)
        self.assertEqual(result['max_cover'], 4)

    def test_zero_stock_color(self):
        # 第三种颜色库存为 0：方案只能由前两种颜色组成，等价于两色问题
        result = solve_stripes(6, [6, 6, 0], 1, 6, Fraction(3))
        self.assertTrue(result['ok'])
        self.assertEqual(result['used'][2], 0)
        self.assertEqual(result['remaining'][2], 0)
        self.assertTrue(all(s['color_index'] != 2 for s in result['segments']))

    def test_random_against_brute_force(self):
        rng = random.Random(20260925)
        for _ in range(500):
            total_rows = rng.randint(1, 9)
            num_colors = rng.randint(2, 3)
            stocks = [rng.randint(0, total_rows + 1) for _ in range(num_colors)]
            min_len = rng.randint(1, 3)
            max_len = rng.randint(min_len, 4)
            preferred = Fraction(rng.randint(1, 8), rng.randint(1, 3))
            result = solve_stripes(total_rows, stocks, min_len, max_len, preferred)
            best = brute_force(total_rows, stocks, min_len, max_len, preferred)
            msg = '参数 rows={} stocks={} len={}~{} pref={}'.format(
                total_rows, stocks, min_len, max_len, preferred)
            if best is None:
                self.assertFalse(result['ok'], msg=msg)
                if result['reason'] == 'no_exact_cover':
                    self.assertEqual(
                        result['max_cover'],
                        brute_cover(total_rows, stocks, min_len, max_len), msg=msg)
            else:
                self.assertTrue(result['ok'], msg=msg)
                self.assertEqual(result['cost'], best[0], msg=msg)
                self.assertEqual(segment_tuple(result), best[1], msg=msg)

    def test_max_rows_forty_runs_fast(self):
        # 上限规模：40 行、3 色充足库存，DP 应瞬间完成且方案自洽
        result = solve_stripes(40, [40, 40, 40], 1, 6, Fraction(4))
        self.assertTrue(result['ok'])
        self.assertEqual(result['segments'][-1]['end'], 40)
        self.assertEqual(sum(result['used']), 40)


if __name__ == '__main__':
    unittest.main()

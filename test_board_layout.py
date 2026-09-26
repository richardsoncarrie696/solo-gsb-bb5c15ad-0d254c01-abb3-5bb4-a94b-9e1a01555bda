"""定型板排片求解器测试：与独立暴力枚举对照最优高度与同分选择规则。"""

import random
import unittest
from itertools import product

from board_layout import solve_board_layout


def brute_force(board_width, board_height, gap, pieces):
    """独立暴力枚举：所有有序分层 × 所有允许朝向，返回最优
    (占用高度, 层数, 层号元组, 旋转元组, 朝向组合)，无板宽可行解返回 None。

    层号元组按输入顺序给出每片所属层号（1 起连续）；只检查每层总宽不超
    板宽，占用高度是否超板高由调用方判断。同分按元组字典序取最小，即
    占用高度 → 层数 → 层号元组 → 旋转元组（0=未旋转 < 1=已旋转）。
    """
    n = len(pieces)
    orientations = []
    for p in pieces:
        opts = [(p['width'], p['height'], False)]
        if p['rotate'] and p['width'] != p['height']:
            opts.append((p['height'], p['width'], True))
        orientations.append(opts)

    best = None
    for assign in product(range(1, n + 1), repeat=n):
        layer_count = max(assign)
        if set(assign) != set(range(1, layer_count + 1)):
            continue  # 层号必须从 1 连续（无空层）
        members = [[] for _ in range(layer_count)]
        for idx, layer in enumerate(assign):
            members[layer - 1].append(idx)
        for combo in product(*orientations):
            used_height = gap * (layer_count - 1)
            fits = True
            for group in members:
                width = sum(combo[i][0] for i in group) + gap * (len(group) - 1)
                if width > board_width:
                    fits = False
                    break
                used_height += max(combo[i][1] for i in group)
            if not fits:
                continue
            rotated = tuple(1 if c[2] else 0 for c in combo)
            key = (used_height, layer_count, assign, rotated)
            if best is None or key < best[0]:
                best = (key, combo)
    if best is None:
        return None
    return best[0] + (best[1],)


def result_key(result):
    """从可行求解结果中取出 (占用高度, 层数, 层号元组, 旋转元组)。"""
    assign = tuple(p['layer'] for p in result['pieces'])
    rotated = tuple(1 if p['rotated'] else 0 for p in result['pieces'])
    return (result['used_height'], result['layer_count'], assign, rotated)


class TestSolveBoardLayout(unittest.TestCase):
    def test_example_five_pieces_two_layers(self):
        # 90×60 板、片间距 3：三片 32 高的片恰好同层（40+20+20+3×2=86≤90），
        # 两片袖子同层（34+34+3=71≤90），占用高度 32+3+14=49
        pieces = [
            {'name': '后片', 'width': 40, 'height': 32, 'rotate': False},
            {'name': '左前片', 'width': 20, 'height': 32, 'rotate': True},
            {'name': '右前片', 'width': 20, 'height': 32, 'rotate': True},
            {'name': '袖子A', 'width': 34, 'height': 14, 'rotate': True},
            {'name': '袖子B', 'width': 34, 'height': 14, 'rotate': True},
        ]
        result = solve_board_layout(90, 60, 3, pieces)
        self.assertTrue(result['ok'])
        self.assertEqual(result['used_height'], 49)
        self.assertEqual(result['layer_count'], 2)
        self.assertEqual(result_key(result)[2], (1, 1, 1, 2, 2))
        self.assertEqual(result_key(result)[3], (0, 0, 0, 0, 0))
        # 各片左上角坐标：层内按输入顺序自左向右，层自上而下
        expected = [(0, 0), (43, 0), (66, 0), (0, 35), (37, 35)]
        for piece, (x, y) in zip(result['pieces'], expected):
            self.assertEqual((piece['x'], piece['y']), (x, y))
        # 分层汇总与占用高度一致
        self.assertEqual([l['height'] for l in result['layers']], [32, 14])
        self.assertEqual([l['width'] for l in result['layers']], [86, 71])
        self.assertEqual([l['y'] for l in result['layers']], [0, 35])

    def test_rotation_enables_single_layer(self):
        # 两片 20×10 可旋转：不旋转同层宽 40 超板宽 25；都旋转后 10+10≤25，
        # 一层高 20 与两层不旋转（10+10，片间距 0）同高，同高取层数最少
        pieces = [
            {'name': 'A', 'width': 20, 'height': 10, 'rotate': True},
            {'name': 'B', 'width': 20, 'height': 10, 'rotate': True},
        ]
        result = solve_board_layout(25, 25, 0, pieces)
        self.assertTrue(result['ok'])
        self.assertEqual(result['used_height'], 20)
        self.assertEqual(result['layer_count'], 1)
        self.assertEqual(result_key(result)[3], (1, 1))

    def test_unrotated_preferred_on_tie(self):
        # 同高、同层数、同分层时未旋转优先：一层不旋转（宽 20）与一层
        # 首片旋转（宽 30）都可行且同高 20，取不旋转
        pieces = [
            {'name': 'A', 'width': 10, 'height': 20, 'rotate': True},
            {'name': 'B', 'width': 10, 'height': 20, 'rotate': True},
        ]
        result = solve_board_layout(30, 20, 0, pieces)
        self.assertTrue(result['ok'])
        self.assertEqual(result_key(result)[3], (0, 0))

    def test_layer_assignment_lexicographic(self):
        # 两片都放不进同一层（10+10>10）：(1,2) 与 (2,1) 同高同层数，
        # 取层号元组字典序最小的 (1,2)，即 A 在上层
        pieces = [
            {'name': 'A', 'width': 10, 'height': 10, 'rotate': False},
            {'name': 'B', 'width': 10, 'height': 10, 'rotate': False},
        ]
        result = solve_board_layout(10, 25, 0, pieces)
        self.assertTrue(result['ok'])
        self.assertEqual(result_key(result)[2], (1, 2))
        self.assertEqual(result['pieces'][0]['y'], 0)
        self.assertEqual(result['pieces'][1]['y'], 10)

    def test_gap_between_pieces_and_layers(self):
        pieces = [
            {'name': 'A', 'width': 10, 'height': 6, 'rotate': False},
            {'name': 'B', 'width': 8, 'height': 4, 'rotate': False},
            {'name': 'C', 'width': 5, 'height': 5, 'rotate': False},
        ]
        result = solve_board_layout(30, 30, 2, pieces)
        self.assertTrue(result['ok'])
        # 全部同层：宽 10+8+5+2×2=27≤30，层高 6，占用高度 6
        self.assertEqual(result['used_height'], 6)
        self.assertEqual(result['layer_count'], 1)
        xs = [p['x'] for p in result['pieces']]
        self.assertEqual(xs, [0, 12, 22])  # 相邻片间隔片间距 2

    def test_square_piece_rotation_not_taken(self):
        # 正方形旋转无新几何：旋转标记恒为未旋转
        pieces = [
            {'name': 'A', 'width': 10, 'height': 10, 'rotate': True},
            {'name': 'B', 'width': 6, 'height': 6, 'rotate': True},
        ]
        result = solve_board_layout(30, 30, 1, pieces)
        self.assertTrue(result['ok'])
        self.assertEqual(result_key(result)[3], (0, 0))

    def test_height_insufficient_reports_min_height(self):
        # 每片单独都能放进，但最优排法 49（32 高三片一层、袖子一层）
        # 超过板高 45
        pieces = [
            {'name': '后片', 'width': 40, 'height': 32, 'rotate': False},
            {'name': '左前片', 'width': 20, 'height': 32, 'rotate': True},
            {'name': '右前片', 'width': 20, 'height': 32, 'rotate': True},
            {'name': '袖子A', 'width': 34, 'height': 14, 'rotate': True},
            {'name': '袖子B', 'width': 34, 'height': 14, 'rotate': True},
        ]
        result = solve_board_layout(90, 45, 3, pieces)
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'height')
        self.assertEqual(result['min_height'], 49)
        self.assertEqual(result['layer_count'], 2)
        self.assertNotIn('pieces', result)
        self.assertNotIn('layers', result)

    def test_width_insufficient_single_piece(self):
        # 95 宽不可旋转：任何朝向宽都超板宽 90
        pieces = [
            {'name': '大片', 'width': 95, 'height': 10, 'rotate': False},
            {'name': '小片', 'width': 10, 'height': 10, 'rotate': True},
        ]
        result = solve_board_layout(90, 60, 3, pieces)
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'width')
        self.assertEqual(len(result['unfit_pieces']), 1)
        unfit = result['unfit_pieces'][0]
        self.assertEqual(unfit['index'], 0)
        self.assertFalse(unfit['width_ok'])
        self.assertTrue(unfit['height_ok'])
        self.assertEqual(unfit['min_width'], 95)

    def test_height_insufficient_single_piece(self):
        # 高 70 不可旋转：任何朝向高都超板高 60
        pieces = [
            {'name': '长片', 'width': 10, 'height': 70, 'rotate': False},
            {'name': '小片', 'width': 10, 'height': 10, 'rotate': True},
        ]
        result = solve_board_layout(90, 60, 3, pieces)
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'height')
        unfit = result['unfit_pieces'][0]
        self.assertTrue(unfit['width_ok'])
        self.assertFalse(unfit['height_ok'])
        self.assertEqual(unfit['min_height'], 70)

    def test_width_and_height_jointly_insufficient(self):
        # 6×12 可旋转、板 10×10：不旋转超高、旋转后超宽，
        # 两个朝向各满足一边但没有同一朝向同时满足
        pieces = [
            {'name': '尴尬片', 'width': 6, 'height': 12, 'rotate': True},
            {'name': '小片', 'width': 3, 'height': 3, 'rotate': False},
        ]
        result = solve_board_layout(10, 10, 0, pieces)
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'both')
        unfit = result['unfit_pieces'][0]
        self.assertTrue(unfit['width_ok'])
        self.assertTrue(unfit['height_ok'])

    def test_both_dimensions_insufficient(self):
        # 95×70 不可旋转：宽超板宽 90、高超板高 60，两个方向都不足
        pieces = [
            {'name': '巨片', 'width': 95, 'height': 70, 'rotate': False},
            {'name': '小片', 'width': 10, 'height': 10, 'rotate': True},
        ]
        result = solve_board_layout(90, 60, 3, pieces)
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'both')
        unfit = result['unfit_pieces'][0]
        self.assertFalse(unfit['width_ok'])
        self.assertFalse(unfit['height_ok'])

    def test_exact_fit_boundary(self):
        # 占用高度恰好等于板高、层宽恰好等于板宽：可行
        pieces = [
            {'name': 'A', 'width': 30, 'height': 20, 'rotate': False},
            {'name': 'B', 'width': 28, 'height': 18, 'rotate': False},
        ]
        result = solve_board_layout(60, 40, 2, pieces)
        self.assertTrue(result['ok'])
        # 同层宽 30+28+2=60≤60 高 20；或分层 20+2+18=40≤40；
        # 同层 20 < 40，取一层
        self.assertEqual(result['used_height'], 20)
        self.assertEqual(result['layer_count'], 1)

    def test_six_pieces_enumeration(self):
        # 6 片上限规模：全部 10×10 不可旋转，板宽 30 每层至多 3 片
        pieces = [
            {'name': '片{}'.format(i), 'width': 10, 'height': 10,
             'rotate': False}
            for i in range(6)
        ]
        result = solve_board_layout(30, 30, 0, pieces)
        self.assertTrue(result['ok'])
        self.assertEqual(result['layer_count'], 2)
        self.assertEqual(result['used_height'], 20)
        self.assertEqual(result_key(result)[2], (1, 1, 1, 2, 2, 2))

    def test_random_against_brute_force(self):
        rng = random.Random(20260926)
        for _ in range(200):
            # 少量 6 片上限规模，多数为 2~5 片以控制枚举耗时
            n = 6 if rng.random() < 0.1 else rng.randint(2, 5)
            board_width = rng.randint(5, 40)
            board_height = rng.randint(5, 60)
            gap = rng.randint(0, 4)
            pieces = [{
                'name': '片{}'.format(i),
                'width': rng.randint(2, 30),
                'height': rng.randint(2, 30),
                'rotate': rng.random() < 0.6,
            } for i in range(n)]
            result = solve_board_layout(board_width, board_height, gap, pieces)
            best = brute_force(board_width, board_height, gap, pieces)
            msg = '参数 板{}×{} 间距{} 片{}'.format(
                board_width, board_height, gap, pieces)
            if best is None:
                # 无板宽可行解：必有片任何朝向都放不进
                self.assertFalse(result['ok'], msg=msg)
                self.assertIn('unfit_pieces', result, msg=msg)
                self.assertGreater(len(result['unfit_pieces']), 0, msg=msg)
                continue
            if best[0] > board_height:
                self.assertFalse(result['ok'], msg=msg)
                if 'unfit_pieces' in result:
                    # 有片任何朝向放不进（宽或高），诊断与暴力一致
                    self.assertGreater(len(result['unfit_pieces']), 0, msg=msg)
                else:
                    self.assertEqual(result['reason'], 'height', msg=msg)
                    self.assertEqual(result['min_height'], best[0], msg=msg)
                    self.assertEqual(result['layer_count'], best[1], msg=msg)
                continue
            self.assertTrue(result['ok'], msg=msg)
            self.assertEqual(result_key(result), best[:4], msg=msg)
            # 坐标与朝向组合一致：逐片核对层号、朝向尺寸与位置
            combo = best[4]
            y_by_layer = {}
            y = 0
            for layer in range(1, best[1] + 1):
                y_by_layer[layer] = y
                y += max(combo[i][1] for i, a in enumerate(best[2])
                         if a == layer) + gap
            x_cursor = {}
            for i, piece in enumerate(result['pieces']):
                layer = best[2][i]
                x = x_cursor.get(layer, 0)
                self.assertEqual((piece['x'], piece['y']),
                                 (x, y_by_layer[layer]), msg=msg)
                self.assertEqual((piece['width'], piece['height']),
                                 combo[i][:2], msg=msg)
                self.assertEqual(piece['rotated'], combo[i][2], msg=msg)
                x_cursor[layer] = x + combo[i][0] + gap
                # 每片完整落在板内
                self.assertLessEqual(piece['x'] + piece['width'],
                                     board_width, msg=msg)
                self.assertLessEqual(piece['y'] + piece['height'],
                                     board_height, msg=msg)

    def test_max_pieces_runs_fast(self):
        # 上限规模：6 片全可旋转（4683 种分层 × 64 种朝向）也应快速完成
        pieces = [
            {'name': '片{}'.format(i), 'width': 12 + i, 'height': 20 - i,
             'rotate': True}
            for i in range(6)
        ]
        result = solve_board_layout(50, 50, 2, pieces)
        best = brute_force(50, 50, 2, pieces)
        self.assertEqual(result['ok'], best is not None and best[0] <= 50)
        if result['ok']:
            self.assertEqual(result_key(result), best[:4])


if __name__ == '__main__':
    unittest.main()

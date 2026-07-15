# -*- coding: utf-8 -*-
# 队形检查与修正功能的独立测试工具, 不需要进行任何战斗.
#
# 用法:
#   python src/test_formation.py --offline [截图路径]
#       离线验证比对逻辑: 用一张战斗截图自造"被打乱"的画面,
#       验证 CompareFormation 能正确输出置换关系. 无需开游戏.
#   python src/test_formation.py --capture 输出.png
#       从模拟器截一张图(用于校准坐标/制作模板).
#   python src/test_formation.py --live-swap A B
#       人站在地下城待机画面时, 实际执行一次"格A<->格B"的队形互换
#       (1-6, 顺序: 上排左中右, 下排左中右). 再执行一次即可换回.
import argparse
import json
import os
import subprocess
import sys
import time

import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from script import (FORMATION_CELL_ROIS, FORMATION_MATCH_THRESHOLD,
                    FORMATION_EDIT_ICON_POS, FORMATION_EDIT_ICON_ROI,
                    FORMATION_EDIT_ON_TEMPLATE, FORMATION_EDIT_OFF_TEMPLATE,
                    FORMATION_SLOT_CENTER_POS,
                    CropFormationCells, CompareFormation, PermutationToSwaps)
from utils import LoadTemplateImage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_TEST_IMAGE = os.path.join(ROOT, "test_combat_screenshot.png")


def _load_adb():
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)["GENERAL"]
    return cfg["EMU_PATH"], cfg["ADB_ADRESS"]


def adb_screenshot():
    adb, addr = _load_adb()
    out = subprocess.run([adb, "-s", addr, "exec-out", "screencap", "-p"],
                         capture_output=True, timeout=10).stdout
    import numpy as np
    img = cv2.imdecode(np.frombuffer(out, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError("截图失败, 请确认模拟器已启动且ADB地址正确.")
    return img


def adb_tap(x, y):
    adb, addr = _load_adb()
    subprocess.run([adb, "-s", addr, "shell", "input", "tap", str(x), str(y)],
                   timeout=10)


def adb_back():
    adb, addr = _load_adb()
    subprocess.run([adb, "-s", addr, "shell", "input", "keyevent", "4"],
                   timeout=10)


def test_offline(image_path):
    img = cv2.imread(image_path)
    if img is None:
        print(f"无法读取截图: {image_path}")
        return 1
    ref = CropFormationCells(img)

    print("== 测试1: 原图对原图, 期望判定为'无变化' ==")
    perm, conf = CompareFormation(ref, img)
    print(f"置换: {perm}  最低匹配度: {conf:.3f}")
    ok1 = (perm == list(range(6))) and conf >= FORMATION_MATCH_THRESHOLD
    print("通过" if ok1 else "失败")

    print("== 测试2: 人工互换格2与格5(索引1/4), 期望检出该互换 ==")
    img2 = img.copy()
    x1, y1, w1, h1 = FORMATION_CELL_ROIS[1]
    x2, y2, w2, h2 = FORMATION_CELL_ROIS[4]
    a = img[y1:y1 + h1, x1:x1 + w1].copy()
    b = img[y2:y2 + h2, x2:x2 + w2].copy()
    img2[y1:y1 + h1, x1:x1 + w1] = b
    img2[y2:y2 + h2, x2:x2 + w2] = a
    perm2, conf2 = CompareFormation(ref, img2)
    swaps = PermutationToSwaps(perm2)
    print(f"置换: {perm2}  最低匹配度: {conf2:.3f}")
    print("换回所需操作: " + ", ".join(f"格{a+1}<->格{b+1}" for a, b in swaps))
    ok2 = (perm2 == [0, 4, 2, 3, 1, 5]) and conf2 >= FORMATION_MATCH_THRESHOLD
    print("通过" if ok2 else "失败")

    print("== 测试3: 无面板画面(纯色图), 期望置信度低于阈值而被跳过 ==")
    img3 = img.copy()
    img3[:] = 30
    perm3, conf3 = CompareFormation(ref, img3)
    print(f"置换: {perm3}  最低匹配度: {conf3:.3f}")
    ok3 = conf3 < FORMATION_MATCH_THRESHOLD
    print("通过" if ok3 else "失败")

    print("== 测试4: 意志力<50蓝底 + 格2/格5互换的复合情况, 期望仍正确检出 ==")
    # 模拟面板背景变为深蓝(意志力低于50): 暗色像素染蓝, 文字保持原样.
    img4 = img.copy()
    for x, y, w, h in FORMATION_CELL_ROIS:
        cell = img4[y - 40:y + h + 90, x:x + w]  # 整个面板区域都染色, 不只名字行
        gray = cv2.cvtColor(cell, cv2.COLOR_BGR2GRAY)
        bg = gray < 140
        cell[bg] = (90, 35, 25)  # BGR 深蓝
    x1, y1, w1, h1 = FORMATION_CELL_ROIS[1]
    x2, y2, w2, h2 = FORMATION_CELL_ROIS[4]
    a = img4[y1:y1 + h1, x1:x1 + w1].copy()
    b = img4[y2:y2 + h2, x2:x2 + w2].copy()
    img4[y1:y1 + h1, x1:x1 + w1] = b
    img4[y2:y2 + h2, x2:x2 + w2] = a
    perm4, conf4 = CompareFormation(ref, img4)
    swaps4 = PermutationToSwaps(perm4)
    print(f"置换: {perm4}  最低匹配度: {conf4:.3f}")
    print("换回所需操作: " + ", ".join(f"格{a+1}<->格{b+1}" for a, b in swaps4))
    ok4 = (perm4 == [0, 4, 2, 3, 1, 5]) and conf4 >= FORMATION_MATCH_THRESHOLD
    print("通过" if ok4 else "失败")

    return 0 if (ok1 and ok2 and ok3 and ok4) else 1


def adb_swipe(x1, y1, x2, y2, ms=800):
    adb, addr = _load_adb()
    subprocess.run([adb, "-s", addr, "shell", "input", "swipe",
                    str(x1), str(y1), str(x2), str(y2), str(ms)], timeout=10)


def _check_icon(screen, template):
    # 在编辑图标ROI内匹配模板, 返回匹配度.
    tpl = LoadTemplateImage(template)
    x, y, w, h = FORMATION_EDIT_ICON_ROI[0]
    res = cv2.matchTemplate(screen[y:y+h, x:x+w], tpl, cv2.TM_CCOEFF_NORMED)
    return float(res.max())


def live_swap(slot_a, slot_b):
    # 与 script.FixFormation 相同的流程: 开编辑模式 -> 拖拽互换 -> 关编辑模式,
    # 并用 CompareFormation 验证互换结果. 人站在地下城待机画面时运行.
    ref = CropFormationCells(adb_screenshot())

    scn = adb_screenshot()
    m_off = _check_icon(scn, FORMATION_EDIT_OFF_TEMPLATE)
    print(f"队列编辑按钮(白色)匹配度: {m_off:.2f}")
    if m_off < 0.8:
        print("未找到队列编辑按钮, 中止. 请确认在地下城待机画面且底部面板可见.")
        return 1
    adb_tap(*FORMATION_EDIT_ICON_POS)
    time.sleep(1.2)
    m_on = _check_icon(adb_screenshot(), FORMATION_EDIT_ON_TEMPLATE)
    print(f"编辑模式(金色)匹配度: {m_on:.2f}")
    if m_on < 0.8:
        print("未能进入队列编辑模式, 中止.")
        return 1

    ax, ay = FORMATION_SLOT_CENTER_POS[slot_a - 1]
    bx, by = FORMATION_SLOT_CENTER_POS[slot_b - 1]
    adb_swipe(ax, ay, bx, by)
    time.sleep(1.2)

    adb_tap(*FORMATION_EDIT_ICON_POS)  # 退出编辑模式
    time.sleep(1.0)

    perm, conf = CompareFormation(ref, adb_screenshot())
    swaps = PermutationToSwaps(perm)
    print(f"互换后检测: 置换 {perm}  最低匹配度 {conf:.3f}")
    print("检出的变化: " + (", ".join(f"格{a+1}<->格{b+1}" for a, b in swaps) or "无"))
    expected = sorted([(min(slot_a, slot_b) - 1, max(slot_a, slot_b) - 1)])
    actual = sorted([(min(a, b), max(a, b)) for a, b in swaps])
    if actual == expected and conf >= FORMATION_MATCH_THRESHOLD:
        print(f"通过: 格{slot_a}<->格{slot_b} 互换已执行且被正确检出. 再运行一次相同命令即可换回.")
        return 0
    print("失败: 检测结果与预期不符, 请人工确认游戏画面.")
    return 1


def main():
    ap = argparse.ArgumentParser(description="队形修正功能测试(无需战斗)")
    ap.add_argument("--offline", nargs="?", const=DEFAULT_TEST_IMAGE, default=None,
                    metavar="截图", help="离线验证比对逻辑")
    ap.add_argument("--capture", metavar="输出.png", help="截取模拟器当前画面")
    ap.add_argument("--live-swap", nargs=2, type=int, metavar=("A", "B"),
                    help="在地下城待机画面实际互换两个格位(1-6)")
    args = ap.parse_args()

    if args.offline:
        sys.exit(test_offline(args.offline))
    if args.capture:
        cv2.imwrite(args.capture, adb_screenshot())
        print(f"已保存: {args.capture}")
        return
    if args.live_swap:
        sys.exit(live_swap(*args.live_swap))
    ap.print_help()


if __name__ == "__main__":
    main()

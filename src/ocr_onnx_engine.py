# ocr_onnx_engine.py
# -*- coding: utf-8 -*-
"""
一个最小可用的 PaddleOCR(ONNX) 推理引擎：det(文本检测) + rec(文本识别)。
输入：OpenCV 读取/截图得到的 BGR numpy 图像（H,W,3）
输出：每个文本框的四点坐标 + 文本内容 + 置信度，支持指定 ROI 加速。

该文件设计目标：
1) 方便迁移进你的“ADB截图 + 状态机脚本”
2) 只初始化一次 det/rec session，后续随用随调
3) 支持整图 OCR，也支持 rois=[[x,y,w,h], ...] 分区域 OCR 加速
"""

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

import onnxruntime as ort
import pyclipper


# =========================
# 1. 字符表/字典加载与对齐
# =========================

def read_keys(keys_path: str) -> List[str]:
    """
    读取 keys.txt（一般为 PaddleOCR 的字典文件）
    说明：
    - PaddleOCR 的 CTC 识别通常有一个 blank 类（索引 0）
    - keys.txt 通常只包含可见字符，不包含 blank
    - 因此我们会自动在最前面插入 '<blank>'
    """
    chars: List[str] = []
    with open(keys_path, "r", encoding="utf-8") as f:
        for line in f:
            ch = line.rstrip("\n")
            if ch != "":
                chars.append(ch)
    return ["<blank>"] + chars


def align_char_dict(idx2char: List[str], num_classes: int) -> List[str]:
    """
    识别模型输出维度 num_classes 可能与你的 keys.txt 数量不完全一致。
    常见原因：
    - PaddleOCR 训练时 use_space_char=True，会额外增加一个“空格”类别
    - 或者模型导出时包含了额外字符/未知字符

    本函数做“温和对齐”，尽量让 idx2char 长度匹配输出维度：
    - 如果差 1：优先补一个空格
    - 如果多 1：且末尾是空格，尝试去掉
    - 其他复杂情况：原样返回（你可以根据实际字典进一步定制）
    """
    if len(idx2char) == num_classes:
        return idx2char

    # 情况A：字典比模型少 1 类：常见为缺少 ' '
    if len(idx2char) == num_classes - 1:
        if " " not in idx2char:
            return idx2char + [" "]
        return idx2char + ["<unk>"]

    # 情况B：字典比模型多 1 类：常见为末尾多了一个 ' '
    if len(idx2char) == num_classes + 1 and idx2char and idx2char[-1] == " ":
        return idx2char[:-1]

    return idx2char


def create_session(onnx_path: str) -> ort.InferenceSession:
    """
    创建 ONNXRuntime Session，优先使用 CUDA（如果可用），否则使用 CPU。
    注意：
    - Windows 环境下是否有 CUDAExecutionProvider 取决于你安装的 onnxruntime 版本
    """
    providers = ort.get_available_providers()
    prefer = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    use = [p for p in prefer if p in providers] or providers
    return ort.InferenceSession(onnx_path, providers=use)


# =========================
# 2. 文本检测（DB 类检测后处理）
# =========================
# PaddleOCR DB 检测常用的归一化参数（RGB）
DET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
DET_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def resize_det_image(img_bgr: np.ndarray, limit_side_len: int = 960):
    """
    检测网络通常要求输入尺寸为 32 的倍数，并且为了速度会把长边限制在 limit_side_len 内。
    返回：
    - resized: 缩放后的图像（BGR）
    - ratio_h/ratio_w: 新旧尺寸比例，用于把检测框映射回原图坐标
    """
    h, w = img_bgr.shape[:2]
    ratio = 1.0
    if max(h, w) > limit_side_len:
        ratio = float(limit_side_len) / max(h, w)

    # DB 检测通常要求 H/W 为 32 的倍数
    new_h = int(round(h * ratio / 32) * 32)
    new_w = int(round(w * ratio / 32) * 32)
    new_h = max(new_h, 32)
    new_w = max(new_w, 32)

    resized = cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    ratio_h = new_h / float(h)
    ratio_w = new_w / float(w)
    return resized, ratio_h, ratio_w


def det_preprocess(img_bgr: np.ndarray) -> np.ndarray:
    """
    检测模型预处理：
    - BGR -> RGB
    - /255
    - (img-mean)/std
    - HWC -> NCHW
    """
    img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    img = (img - DET_MEAN) / DET_STD
    x = img.transpose(2, 0, 1)[None, ...].astype(np.float32)
    return x


def order_points_clockwise(pts: np.ndarray) -> np.ndarray:
    """
    将 4 个点排序为 [左上, 右上, 右下, 左下]
    便于后续透视变换与稳定输出
    """
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]  # 左上
    rect[2] = pts[np.argmax(s)]  # 右下
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # 右上
    rect[3] = pts[np.argmax(diff)]  # 左下
    return rect


def polygon_score(pred: np.ndarray, contour: np.ndarray) -> float:
    """
    计算轮廓区域在概率图 pred 上的平均得分，作为 box_score。
    pred: (H,W) 的概率图（sigmoid 后）
    contour: (N,2) 轮廓点
    """
    mask = np.zeros(pred.shape, dtype=np.uint8)
    cv2.fillPoly(mask, [contour.astype(np.int32)], 1)
    return float(pred[mask == 1].mean()) if np.any(mask == 1) else 0.0


def unclip_box(box: np.ndarray, unclip_ratio: float = 2.0) -> Optional[np.ndarray]:
    """
    DB 检测后处理“扩张”操作（unclip），让文本框更贴合文本边缘。
    - 通过 pyclipper 对多边形做 offset 扩张
    - 再用 minAreaRect 取最小外接矩形（四点框）
    """
    poly = box.reshape(-1, 2)
    area = cv2.contourArea(poly.astype(np.float32))
    if area < 1.0:
        return None
    perimeter = cv2.arcLength(poly.astype(np.float32), True)
    if perimeter < 1.0:
        return None

    # 扩张距离：area * ratio / perimeter（经典 DB unclip 公式）
    distance = (area * unclip_ratio) / (perimeter + 1e-6)

    pc = pyclipper.PyclipperOffset()
    pc.AddPath(poly.tolist(), pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
    expanded = pc.Execute(distance)
    if not expanded:
        return None

    expanded = np.array(expanded[0], dtype=np.float32)
    if expanded.shape[0] < 4:
        return None

    rect = cv2.minAreaRect(expanded)
    points = cv2.boxPoints(rect)
    return points.astype(np.float32)


def boxes_from_db_map(
    pred: np.ndarray,
    bin_thresh: float = 0.3,
    box_thresh: float = 0.6,
    unclip_ratio: float = 2.0
):
    """
    从 DB 概率图 pred 中提取文本框：
    1) pred > bin_thresh 得到二值图
    2) findContours 得到候选轮廓
    3) 对每个轮廓计算平均得分（box_score），低于 box_thresh 则丢弃
    4) 对框做 unclip 扩张，并输出 4 点框

    返回：[(box(4,2), det_score), ...]
    """
    bitmap = (pred > bin_thresh).astype(np.uint8) * 255
    contours, _ = cv2.findContours(bitmap, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    boxes = []
    for cnt in contours:
        if cnt.shape[0] < 3:
            continue

        rect = cv2.minAreaRect(cnt)
        box = cv2.boxPoints(rect).astype(np.float32)
        box = order_points_clockwise(box)

        score = polygon_score(pred, cnt[:, 0, :])
        if score < box_thresh:
            continue

        expanded = unclip_box(box, unclip_ratio=unclip_ratio)
        if expanded is None:
            continue

        expanded = order_points_clockwise(expanded)
        boxes.append((expanded, score))
    return boxes


# =========================
# 3. 文本识别（CTC 解码）
# =========================
# PaddleOCR rec 常见归一化参数（RGB）
REC_MEAN = np.array([0.5, 0.5, 0.5], dtype=np.float32)
REC_STD  = np.array([0.5, 0.5, 0.5], dtype=np.float32)


def get_rotate_crop_image(img_bgr: np.ndarray, points: np.ndarray) -> np.ndarray:
    """
    根据 4 点框从原图中裁剪出文本区域：
    - 透视变换把四边形拉正为矩形
    - 如果裁剪结果“高度/宽度”过大，说明文本可能是竖排/旋转，做一次旋转
    """
    points = order_points_clockwise(points.astype(np.float32))
    tl, tr, br, bl = points

    w1 = np.linalg.norm(tr - tl)
    w2 = np.linalg.norm(br - bl)
    h1 = np.linalg.norm(bl - tl)
    h2 = np.linalg.norm(br - tr)

    dst_w = int(max(w1, w2))
    dst_h = int(max(h1, h2))
    dst_w = max(dst_w, 1)
    dst_h = max(dst_h, 1)

    dst = np.array([[0, 0], [dst_w - 1, 0], [dst_w - 1, dst_h - 1], [0, dst_h - 1]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(points, dst)
    warped = cv2.warpPerspective(
        img_bgr, M, (dst_w, dst_h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE
    )

    # 经验规则：高宽比太大时旋转一下更利于识别
    if dst_h / float(dst_w + 1e-6) > 1.5:
        warped = cv2.rotate(warped, cv2.ROTATE_90_CLOCKWISE)

    return warped


def rec_resize_norm_img(img_bgr: np.ndarray, rec_img_h: int = 48, rec_img_w: int = 320) -> np.ndarray:
    """
    识别模型预处理：
    - BGR -> RGB
    - /255
    - 固定高度 rec_img_h（通常 48），宽度按比例缩放并右侧 padding 到 rec_img_w（通常 320）
    - (img-mean)/std
    - HWC -> NCHW
    """
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    h, w = img_rgb.shape[:2]
    ratio = w / float(h + 1e-6)

    resized_w = int(math.ceil(rec_img_h * ratio))
    resized_w = min(resized_w, rec_img_w)

    img_resized = cv2.resize(img_rgb, (resized_w, rec_img_h), interpolation=cv2.INTER_LINEAR)

    padding = np.zeros((rec_img_h, rec_img_w, 3), dtype=np.float32)
    padding[:, :resized_w, :] = img_resized

    padding = (padding - REC_MEAN) / REC_STD
    x = padding.transpose(2, 0, 1)[None, ...].astype(np.float32)
    return x


def ctc_decode(probs: np.ndarray, idx2char: List[str]) -> Tuple[str, float]:
    """
    CTC 解码：
    - probs: (1, T, C)（最常见）或某些导出为 (1, C, T)
    - 先对 logits 做 softmax（若看起来不是概率）
    - argmax 得到每个 time step 的类别
    - 去掉 blank（索引0）以及连续重复
    - 输出文本与平均置信度
    """
    if probs.ndim != 3:
        raise ValueError(f"识别输出维度异常: {probs.shape}")

    C = len(idx2char)

    # 适配输出维度
    if probs.shape[-1] == C:
        p = probs[0]  # (T,C)
    elif probs.shape[1] == C:
        # (1,C,T) -> (T,C)
        p = probs[0].transpose(1, 0)
    else:
        raise ValueError(f"无法匹配字典大小({C})与输出形状{probs.shape}")

    # 如果看起来像 logits（范围大），则做 softmax
    if p.max() > 1.2 or p.min() < -0.2:
        e = np.exp(p - p.max(axis=1, keepdims=True))
        p = e / (e.sum(axis=1, keepdims=True) + 1e-9)

    pred_idx = p.argmax(axis=1)
    pred_prob = p.max(axis=1)

    last = -1
    text_chars = []
    confs = []

    for i, idx in enumerate(pred_idx.tolist()):
        # blank 类直接跳过，但仍更新 last
        if idx == 0:
            last = idx
            continue
        # 连续重复去重（CTC 规则）
        if idx == last:
            continue
        text_chars.append(idx2char[idx])
        confs.append(float(pred_prob[i]))
        last = idx

    out_text = "".join(text_chars)
    out_conf = float(np.mean(confs)) if confs else 0.0
    return out_text, out_conf


# =========================
# 4. 统一输出结构
# =========================

@dataclass
class OcrResult:
    """
    单条 OCR 结果：
    - text: 识别文本
    - conf: 识别置信度（粗略，来自 CTC 的均值）
    - det_score: 检测得分（来自 DB 的 box_score）
    - box: (4,2) 四点框坐标（原图坐标系）
    """
    text: str
    conf: float
    det_score: float
    box: np.ndarray  # float32 (4,2)

    def center(self) -> Tuple[int, int]:
        """
        返回文本框中心点，常用于点击。
        """
        c = self.box.mean(axis=0)
        return int(round(c[0])), int(round(c[1]))


# =========================
# 5. 对外主类：OnnxPaddleOCR
# =========================

class OnnxPaddleOCR:
    """
    对外 OCR 引擎类：
    - __init__ 只做一次 session 初始化
    - ocr(img, rois=...) 可对整图或多个 ROI 做“检测+识别”
    """

    def __init__(self, det_path: str, rec_path: str, keys_path: str):
        # 初始化 ONNX session（只做一次）
        self.det_sess = create_session(det_path)
        self.rec_sess = create_session(rec_path)

        # 加载字典（包含 blank）
        self.idx2char = read_keys(keys_path)

        # 记录输入名，避免每次 get_inputs()
        self.det_input = self.det_sess.get_inputs()[0].name
        self.rec_input = self.rec_sess.get_inputs()[0].name

    def det_infer(
        self,
        img_bgr: np.ndarray,
        limit_side_len: int = 960,
        bin_thresh: float = 0.3,
        box_thresh: float = 0.6,
        unclip_ratio: float = 2.0
    ):
        """
        仅做检测，返回文本框列表（已映射回原图坐标系）：
        返回：[(box(4,2), det_score), ...]
        """
        # 先缩放到适合检测的尺寸
        resized, ratio_h, ratio_w = resize_det_image(img_bgr, limit_side_len=limit_side_len)

        # 预处理并推理
        x = det_preprocess(resized)
        out = self.det_sess.run(None, {self.det_input: x})[0]

        # 兼容不同导出形状：常见为 (1,1,H,W) 或 (1,H,W,1) 或 (1,H,W)
        if out.ndim == 4:
            if out.shape[1] == 1:
                pred = out[0, 0]
            elif out.shape[-1] == 1:
                pred = out[0, :, :, 0]
            else:
                pred = out[0, 0]
        elif out.ndim == 3:
            pred = out[0]
        else:
            raise ValueError(f"检测输出维度异常: {out.shape}")

        pred = pred.astype(np.float32)

        # 若输出尺寸与 resized 不一致，进行 resize 对齐
        if pred.shape[:2] != resized.shape[:2]:
            pred = cv2.resize(pred, (resized.shape[1], resized.shape[0]))

        # 若看起来像 logits，则做 sigmoid
        if pred.max() > 1.2 or pred.min() < -0.2:
            pred = 1.0 / (1.0 + np.exp(-pred))

        # DB 后处理提框
        boxes = boxes_from_db_map(pred, bin_thresh=bin_thresh, box_thresh=box_thresh, unclip_ratio=unclip_ratio)

        # 把框映射回原图坐标
        final = []
        for box, score in boxes:
            box[:, 0] = np.clip(box[:, 0] / ratio_w, 0, img_bgr.shape[1] - 1)
            box[:, 1] = np.clip(box[:, 1] / ratio_h, 0, img_bgr.shape[0] - 1)
            final.append((box, float(score)))

        # 排序：先按 y 再按 x，保证输出顺序更接近“阅读顺序”
        final.sort(key=lambda b: (b[0][:, 1].mean(), b[0][:, 0].mean()))
        return final

    def rec_infer(self, crop_bgr: np.ndarray, rec_img_h: int = 48, rec_img_w: int = 320) -> Tuple[str, float]:
        """
        仅做识别：输入裁剪后的单行/单块文本图像，输出 (text, conf)。
        """
        x = rec_resize_norm_img(crop_bgr, rec_img_h=rec_img_h, rec_img_w=rec_img_w)
        out = self.rec_sess.run(None, {self.rec_input: x})[0]

        # 对齐字典长度与输出类别数
        idx2char = align_char_dict(self.idx2char, int(out.shape[-1]))
        return ctc_decode(out.astype(np.float32), idx2char)

    def ocr(
        self,
        img_bgr: np.ndarray,
        rois: Optional[List[List[int]]] = None,
        limit_side_len: int = 960,
        bin_thresh: float = 0.3,
        box_thresh: float = 0.6,
        unclip_ratio: float = 2.0,
        min_rec_conf: float = 0.0
    ) -> List[OcrResult]:
        """
        执行完整 OCR（检测 + 逐框识别）。

        参数：
        - img_bgr: 原始图像（BGR）
        - rois: 可选，ROI 列表，每个 ROI 为 [x,y,w,h]
               若提供，则对每个 ROI 单独做 det+rec，再把坐标偏移回原图。
               用于加速：不要每次对整张 900x1600 做 det。
        - min_rec_conf: 识别结果的最低置信度阈值（过低的结果过滤掉）

        返回：
        - List[OcrResult]
        """
        results: List[OcrResult] = []

        # 情况1：不指定 ROI，直接全图 det + rec
        if not rois:
            boxes = self.det_infer(img_bgr, limit_side_len, bin_thresh, box_thresh, unclip_ratio)
            for box, det_score in boxes:
                crop = get_rotate_crop_image(img_bgr, box)
                text, conf = self.rec_infer(crop)
                if conf >= min_rec_conf and text.strip() != "":
                    results.append(OcrResult(text=text, conf=conf, det_score=det_score, box=box))
            return results

        # 情况2：指定 ROI，逐个 ROI 处理，并把坐标映射回原图
        H, W = img_bgr.shape[:2]
        for (x, y, w, h) in rois:
            # ROI 裁剪边界保护
            x0 = max(0, int(x))
            y0 = max(0, int(y))
            x1 = min(W, x0 + max(1, int(w)))
            y1 = min(H, y0 + max(1, int(h)))

            roi_img = img_bgr[y0:y1, x0:x1].copy()
            boxes = self.det_infer(roi_img, limit_side_len, bin_thresh, box_thresh, unclip_ratio)

            for box, det_score in boxes:
                # 把 ROI 内坐标偏移回原图坐标
                box[:, 0] += x0
                box[:, 1] += y0

                crop = get_rotate_crop_image(img_bgr, box)
                text, conf = self.rec_infer(crop)

                if conf >= min_rec_conf and text.strip() != "":
                    results.append(OcrResult(text=text, conf=conf, det_score=det_score, box=box))

        results.sort(key=lambda r: (r.box[:, 1].mean(), r.box[:, 0].mean()))
        return results

    def draw_boxes(self, img_bgr: np.ndarray, results: List[OcrResult]) -> np.ndarray:
        """
        调试用途：把检测到的文本框画出来（绿色四边形）。
        """
        vis = img_bgr.copy()
        for r in results:
            b = r.box.astype(np.int32)
            cv2.polylines(vis, [b], True, (0, 255, 0), 2)
        return vis

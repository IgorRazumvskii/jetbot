"""Генерация ArUco-маркера для печати в точном физическом размере.

    ros2 run aruco_approach make_marker --id 0 --size-mm 100 --out marker_0.pdf

PDF/PNG сохраняются с нужным DPI: при печати в масштабе 100% («реальный
размер») чёрный квадрат маркера будет ровно size-mm. Белая рамка вокруг
нужна детектору — не обрезайте её. Параметр marker_size узла = size-mm / 1000.
"""
import argparse

import cv2
import numpy as np

from aruco_approach.detector import generate_marker


def main(args=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dict', default='DICT_4X4_50')
    parser.add_argument('--id', type=int, default=0)
    parser.add_argument('--size-mm', type=float, default=100.0,
                        help='сторона чёрного квадрата маркера, мм')
    parser.add_argument('--border-mm', type=float, default=20.0, help='белая рамка, мм')
    parser.add_argument('--dpi', type=int, default=300)
    parser.add_argument('--out', default=None, help='.pdf или .png')
    opts = parser.parse_args(args)

    px_per_mm = opts.dpi / 25.4
    side = int(round(opts.size_mm * px_per_mm))
    border = int(round(opts.border_mm * px_per_mm))
    marker = generate_marker(opts.dict, opts.id, side)
    page = np.full((side + 2 * border, side + 2 * border), 255, dtype=np.uint8)
    page[border:border + side, border:border + side] = marker
    label = f'{opts.dict} id={opts.id} size={opts.size_mm:g} mm'
    cv2.putText(page, label, (border, page.shape[0] - border // 3), cv2.FONT_HERSHEY_SIMPLEX,
                max(0.5, border / 120.0), 128, max(1, border // 60), cv2.LINE_AA)

    out = opts.out or f'aruco_{opts.dict}_id{opts.id}_{opts.size_mm:g}mm.pdf'
    try:
        from PIL import Image
        Image.fromarray(page).save(out, resolution=opts.dpi, dpi=(opts.dpi, opts.dpi))
    except ImportError:
        if out.endswith('.pdf'):
            out = out[:-4] + '.png'
        cv2.imwrite(out, page)
        print('PIL не найден: сохранён PNG без DPI, при печати задайте размер вручную')
    print(f'{out}: {label}; marker_size = {opts.size_mm / 1000.0:g} м')


if __name__ == '__main__':
    main()

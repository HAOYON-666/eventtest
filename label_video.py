import cv2, time
import os, shutil, json, random, sys, logging, glob
from pprint import pprint
from collections import defaultdict
import logging 
from pathlib import Path
from queue import Queue
import argparse
import copy

showimage = None
RECTS_CACHE = None
SUFFIXS = ['.avi','.mkv', '.mov', '.mp4']

class ShowImage:
    def __init__(self, window_name, img_ori):
        self.drawing = False  # 如果按下鼠标，则为True
        self.tlx, self.tly = -1, -1
        self.rects = []  # 矩形区域
        self.window_name = window_name
        self.img_labeling = img_ori # 中间框图用来保存框
        self.img_begin = img_ori.copy()# 原始图用来回退
        self.img_moving = None # 鼠标移动时显示目标框

    def mouse_down(self, x, y):
        print("in down")
        self.drawing = True
        self.tlx = x
        self.tly = y

    def mouse_move(self, x, y):
        print("in move")
        self.img_moving = self.img_labeling.copy()
        cv2.rectangle(self.img_moving, (self.tlx, self.tly), (x, y), (0, 255, 0), 2)
        cv2.imshow(self.window_name, self.img_moving)

    def mouse_up(self, x, y):
        print("in up")
        rect = (self.tlx, self.tly, x, y)
        cv2.rectangle(self.img_labeling, (self.tlx, self.tly), (x, y), (0, 255, 0), 2)
        self.drawing = False
        self.rects.append(rect)
        cv2.imshow(self.window_name, self.img_labeling)

    def fresh_rects(self, rects):
        self.rects = rects
        self._fresh_labeling_img()

    def _fresh_labeling_img(self):
        self.img_labeling = self.img_begin.copy()
        for rect in self.rects:
            cv2.rectangle(self.img_labeling, (rect[0], rect[1]), (rect[2], rect[3]), (0,255,0), 2)
        self.img_moving = self.img_labeling
        cv2.imshow(self.window_name, self.img_labeling)

    def show_drawing(self):
        cv2.imshow(self.window_name, self.img_moving)

    def show_labeling(self):
        cv2.imshow(self.window_name, self.img_labeling)

    def back(self, x, y):
        if len(self.rects) == 0:
            logging.info("没有目标无法回退")
            return
        for rect in self.rects:
            if self._check_mouse_in_box(rect, x, y):
                self.rects.remove(rect)
                break
            else:
                self.rects.pop()
                break
        self._fresh_labeling_img()
    
    def _check_mouse_in_box(self, rect, x, y):
        if rect[0] < x < rect[2] and rect[1] < y < rect[3]:
            return True
        return False

def draw_rectangle(event, x, y, flags, param):
    global showimage
    if event == cv2.EVENT_LBUTTONDOWN:
        showimage.mouse_down(x, y)
    elif event == cv2.EVENT_MOUSEMOVE:
        if showimage.drawing:
            showimage.mouse_move(x, y)
    elif event == cv2.EVENT_LBUTTONUP:
        showimage.mouse_up(x, y)
    elif event == cv2.EVENT_MBUTTONDOWN:
        showimage.back(x,y)

class FrameCache():
    def __init__(self, size, frame_interval, w_ratio, h_ratio):
        self.q = Queue(size)
        self.index = 0
        self.frame_id = 1
        self.frameid2box = defaultdict(list)
        self.frame_interval = frame_interval
        self.w_ratio = w_ratio
        self.h_ratio = h_ratio

    def get_size(self):
        return self.q.qsize()
        
    def cache_frame(self, showimage):
        if self.q.full():
            old_show_image = self.q.get()
            self.frameid2box[self.frame_id] = self.resize_box(old_show_image.rects)
            self.frame_id += self.frame_interval
        self.q.put(showimage)

    def back_one(self):
        if -self.index < self.q.qsize():
            self.index -= 1
        before = self.q.queue[self.index]
        print(f"current index {self.index}")
        return  before

    def forward_one(self):
        if self.index < -1:
            self.index += 1
        after = self.q.queue[self.index]
        print(f"current index {self.index}")
        return after
    
    def save_label(self, save_path):
        while not self.q.empty():
            showimage = self.q.get()
            self.frameid2box[str(self.frame_id)] = self.resize_box(showimage.rects)
            self.frame_id += self.frame_interval
        with open(save_path, "w") as f:
            json.dump(self.frameid2box, f, indent=4)

    def resize_box(self, rects):
        res = []
        for rect in rects:
            res.append([rect[0]*self.w_ratio, rect[1]*self.h_ratio, rect[2]*self.w_ratio, rect[3]*self.h_ratio])
        return res

def process_video(video_path, args):
    global showimage
    window_name = "image"

    label_path = Path(video_path).with_suffix(".json")
    print("load_video")
    cap = cv2.VideoCapture(video_path)
    # 获取视频帧的宽度和高度
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    w_ratio = frame_width / args.window_width
    h_ratio = frame_height / args.window_height

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, args.window_width, args.window_height)
    cv2.setMouseCallback(window_name, draw_rectangle)
    frame_id = 1
    cache = FrameCache(50, args.frame_interval, w_ratio, h_ratio)
    # 初始化
    ret, frame = cap.read()
    frame = cv2.resize(frame, (args.window_width, args.window_height))
    showimage = ShowImage(window_name=window_name, img_ori=frame)
    showimage.show_labeling()
    # 循环后边的帧
    is_new = True
    while cap.isOpened():
        key = cv2.waitKey(1000) & 0xFF 
        # print(key)
        if key == 115:
            if cache.index == 0:
                if is_new:
                    cache.cache_frame(showimage) # 按下下一帧在保存前一帧
                    RECTS_CACHE = copy.deepcopy(showimage.rects)
                while not (frame_id % args.frame_interval == 0):
                    ret, frame = cap.read()
                    print(frame_id)
                    frame_id += 1
                ret, frame = cap.read()
                frame_id += 1
                if ret:
                    frame = cv2.resize(frame, (args.window_width, args.window_height))
                    showimage = ShowImage(window_name=window_name, img_ori=frame)
                    showimage.fresh_rects(RECTS_CACHE)
                    current_img_bk = showimage
                    showimage.show_labeling()
                    is_new = True
                else:
                    cap.release()

            if cache.index == -1:
                cache.index = 0
                showimage = current_img_bk
                showimage.show_labeling()
                is_new = True

            if cache.index < -1:
                showimage = cache.forward_one()
                showimage.show_labeling()
                is_new = False

        if key == 97:
            if cache.get_size() < 1:
                print(f"cache length : {cache.size}")
                continue
            showimage = cache.back_one()
            showimage.show_labeling()
            is_new = False
    
    cache.save_label(label_path)
    print(label_path)

def parse_args():
    parser = argparse.ArgumentParser("")
    parser.add_argument("--video_dir", type=str, default="/home/user/Desktop/22_大货车禁行/大货车禁行/01_第一批", help="视频文件夹路径")
    parser.add_argument("--frame_interval", type=int, default=3, help="帧间隔")
    parser.add_argument("--window_width", type=int, default=1920, help="视频窗口的宽度")
    parser.add_argument("--window_height", type=int, default=1080, help="视频窗口的高度")
    return parser.parse_args()

def main(args):
    video_paths = [i for i in glob.glob(os.path.join(args.video_dir, "*.*")) if Path(i).suffix in SUFFIXS]
    for video_path  in video_paths:
        process_video(video_path=video_path, args=args)
        cv2.destroyAllWindows()

if __name__=='__main__':
    args = parse_args()
    main(args)
import os, shutil, json, random, sys, logging, glob
from pprint import pprint
from collections import defaultdict 
import ffmpeg 
from pathlib import Path
import numpy as np
import pandas as pd
import re
import logging 
from PIL import Image, ImageDraw
from .general import GlobalConfig

class GatherRes():

    def __init__(self, log_paths, test_dir, test_config):
        self.df = {
            "场景" : [test_dir.split('/')[-1]],
            "参数" : [test_config],
            "视频名" : [None],
            "视频时长" : [None],
            "报警数量" : ["="],
            "正确报警数量" : [None],
            "正报重复数量" : [None],
            "错误报警数量" : [None],
            "误报重复数量" : [None],
            "llm修正-正确报警数量" : [None],
            "llm修正-正报重复数量" : [None],
            "llm修正-错误报警数量" : [None],
            "llm修正-误报重复数量" : [None],
            "漏报原因分析" : [None]
        }
        self.use_llm = False
        self.result_dir = os.path.dirname(log_paths[0])
        # null_warning 文件路径
        null_warning_dir = os.path.dirname(os.path.dirname(log_paths[0]))
        time_stamp = re.search(r'(\d+-\d+)', os.path.basename(os.path.dirname(log_paths[0]))).group(1)
        self.null_warning_path = os.path.join(null_warning_dir, f"{time_stamp}_null_warning.txt")

        self.test_dir = test_dir
        self.all_infos = self._gather_log(log_paths) 
        self.videos_name = [i for i in os.listdir(test_dir) if Path(i).suffix in GlobalConfig.SUFFIXS]
        self.ps = []
        self.fs = []
        self.video_ps = []
        self.video_fs = []
         
    def get_df(self):
        '''根据视频文件夹下的视频名和log中的视频名进行比对，统计报警数量 
        Args:
            arg
        Outputs:
            df : pd.DataFrame, 单个场景的统计结果
        '''
        
        video_num = len(self.videos_name)

        for video_name in self.videos_name:
            alarm_info = self._clear_dumplicate_alarm(self.all_infos[Path(video_name).stem])
            label_path = Path(os.path.join(self.test_dir, video_name)).with_suffix(".json")

            p, f, d_p, d_f, llm_p, llm_f, llm_d_p, llm_d_f = self.compare_alarm_with_lable(alarm_info, label_path)
            self.df["场景"].append(None)
            self.df["参数"].append(None)
            self.df["视频时长"].append(self.get_duration(os.path.join(self.test_dir, video_name)))
            self.df["视频名"].append(video_name)
            self.df["报警数量"].append(p+f+d_p+d_f)
            self.df["正确报警数量"].append(p)
            self.df["错误报警数量"].append(f)
            self.df["正报重复数量"].append(d_p)
            self.df["误报重复数量"].append(d_f)
            self.df["llm修正-正确报警数量"].append(llm_p)
            self.df["llm修正-错误报警数量"].append(llm_f)
            self.df["llm修正-正报重复数量"].append(llm_d_p)
            self.df["llm修正-误报重复数量"].append(llm_d_f)
            self.df["漏报原因分析"].append(None)

        # 只要视频中有正确报警就记作正确报警视频
        p_video_num = sum([i > 0 for i in self.df["正确报警数量"][1:]])
        f_video_num = np.sum(np.array([i > 0 for i in self.df["错误报警数量"][1:]]) & np.array([i == 0 for i in self.df["正确报警数量"][1:]]))

        llm_p_video_num = sum([i > 0 for i in self.df["llm修正-正确报警数量"][1:]])
        llm_f_video_num = np.sum(np.array([i > 0 for i in self.df["llm修正-错误报警数量"][1:]]) & np.array([i == 0 for i in self.df["llm修正-正确报警数量"][1:]]))
        sub_static = {
            "正确报警视频":f"{p_video_num}/{video_num}",
            "错误报警视频":f"{f_video_num}/{video_num}",
            "正确":np.sum(self.df["正确报警数量"][1:]),
            "正确重复":np.sum(self.df["正报重复数量"][1:]),
            "错误":np.sum(self.df["错误报警数量"][1:]),
            "错误重复":np.sum(self.df["误报重复数量"][1:]),
            "llm正确报警视频":f"{llm_p_video_num}/{video_num}",
            "llm错误报警视频":f"{llm_f_video_num}/{video_num}",
            "llm正确":np.sum(self.df["llm修正-正确报警数量"][1:]),
            "llm正确重复":np.sum(self.df["llm修正-正报重复数量"][1:]),
            "llm错误":np.sum(self.df["llm修正-错误报警数量"][1:]),
            "llm错误重复":np.sum(self.df["llm修正-误报重复数量"][1:]),
        }
        self.df["视频名"][0] = str(sub_static)
        return pd.DataFrame(data=self.df)

    @staticmethod
    def get_duration(video_path):
        '''获取视频时长'''
        try:
            duration = int(ffmpeg.probe(video_path)["format"]["duration"].split(".")[0])
        except:
            return "0"
        return f"{duration//3600}:{(duration%3600)//60}:{duration%60}"
    
    @staticmethod
    def get_fps(video_path)->int:
        '''获取视频帧率
        Args:
            video_path
        Outputs:
            fps:int
        '''
        try:
            fps = int(eval(ffmpeg.probe(video_path)["streams"][0]["r_frame_rate"]))
        except:
            logging.error(f"获取视频帧率失败: {video_path}")
            return 0
        return fps

    def _xywh2xyxy(self, bbox):
        x1, y1, w, h = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
        return [x1, y1, x1+w, y1+h]
    
    def plot_label_box(self, boxs, alert_img_path):
        '''为报警图片添加标注信息，便于和报警框对比 
        Args:
            arg
        Outputs:
            out
        '''
        pass 
    
    def compare_alarm_with_lable(self, alarm_info, label_path):
        '''将报警信息和标签进行比对，统计正确报警数量，错误报警数量，漏报数量
        Args:
            alarm_info: 报警信息列表 [{box:[], frame_id:, event_id:, result_name:},...]
            label_path: 标签路径
        Outputs:
            p: 正确匹配数量
            f: 错误匹配数量
            d_p: 正确匹配重复数量
            d_f: 错误匹配重复数量
            m: 漏报数量
        '''
        p, f, d_p, d_f = 0, 0, 0, 0
        llm_p, llm_f, llm_d_p, llm_d_f = 0, 0, 0, 0
        # 如果没有标签文件，所有报警都是正确报警
        if not os.path.isfile(label_path):
            for info in alarm_info:
                d_p += info["dumplicate_times"]
                if info["llm_check"] == 1:
                    llm_p += 1
                    llm_d_p += info["dumplicate_times"]

                self.ps.extend(info["result_pic_name"])
                self.video_ps.extend(info["result_video_name"])
            return len(alarm_info), 0, d_p, 0, llm_p, llm_f, llm_d_p, llm_d_f 
        
        label = json.load(open(label_path))
        # video_name = Path(label_path).stem
        for info in alarm_info:
            # 检测框
            detect_frame_id = info["frame_id"]
            box = info["box"]
            detect_box = [box[0], box[1], box[0]+box[2], box[1]+box[3]]

            #标注框
            label_frame_keys = np.array([int(i) for i in label.keys()])
            near_id = np.argmin(np.abs(label_frame_keys - detect_frame_id))
            label_boxs = label[str(label_frame_keys[near_id])]
            max_iou = 0
            for label_box in label_boxs:
                iou = self._compute_iou(label_box, detect_box)
                if iou > max_iou:
                    max_iou = iou
            # 保存下报警位置和标记位置
            self.plot_label_alert(label_boxs, detect_box, info["result_pic_name"][0], max_iou)
            if max_iou > 0.05:
                p += 1 
                d_p += info["dumplicate_times"]
                self.ps.extend(info["result_pic_name"])
                self.video_ps.extend(info["result_video_name"])
                if info["llm_check"] == 1:
                    llm_p += 1
                    llm_d_p += info["dumplicate_times"]
                if info["llm_check"] == 0:
                    pass 
            else:
                f += 1
                d_f += info["dumplicate_times"]
                self.fs.extend(info["result_pic_name"])
                self.video_fs.extend(info["result_video_name"])
                if info["llm_check"] == 1:
                    llm_f += 1
                    llm_d_f += info["dumplicate_times"]
                if info["llm_check"] == 0:
                    pass 
        return p, f, d_p, d_f, llm_p, llm_f, llm_d_p, llm_d_f

    def plot_label_alert(self, label_boxs, alert_boxs, img_name, max_iou):
        for root, _, files in os.walk(self.result_dir):
            for file in files:
                if img_name in file and "check" not in file:
                    img_path = os.path.join(root, file)
        img = Image.open(img_path)
        draw = ImageDraw.Draw(img)
        for box in label_boxs:
            draw.rectangle(box, outline="blue", width=2)
        draw.rectangle(alert_boxs, outline="red", width=2)
        draw.text((10,10), str(max_iou), fill="red")
        img.save(img_path)

    def _compute_iou(self, box1, box2):
        """
        参数:
        box1, box2 -- 边界框，表示为 [x_min, y_min, x_max, y_max]
        """
        # 计算交集的坐标
        x_min_inter = max(box1[0], box2[0])
        y_min_inter = max(box1[1], box2[1])
        x_max_inter = min(box1[2], box2[2])
        y_max_inter = min(box1[3], box2[3])

        inter_area = max(0, x_max_inter - x_min_inter) * max(0, y_max_inter - y_min_inter)
        box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
        box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union_area = box1_area + box2_area - inter_area
        iou = inter_area / (union_area + 1e-6)

        return iou
    
    def is_zero(self, box):
        '''判断box长或者宽是否为0'''
        if box[2] == 0 or box[3] == 0:
            logging.error("box长或者宽为0")
            return True
        return False
    
    def _gather_log(self, log_paths):
        '''汇总log中的结果'''
        res = defaultdict(list)
        pattern = r'Event_(\d+)_(\d+)(?:.*?)?-(.*)(?=\.mp4)'
        
        for log_path in log_paths:
            with open(log_path, "r") as f:
                for line_id, line in enumerate(f.readlines()):
                        info = eval(line.strip())
                        for event_info in info["ChannelEvtInfo"][0]["Evt_List"]:
                            alert_img_path = event_info["EventImagePath"]
                            alert_video_path = event_info["EventVideoPath"]
                            video_name = re.search(pattern, os.path.basename(alert_video_path))[3]
                            result_pic_name = Path(alert_img_path).stem # 报警图片名
                            result_video_name = Path(alert_video_path).stem
                            frame_id = info["Frame"]
                            x = event_info["PosX"]
                            y = event_info["PosY"]
                            w = event_info["PosW"]
                            h = event_info["PosH"]

                            event_id = event_info["EvtType"]
                            if "llm_check" in event_info.keys():
                                llm_check = int(event_info["llm_check"])
                                self.use_llm = True
                            else:
                                llm_check = None
                            res[video_name].append(
                                {
                                    "box":[x, y, w, h], 
                                    "frame_id" : frame_id, 
                                    "event_id" : event_id, 
                                    "result_pic_name" : [result_pic_name], 
                                    "result_video_name":[result_video_name],
                                    "llm_check" : llm_check
                                }
                            )
        return res
    
    def _clear_dumplicate_alarm(self, alarm_infos, iou_thresh=0.05):
        '''将报警信息中的重复报警去除，只保留第一次报警的信息 
        Args:
            alarm_infos: 报警信息列表 [{box:[], frame_id:, event_id:},...]
        Outputs:
            alarm_infos: 去重后的报警信息列表: [{box:[], frame_id:, event_id:, dumplicate_times:},...]
        '''
        for i in range(len(alarm_infos)):
            alarm_infos[i]["dumplicate_times"] = 0
        # 去除错误报警框
        alarm_infos = [i for i in alarm_infos if not self.is_zero(i["box"])]
        # 去除重复报警框
        for i in range(len(alarm_infos)):
            if alarm_infos[i]["dumplicate_times"] is None:
                continue
            for j in range(i+1, len(alarm_infos)):
                if alarm_infos[j]["dumplicate_times"] is None:
                    continue
                iou = self._compute_iou(self._xywh2xyxy(alarm_infos[i]["box"]), self._xywh2xyxy(alarm_infos[j]["box"]))
                if iou > iou_thresh:
                    alarm_infos[i]["dumplicate_times"] += 1
                    alarm_infos[i]["result_pic_name"].append(alarm_infos[j]["result_pic_name"][0])
                    alarm_infos[i]["result_video_name"].append(alarm_infos[j]["result_video_name"][0])
                    alarm_infos[j]["dumplicate_times"] = None 

        alarm_infos = [i for i in alarm_infos if i["dumplicate_times"] is not None]
        return alarm_infos

    def move_video(self):
        '''分离正确报警和错误报警的视频 
        Args:
            arg
        Outputs:
            out
        '''
        p = os.path.join(self.result_dir, "01_正确报警")
        f = os.path.join(self.result_dir, "02_错误报警")
        os.makedirs(p, exist_ok=True)
        os.makedirs(f, exist_ok=True)

        for root, dirs, files in os.walk(self.result_dir):
            for file in files:
                if self._is_contain(file, self.ps) or self._is_contain(file, self.video_ps):
                    if os.path.isfile(os.path.join(p, file)):
                        continue
                    shutil.move(os.path.join(root, file), p)
                elif self._is_contain(file, self.fs) or self._is_contain(file, self.video_fs):
                    if os.path.isfile(os.path.join(f, file)):
                        continue
                    shutil.move(os.path.join(root, file), f)
                else:
                    if file.endswith(".jpg") or file.endswith(".mp4"):
                        logging.warning(f"不在正确或错误结果中 : {file}")

    def _is_contain(self, name:str, keys:list):
        '''判断name是否包含keys中的任意一个关键字
        Args:
            key:关键字列表
            names:查询字符串
        Outputs:
        
        '''
        for key in keys:
            if Path(key).stem in name:
                return True
        return False
    
if __name__=='__main__':
    pass 
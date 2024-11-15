import os, shutil, json, random, sys, logging, glob
from pprint import pprint
import pandas as pd 
from collections import defaultdict
import subprocess
from pathlib import Path
import logging 
import argparse
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s | %(message)s')

class CutVideo():
    def __init__(self, excel_path, save_root, ft, bt) -> None:
        self.excel = pd.read_excel(excel_path, sheet_name="Sheet1")
        self.path2tstamp = defaultdict(list)
        self.save_root = save_root
        
        for idx, row in self.excel.iterrows():
            video_path = row["url"]
            sence = row["场景"]
            start_time = row['开始时间']

            save_dir = os.path.join(self.save_root, sence)
            os.makedirs(save_dir, exist_ok=True)
            start, end = self.get_time_interval(start_time, ft, bt)
            save_path = os.path.join(save_dir, Path(video_path).stem + f"_{start}-{end}" + Path(video_path).suffix)
            try:
                subprocess.call(f"ffmpeg -y -i '{video_path}' -ss {start} -to {end} -c copy '{save_path}'", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                # subprocess.call(f"ffmpeg -i '{video_path}' -ss {start} -to {end} -c copy '{save_path}'", shell=True)
                logging.info(f"文件已保存：{save_path}")
            except Exception as e:
                logging.info(f"视频截取失败：{save_path} {e}")
            
    def get_time_interval(self, start_time, ft, bt):
        start_time = str(start_time)
        start_second = int(start_time.split(":")[0]) * 3600 + int(start_time.split(":")[1]) * 60 + int(start_time.split(":")[2])
        true_start = start_second - ft
        if true_start < 0:
            true_start = 0
            logging.warning("开始时间小于0,强制调整为0")
        true_end = start_second + bt
        return self._second2time(true_start), self._second2time(true_end)
    
    def _second2time(self, second):
        return f"{second//3600}:{(second%3600)//60}:{second%60}"

    def cut(self, video_path, start_time, end_time, save_dir):
        for video_path, sub_infos in self.path2tstamp.items():
            for info in sub_infos:
                s = os.path.join(self.save_dir, sub_infos[0])
                

if __name__=='__main__':
    # parser = argparse.ArgumentParser("")
    # parser.add_argument("xlsx_path")
    CutVideo("/home/user/Desktop/裁剪需求.xlsx",\
             "/home/user/Desktop/test_res",\
            60,120)
    
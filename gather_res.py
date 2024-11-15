import os, shutil, json, random, sys, logging, glob, time 
from pprint import pprint 
import subprocess
import logging 
import argparse
import utils
import yaml
from utils import GlobalConfig
from easydict import EasyDict as edict

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config_path", type=str, default="./gather_lh_96.yaml")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--tmp", action="store_true", help="临时测试加tmp子串，好删除")
    args = parser.parse_args()
    return args
            
def main(args):
    res_excel = utils.WriteExcel(os.path.join(GlobalConfig.RESULT_DIR, f"{GlobalConfig.TIME_NOW}_统计结果汇总.xlsx"))
    data = utils.PrepareData()

    total_event_dir_num = data.event_num
    total_video_num = data.video_num
    current_event_dir_num = 0
    current_video_num = 0

    for test_dir, video_paths, config_path in data:
        logging.info(f"并行数量 : {GlobalConfig.CONCURRENT_NUM}")
        test_event = test_dir.split('/')[-2]
        test_sence = test_dir.split('/')[-1]

        # 视频分批次
        current_event_dir_num += 1
        CONCURRENT_NUM = GlobalConfig.CONCURRENT_NUM
        for idx in range(0, len(video_paths), CONCURRENT_NUM):
            if len(video_paths) < CONCURRENT_NUM:
                video_batch = video_paths
                current_video_num +=  len(video_paths)
            elif idx+CONCURRENT_NUM > len(video_paths):
                video_batch = video_paths[idx:]
                current_video_num += len(video_paths) - idx
            else:
                video_batch = video_paths[idx:idx+CONCURRENT_NUM]
                current_video_num += CONCURRENT_NUM

            # 1.保存程序运行日志 
            result_dir_name = f"{GlobalConfig.TIME_NOW}_{test_event}_{test_sence}"

            os.makedirs(os.path.join(GlobalConfig.RESULT_DIR, result_dir_name), exist_ok=True)
            log_path = os.path.join(GlobalConfig.RESULT_DIR, result_dir_name, f"batch{idx}-{idx+CONCURRENT_NUM}.log")
            event_log_path = os.path.join(GlobalConfig.RESULT_DIR, result_dir_name, f"batch{idx}-{idx+CONCURRENT_NUM}_event.log")
            back_config_path = os.path.join(GlobalConfig.RESULT_DIR, result_dir_name, f"batch{idx}-{idx+CONCURRENT_NUM}_configInfo.json")
            with open(log_path,"w") as f:
                pass 
            with open(event_log_path,"w") as f:
                pass 

            logging.info(f'日志文件 : {log_path}')
            logging.info(f'事件日志文件 : {event_log_path}')
            kill_proc_env = os.environ.copy()
            kill_proc_env.update(
                    {
                        "total_event_dir_num":str(total_event_dir_num),
                        "current_event_dir_num":str(current_event_dir_num),
                        "total_video_num":str(total_video_num),
                        "current_video_num":str(current_video_num),
                        "run_port":str(args.run_port),
                        "event_port":str(args.event_port),
                        "event_log_path":event_log_path,
                        "use_llm": "1" if GlobalConfig.TESTPATHS_LLM else "0",
                        "exe_name": args.exe_name,
                    }
                )

            kill_proc = subprocess.Popen(f"python {os.path.join(GlobalConfig.SCRIPT_DIR, 'kill_run_over.py')}", env=kill_proc_env, shell=True)
            # 2.修改配置文件
            c = utils.ConfigInfo(
                args,
                config_path,
                video_batch,
                batch_start=idx,
                result_dir=os.path.join(GlobalConfig.RESULT_DIR, result_dir_name))
            c.save(back_config_path)
            # logging.info(f"结果保存路径为:{os.path.join("/result_dir", result_dir_name)}")
            test_config = c.get_sheet_config()
            # 3.运行程序
            try:
                with open(log_path, "w") as f:
                    subprocess.call(f'./{args.exe_name}', shell=True, stdout=f, stderr=f)
                # 等待子进程完成
                while kill_proc.poll() is None:
                    time.sleep(0.1)
            except:
                kill_proc.terminate()

        # 4.整理报警结果
        log_paths = glob.glob(os.path.join(GlobalConfig.RESULT_DIR, result_dir_name, "*event.log"))
        gather_res = utils.GatherRes(log_paths=log_paths, test_dir=test_dir, test_config=test_config)
        df = gather_res.get_df()
        gather_res.move_video()
        res_excel.fresh(sheet_name=test_event, data=df)    

        print("="*120)
            
if __name__=='__main__':
    args = get_args()
    utils.parse_yaml(args.config_path)
    os.chdir(GlobalConfig.EXE_DIR)

    if not args.debug:
        with utils.PrepareCloudEagleEnv(args) as a:
            main(a)
    else:
        # 直接使用某个时间戳下的测试结果生成图表
        if os.path.isfile("./debug_res.xlsx"):
            os.remove("./debug_res.xlsx")

        time_stamps = set([i.split("_")[0] for i in os.listdir(GlobalConfig.RESULT_DIR)])
        time_stamps = sorted(time_stamps)
        for id, s in enumerate(time_stamps):
            print(f"{id:<2} --> {s}")
        time_stamp_id = input("需要统计的时间戳的ID:")
        if time_stamp_id == "q":
            sys.exit()
        time_stamp = time_stamps[int(time_stamp_id)]
        print(f"选定时间戳:{time_stamp}")


        result_dirs = glob.glob(os.path.join(GlobalConfig.RESULT_DIR, f"{time_stamp}*"))
        data = utils.PrepareData()
        test2res = data.get_test_res_pair(result_dirs)
        for test_dir, result_dir in test2res.items():
            if not os.path.isdir(result_dir):
                continue
            config_path = glob.glob(os.path.join(result_dir,"*configInfo.json"))[0]
            video_paths=glob.glob(os.path.join(test_dir,"*.mp4"))
            c = utils.ConfigInfo(args=args, 
                   config_path=config_path, 
                   video_paths=video_paths, 
                   batch_start=0, 
                   result_dir=result_dir)
            test_config = c.get_sheet_config()
            log_paths = glob.glob(f"{result_dir}/*event.log")
            gather_res = utils.GatherRes(log_paths=log_paths, test_dir=test_dir, test_config=test_config)
            df = gather_res.get_df()
            gather_res.move_video()
            e = utils.WriteExcel("./debug_res.xlsx")
            e.fresh(sheet_name="test", data=df)

        print("./debug_res.xlsx")


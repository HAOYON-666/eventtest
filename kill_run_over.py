import socket, requests
import subprocess
import os, sys
import time 
import threading
import json
import base64, io
from PIL import Image 
from queue import Queue
from pprint import pprint 

ENV = os.environ.copy()
RUNNING_FLAG = True

def udp_server(alert_q:Queue, start=None, port=None,host='0.0.0.0'):
    global RUNNING_FLAG
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind((host, port))
        print(f"Listening on {host}:{port}...")
        # 设置超时为5秒
        s.settimeout(5)
        def get_runtime_str(seconds:int):
            return f"{seconds//3600:02}:{(seconds%3600)//60:02}:{seconds%60:02}"

        try:
            while True:
            # 尝试接收数据
                data, addr = s.recvfrom(1024)
                seconds = int(time.time() - start)
                if ENV["use_llm"].lower() == "true":
                    print(f'当前待llm确认事件长度 : {alert_q.qsize()} 事件 : {ENV["current_event_dir_num"]:>5}/{ENV["total_event_dir_num"]:5} 视频 : {ENV["current_video_num"]:>5}/{ENV["total_video_num"]:5} 运行时间 : {get_runtime_str(seconds)}', end="\r")
                else:
                    print(f'事件 : {ENV["current_event_dir_num"]:>5}/{ENV["total_event_dir_num"]:5} 视频 : {ENV["current_video_num"]:>5}/{ENV["total_video_num"]:5} 运行时间 : {get_runtime_str(seconds)}', end="\r")
        except socket.timeout:
            seconds = int(time.time() - start)
            if ENV["use_llm"].lower() == "true":
                print(f'当前待llm确认事件长度 : {alert_q.qsize()} 事件 : {ENV["current_event_dir_num"]:>5}/{ENV["total_event_dir_num"]:5} 视频 : {ENV["current_video_num"]:>5}/{ENV["total_video_num"]:5} 运行时间 : {get_runtime_str(seconds)}')
            else:
                print(f'事件 : {ENV["current_event_dir_num"]:>5}/{ENV["total_event_dir_num"]:5} 视频 : {ENV["current_video_num"]:>5}/{ENV["total_video_num"]:5} 运行时间 : {get_runtime_str(seconds)}')
            print("超过5s没有接收到数据")
            RUNNING_FLAG = False
            alert_q.put(None)
            # subprocess.run(f"ps -ef | grep {exe_name}| grep -v grep| awk \'{{print $2}}\'| xargs kill -9", shell=True)

def recive_alert(alert_q:Queue, port=60500, host='0.0.0.0'):
    global RUNNING_FLAG
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    # with socket.socket() as s:
        s.bind((host, int(port)))
        # s.setblocking(True)
        s.settimeout(5000)
        while True:
        # 尝试接收数据
            try:
                if RUNNING_FLAG:
                    data, addr = s.recvfrom(8192)
                    data = data.decode("utf-8")
                    alert_q.put(data)
                else:
                    s.close()
                    return 
            except BlockingIOError:
                continue
            except socket.timeout:
                return 


def check_event_with_llm(alert_q:Queue, event_log_path):
    while True:
        data = alert_q.get()
        if data == None:
            subprocess.call(f"pkill -f {ENV['exe_name']}", shell=True)
            return 
        print(f"当前待llm确认事件长度 : {alert_q.qsize()}", end="\r")
        with open(event_log_path, "a") as f:
            if not ENV["use_llm"].lower() == "true":
                f.write(data)
            else:
                result_dir = os.path.dirname(event_log_path)
                try:
                    alert = eval(data)
                except:
                    print("大模型确认，事件日志读取错误")
                for event in alert["ChannelEvtInfo"][0]["Evt_List"]:
                    x, y, w, h = int(event["PosX"]), int(event["PosY"]), int(event["PosW"]), int(event["PosH"]) 
                    EvtType = event["EvtType"]
                    img_name = os.path.basename(event["EventImagePath"])
                    # 查找报警图片的本地路径
                    local_img_path = None
                    for root, _, files in os.walk(result_dir):
                        for file in files:
                            if file == img_name:
                                local_img_path = os.path.join(root, file)
                    if local_img_path == None:
                        print("没有找到本地报警图片路径")
                        return 
                    # 发送请求，大模型二次确认
                    files = {"file":open(local_img_path, "rb")}
                    data = {
                        "text_input" : f"[{x}, {y}, {w}, {h}]",
                        "event_type" : EvtType              
                    }
                    url = "http://192.168.6.27:50888/event_check"
                    res = requests.post(url=url, data=data, files=files).json()
                    # 保存返回的大模型推理图片
                    if not res["check_image"] == "None":
                        img_byte = base64.b64decode(res["check_image"])
                        img_stream = io.BytesIO(img_byte)
                        img = Image.open(img_stream)
                        img.save(local_img_path.replace(".jpg", "_llm_check.jpg"))
                        img.save("/data/liuhui_work/tmp.jpg")
                    # 保存大模型推理结果
                    if res["states"] == -1:
                        print("大模型调用出错")
                    else:
                        event["llm_check"] = res["states"]
                f.write(json.dumps(alert) + "\n") 
    
if __name__ == "__main__":
    print('启动监听')
    tic = time.time()
    time.sleep(5)
    alert_q = Queue()
    p_kill = threading.Thread(target=udp_server, args=(alert_q,tic,int(ENV["run_port"]),))
    p_event_log = threading.Thread(target=recive_alert, args=(alert_q, int(ENV["event_port"]),), daemon=True)
    p_llm_check = threading.Thread(target=check_event_with_llm, args=(alert_q, ENV["event_log_path"],))


    p_kill.start()
    p_event_log.start()
    p_llm_check.start()

    p_kill.join()
    p_llm_check.join()




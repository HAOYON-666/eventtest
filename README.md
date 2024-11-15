## 一、自动测试脚本使用方法
### 1. 需要先确认本机的ffmpeg能否正常使用
- 如果没有ffmpeg 
    - apt install ffmpeg
- 如果提示无法定位到ffmpeg，先更新下安装包的索引列表
    - apt update
    - apt install ffmpeg
- 如果报错`ffmpeg: symbol lookup error: /usr/lib/x86_64-linux-gnu/libgobject-2.0.so.0: undefined symbol: g_date_copy`
    - 将对应路径添加到环境变量中
        - `export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH`
### 2. 安装conda虚拟环境
    - bash Miniconda3-latest-Linux-x86_64.sh
### 3. 安装依赖
    - pip install -r requirement.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
### 4. 设置云鹰程序目录下的log.conf文件，使事件输出到日志文件中，后续会根据日志文件的内容统计表格，如果不开结果为0
    - 将log.conf的91行左右改为如下形式
    ```bash 
        -- protocol_evt
        * GLOBAL:
            FORMAT                  =   "[%level | %datetime] | %msg"
            ENABLED                 =   true
            TO_FILE                 =   false
            TO_STANDARD_OUTPUT      =   true
            MILLISECONDS_WIDTH      =   3
            FILENAME                =   "easylog/protocol_evt_log/evt_%datetime{%Y%M%d}.log"
            PERFORMANCE_TRACKING    =   false
            MAX_LOG_FILE_SIZE       =   1048576
            LOG_FLUSH_THRESHOLD     =   0
    ```
### 5. 自动测试
    - 配置gather_config.yaml中的各项配置
    - 运行python文件gather_res.py
        - python gather_res.py --config_path '配置文件的路径'

### configInfo_template.json 模板的使用方法
    - 此功能是用来批量修改测试目录下的配置文件

```mermaid
graph TD
    1(对比模板和测试路径下的配置文件)
    2(SystemInfo)
    3(SendInfo)
    4(CameraInfo)
    1 --> 2 & 3 & 4
    5{是否在模板中配置}
    6(采用模板的配置)
    7(保留测试路径下的配置)
    2 --> 5 -->|是| 6
    5 -->|否| 7

    8(EventRuleInfo字段不做以下判断)
    4 --> 8 --> 5

```
  
## 二、标注测试视频脚本使用方法
### 1. 搭建环境
- 在`01_安装包`文件夹下有conda安装包：`Miniconda3-latest-Windows-x86_64.exe`，双击安装即可
- 安装完conda后重新启动一个终端，命令行最开始有`(base)`标志说明安装完成
- 使用如下命令安装opencv：
    - pip install opencv-python -i https://pypi.tuna.tsinghua.edu.cn/simple

### 2. 命令示例
- python label_video.py --video_dir /data/test --frame_interval 5 --window_width 1920 --window_height 1080
#### 2.1. 参数含义
    - --video_dir:必选参数，包含测试视频的文件夹路径
    - --frame_interval:必选参数，设置标注时的跳帧间隔
    - --window_width: 可选参数，弹出窗口的宽度，默认1920
    - --window_height：可选参数，弹出窗口高度， 默认1080

    可选参数可以缺省，按默认值处理

### 3. 运行结果
1. 会为每个视频文件生成同名的json文件
### 4.快捷键使用
- s 前进一帧
- a 后退一帧
- 鼠标左键 拉框
- 滚轮键按下 取消框
  
## 三、使用python脚本测试视频或图片
- 这部分脚本修改自yolov5 6.2的官方代码，添加了算能模型、华为模型、v4以及v4tiny模型的推理测试支持
### 1. 使用示例
```python
# 推理onnx模型
python detect.py --weights ../../model-release/detect/01_交通基础检测/2024-04-29/v5s_640x640.onnx --source ../../tmp.mp4 --imgsz 640
- weights 参数指定要使用的模型，算能和华为的模型推理需要到特定的机器上
- source 指定推理数据的路径，如果是文件夹会推理此文件夹下所有的视频和图片，不支持递归查找
- imgsz 推理尺寸，默认为640x640, 如果需要推理416模型需要特别指定 ‘--imgsz 416’，如果需要推理v4模型需要指定 ‘--imgsz 320 608’
- 如果推理的是v4模型还需要加上‘--v4’，v4模型只支持推理onnx不支持推理.weights, 由于历史原因老模型的输出格式不一致，所以存在推理失败的情况
- 推理算能华为等模型只需要修改--weights参数并切换到相应的硬件环境即可
```
### 2. 可能用到的功能
- 结果默认保存在当前目录下的run/exp下，配合--project和--name参数可以自定义保存路径
- --line-thickness 修改叠加检测框的线的宽度
- --save-crop 把小图存出来
- --classes 只叠加特定类别的检测框
- 更多功能可以通过’python detect.py --help’查看
### 可能遇到的问题
#### 1. 事件测试
- 遇到‘不在正确或错误结果中’的warning
-- 一个场景的视频推理结束后，会把所有的报警视频和报警图片分别挪到正确报警和错误报警，这个日志的意思是有的报警图片或者报警视频没有匹配到报警日志中的文件名，挪不过去。对统计结果没有影响，只是个warning，有可能是报警图片和报警视频名不一致导致的

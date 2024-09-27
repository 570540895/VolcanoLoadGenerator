import os
import time
import logging
import yaml
import sched
import sys
import pandas as pd
from string import Template

is_debug = True if sys.gettrace() else False

# 时间压缩比
time_compress = 30

# 构造负载倍数
load_times = 1
# 构造负载延迟(秒)
load_latency = 3

# 预留时间用于生成yml文件
start_interval = 30
# 任务启动延迟阈值
time_interval_threshold = 0

log_file = r'logs/test.log'
logging.basicConfig(filename=log_file, level=logging.DEBUG)
log = logging.getLogger(__name__)

csv_file = r'data/test.csv'
sorted_csv_file = r'data/sorted_test.csv'

job_template_path = r'templates/'

job_path = r'jobs/'
deployment_path = r'deployments/'

"""
def is_replicas(row1, row2):
    return row1['jobId'] == row2['jobId'] \
           and row1['startTime'] == row2['startTime'] \
           and row1['endTime'] == row2['endTime']
"""


def create_yml_files(test_index, pod_num, duration, cpu_num, memory, gpu_num, is_running):
    job_file_name = '{}job-{}.yml'.format(job_path, str(test_index))
    job_name = 'vcjob-{}'.format(str(test_index))
    min_available = str(pod_num)
    replicas = min_available
    task_name = 'task-{}'.format(str(test_index))
    pod_name = 'pod-{}'.format(str(test_index))
    ctr_name = 'ctr-{}'.format(str(test_index))
    duration = str(duration)

    # cpu缩放1000倍， mem缩放1024倍
    cpu = '{}m'.format(str(cpu_num))
    mem = '{}Mi'.format(str(memory))
    gpu = '{}'.format(str(gpu_num))

    job_template_file = '{}{}'.format(job_template_path,
                                      'running_job_template.yml' if is_running else 'finished_job_template.yml')
    with open(job_template_file, encoding='utf-8') as fp:
        read_cfg = fp.read()
        job_template = Template(read_cfg)
        job_s = job_template.safe_substitute({'JobName': job_name,
                                              'MinAvailable': min_available,
                                              'Replicas': replicas,
                                              'TaskName': task_name,
                                              'PodName': pod_name,
                                              'CtrName': ctr_name,
                                              'Duration': duration,
                                              'Cpu': cpu,
                                              'Memory': mem,
                                              'Gpu': gpu
                                              })
    job_yaml_data = yaml.safe_load(job_s)
    with open(job_file_name, 'w') as fp:
        yaml.dump(job_yaml_data, fp, sort_keys=False)


def exec_test(test_index, row_index, time_interval):
    job_file_name = 'job-{}.yml'.format(str(test_index))
    print('printing: {} row_index: {} time_interval: {}'.format(job_file_name, row_index, time_interval))


# execute cluster loader task
def exec_kubectl(test_index):
    job_file_name = '{}job-{}.yml'.format(job_path, str(test_index))
    cmd = 'kubectl apply -f {}'.format(job_file_name)
    os.system(cmd)


def run():
    try:
        df = pd.read_csv(csv_file)
        assert df.shape[0] >= 2
        df = df.sort_values('createDate', ascending=True)
        df = df.reset_index(drop=True)
        df.to_csv(sorted_csv_file, index=False)
    except Exception as e:
        log.error(e)
        print(e)
        raise

    test_index = 0
    row_index = 0

    scheduler = sched.scheduler(time.time, time.sleep)
    csv_start_time = df['createDate'][0]

    # 实际任务开始执行时间
    exec_start_time = int(time.time()) + start_interval

    for _, row in df.iterrows():
        pod_num = row['worker_num']
        duration = max(1, int((row['endTime'] - row['startTime']) / time_compress))
        cpu_num = row['cpu_num']
        memory = row['mem(GB)']
        gpu_num = row['gpu_num']
        is_running = (row['status'] == 'running')

        time_interval = int((row['createDate'] - csv_start_time) / time_compress)
        # if time_interval > 600:
            # break
        for i in range(load_times):
            create_yml_files(test_index, pod_num, duration, cpu_num, memory, gpu_num, is_running)
            exec_func = exec_test if is_debug else exec_kubectl
            exec_func_params = (test_index, row_index, time_interval,) if is_debug else (test_index,)
            if time_interval >= time_interval_threshold:
                scheduler.enter(exec_start_time + time_interval + i * load_latency - int(time.time()), 0,
                                exec_func, exec_func_params)
            test_index += 1
        row_index += 1
    scheduler.run()


if __name__ == '__main__':
    run()

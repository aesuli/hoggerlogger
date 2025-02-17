import argparse
import json
import pwd
import psutil
from collections import defaultdict
from datetime import datetime
import time
import socket
import sys
import nvsmi

def owner(pid):
    try:
        with open(f'/proc/{pid}/status') as proc_file:
            for line in proc_file:
                if line.startswith('Uid:'):
                    uid = int(line.split()[1])
                    return pwd.getpwuid(uid).pw_name
    except:
        return None


if __name__=='__main__':
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.bind('\0HoggerLogger_single_process_lock')
    except socket.error:
        print('Process already running', file=sys.stderr)
        exit(0)

    parser = argparse.ArgumentParser()
    parser.add_argument('--interval', type=int, default=60, help='Interval log in seconds')
    parser.add_argument('--output_file', type=argparse.FileType('at', encoding='utf-8'), default=sys.stdout,
                        help='Output file, default is standard output')
    args = parser.parse_args()

    interval = args.interval
    output_file = args.output_file

    while True:
        # Initial call to load CPU usage
        for proc in psutil.process_iter(['pid', 'name', 'username']):
            try:
                proc.cpu_percent(interval=0)  # Prime the measurement
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass  # Ignore inaccessible processes

        # Wait for a small interval before measuring CPU usage
        time.sleep(0.1)

        user_threads = defaultdict(int)
        user_mem = defaultdict(int)
        user_cpu_percent = defaultdict(int)
        for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_info', 'num_threads']):
            try:
                info = proc.info  # Dictionary with requested process details
                user = info['username']
                user_threads[user] += info['num_threads']
                user_mem[user] += int(info['memory_info'].rss /1024**2)
                user_cpu_percent[user] += int(info['cpu_percent'])
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass  # Skip processes that no longer exist or can't be accessed

        # scan of GPU processes
        gpus = list(nvsmi.get_gpus())
        gpus = {gpu.id: gpu for gpu in gpus}

        user_gpu = defaultdict(int)
        user_gpu_percent = defaultdict(int)
        user_gpu_mem = defaultdict(int)

        processes = nvsmi.get_gpu_processes()

        # current version of nvsmi can't tell which process causes the load on a GPU, let's divide it equally
        processes_per_gpu = defaultdict(int)
        for process in processes:
            processes_per_gpu[process.gpu_id] += 1

        for process in processes:
            user = owner(process.pid)
            if user:
                user_gpu[user]+=1
                user_gpu_percent[user] += int(gpus[process.gpu_id].gpu_util/processes_per_gpu[process.gpu_id])
                user_gpu_mem[user] += int(process.used_memory)

        # Get overall memory usage.
        vm = psutil.virtual_memory()

        system = {
            'time': datetime.now().replace(microsecond=0).isoformat(),
            'total_processes': len(psutil.pids()),
            'mem_percent': vm.used*100//vm.total,
            'cpu_percent': int(sum(psutil.cpu_percent(percpu=True))),
            'gpu_mem_percent': int(sum(gpu.mem_used for gpu in gpus.values())*100//sum(gpu.mem_total for gpu in gpus.values())),
            'gpu_percent': int(sum(gpu.gpu_util for gpu in gpus.values())),
        }

        disks = list()
        for p in psutil.disk_partitions():
            if p.fstype!='squashfs' and not p.mountpoint.startswith('/proc') and not p.mountpoint.startswith('/boot'):
                disk_usage = psutil.disk_usage(p.mountpoint)
                disks.append({
                    'mount': p.mountpoint,
                    'use_percent': int(disk_usage.percent)
                })

        system['disks'] = disks

        users = list()
        for user in sorted(user_threads):
            if user_cpu_percent[user]>0 or user_mem[user]>100 or user_gpu[user]>0:
                users.append({
                    'user': user,
                    'cpu_percent': user_cpu_percent[user],
                    'mem': user_mem[user],
                    'threads': user_threads[user],
                    'gpu_count': user_gpu[user],
                    'gpu_percent': user_gpu_percent[user],
                    'gpu_mem': user_gpu_mem[user],
                    })

        record = {
            'system': system,
            'users': users,
            }
        
        print(json.dumps(record), file=output_file, flush=True)

        time.sleep(interval)

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
    """
    Returns the username of the process owner given a process ID (pid).
    Reads the /proc/<pid>/status file to extract the UID, then converts it to a username.
    """
    try:
        with open(f'/proc/{pid}/status') as proc_file:
            for line in proc_file:
                if line.startswith('Uid:'):
                    uid = int(line.split()[1])
                    return pwd.getpwuid(uid).pw_name
    except:
        return None


if __name__ == '__main__':
    # Prevent multiple instances of the script by using a Unix domain socket lock.
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        # Bind to a unique, abstract socket name. If already bound, another instance is running.
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

    # Main loop: Collect system metrics and output JSON at regular intervals.
    while True:
        # Prime the CPU usage measurements for all processes.
        for proc in psutil.process_iter(['pid', 'name', 'username']):
            try:
                proc.cpu_percent(interval=0)  # Prime the measurement
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Ignore processes that are inaccessible or have terminated.
                pass

        # Brief pause to allow CPU percentage measurements to accumulate.
        time.sleep(0.1)

        user_threads = defaultdict(int)
        user_mem = defaultdict(int)
        user_cpu_percent = defaultdict(int)
        user_files = defaultdict(int)
        for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_info', 'num_threads', 'open_files']):
            try:
                info = proc.info  # Dictionary with requested process details
                user = info['username']
                user_threads[user] += info['num_threads']
                user_mem[user] += int(info['memory_info'].rss /1024**2)
                user_cpu_percent[user] += int(info['cpu_percent'])
                user_files[user] += len(info['open_files']) if info['open_files'] else 0
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Skip processes that are no longer available or cannot be accessed.
                pass

        # scan of GPU processes
        gpus = list(nvsmi.get_gpus())
        gpus = {gpu.id: gpu for gpu in gpus}

        # Dictionaries to accumulate GPU metrics per user.
        user_gpu = defaultdict(list)  # List of GPU IDs associated with each user
        user_gpu_percent = defaultdict(int)  # Accumulated GPU utilization per user
        user_gpu_mem = defaultdict(int)  # Accumulated GPU memory usage per user

        # Get processes running on GPUs.
        processes = nvsmi.get_gpu_processes()

        # Determine the number of processes per GPU, since the library doesn't attribute GPU load to a specific process.
        processes_per_gpu = defaultdict(int)
        for process in processes:
            processes_per_gpu[process.gpu_id] += 1

        for process in processes:
            user = owner(process.pid)
            if user:
                user_gpu[user].append(process.gpu_id)
                user_gpu_percent[user] += int(gpus[process.gpu_id].gpu_util/processes_per_gpu[process.gpu_id])
                user_gpu_mem[user] += int(process.used_memory)

        # Get overall memory usage.
        vm = psutil.virtual_memory()

        # Construct a dictionary of system-wide metrics.
        system = {
            'time': datetime.now().replace(microsecond=0).isoformat(),  # Current timestamp
            'total_processes': len(psutil.pids()),  # Total number of processes running
            'mem_percent': vm.used * 100 // vm.total,  # Percentage of memory used
            'cpu_percent': int(sum(psutil.cpu_percent(percpu=True))),  # Total CPU usage across all cores
            'gpu_mem_percent': int(
                sum(gpu.mem_used for gpu in gpus.values()) * 100 // sum(gpu.mem_total for gpu in gpus.values())),
            # GPU memory usage percentage
            'gpu_percent': int(sum(gpu.gpu_util for gpu in gpus.values())),  # Total GPU utilization percentage
        }

        # Gather disk usage statistics for relevant partitions.
        disks = list()
        for p in psutil.disk_partitions():
            # Exclude certain filesystems and mount points that are not relevant.
            if p.fstype != 'squashfs' and not p.mountpoint.startswith('/proc') and not p.mountpoint.startswith('/boot'):
                disk_usage = psutil.disk_usage(p.mountpoint)
                disks.append({
                    'mount': p.mountpoint,
                    'use_percent': int(disk_usage.percent)
                })

        system['disks'] = disks

        users = list()
        for user in sorted(user_threads):
            # Include users with notable activity (CPU usage, memory usage, or GPU activity).
            if user_cpu_percent[user] > 0 or user_mem[user] > 100 or len(user_gpu[user]) > 0:
                users.append({
                    'user': user,
                    'cpu_percent': user_cpu_percent[user],
                    'mem': user_mem[user],
                    'threads': user_threads[user],
                    'gpu_count': len(set(user_gpu[user])),
                    'gpu_processes': len(user_gpu[user]),
                    'gpu_percent': user_gpu_percent[user],
                    'gpu_mem': user_gpu_mem[user],
                    'open_files': user_files[user],
                    })

        record = {
            'system': system,
            'users': users,
            }
        
        print(json.dumps(record), file=output_file, flush=True)

        time.sleep(interval)

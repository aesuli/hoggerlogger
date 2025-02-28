# HoggerLogger

HoggerLogger is a lightweight system monitoring tool written in Python that aggregates system, process, and GPU metrics. 
It collects detailed information about CPU, memory, disk, and GPU usage, and aggregates process-level statistics by user. 
The tool outputs a JSON record at regular intervals, making it easy to integrate with other monitoring systems or log analysis tools.

---

## Features

- **System Usage Monitoring:**  
  Captures overall system metrics such as:
  - Total processes running
  - System memory and CPU usage
  - Disk usage for relevant partitions
  - Overall GPU usage

- **GPU Monitoring:**  
  Uses the `nvsmi` module to scan GPU processes and aggregates GPU utilization and memory usage per user.

- **Single Instance Lock:**  
  Uses a Unix socket lock to prevent multiple instances from running simultaneously.

- **Configurable Logging Interval:**  
  Allows customization of the log interval (default is 60 seconds).

- **JSON Output:**  
  Outputs data in JSON format for easy parsing and integration.

---

## Requirements

- **Python 3.x**
- **Dependencies:**
  - [psutil](https://pypi.org/project/psutil/)
  - [nvsmi](https://pypi.org/project/nvsmi/)

---

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/aesuli/hoggerlogger.git
   cd hoggerlogger
   ```

2. **Create and activate a virtual environment (optional but recommended):**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install the required packages:**

   ```bash
   pip install -r requirements.txt
   ```

   *Alternatively, install packages individually:*

   ```bash
   pip install psutil nvsmi
   ```

---

## Usage

Run the script using Python. The script accepts two optional arguments:

- `--interval`: The logging interval in seconds (default is 60 seconds).
- `--output_file`: The file to which output is appended (default is standard output).

### Example

```bash
python hogger_logger.py --interval 60 --output_file hogger_log.json
```

---

## Sample Output

The script constructs a JSON object with two main sections:
   - `system`: Contains overall system metrics.
   - `users`: Contains aggregated metrics for each user with significant resource usage.

The JSON record is printed (or written to the specified output file) and the script waits for the specified interval before repeating the data collection.

Below is an example of the JSON output produced by the script:

```json
{
  "system": {
    "time": "2025-02-28T12:00:00",
    "total_processes": 150,
    "mem_percent": 75,
    "cpu_percent": 240,
    "gpu_mem_percent": 60,
    "gpu_percent": 90,
    "disks": [
      {
        "mount": "/",
        "use_percent": 45
      },
      {
        "mount": "/home",
        "use_percent": 55
      }
    ]
  },
  "users": [
    {
      "user": "alice",
      "cpu_percent": 120,
      "mem": 2048,
      "threads": 150,
      "gpu_count": 1,
      "gpu_processes": 2,
      "gpu_percent": 45,
      "gpu_mem": 500,
      "open_files": 30
    },
    {
      "user": "bob",
      "cpu_percent": 80,
      "mem": 1024,
      "threads": 100,
      "gpu_count": 0,
      "gpu_processes": 0,
      "gpu_percent": 0,
      "gpu_mem": 0,
      "open_files": 10
    }
  ]
}
```
---

## License

This project is licensed under the [BSD 3-Clause License](LICENSE).

---

## Acknowledgements

- Thanks to the developers of [psutil](https://github.com/giampaolo/psutil) and [nvsmi](https://pypi.org/project/nvsmi/) for providing the essential tools used in this project.

---

Happy monitoring!
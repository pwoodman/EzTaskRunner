"""
System Information Module

Contains functions for gathering system metrics and information.
"""

import platform
import os
import psutil
from datetime import datetime

def get_system_info():
    """
    Gather and return system information.
    
    Returns:
        str: Formatted system information
    """
    # Get system information
    system_info = []
    
    # Basic system info
    system_info.append(f"System: {platform.system()} {platform.release()}")
    system_info.append(f"Node Name: {platform.node()}")
    system_info.append(f"Python Version: {platform.python_version()}")
    system_info.append(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # CPU information
    cpu_count = psutil.cpu_count(logical=False)
    logical_cpu_count = psutil.cpu_count(logical=True)
    cpu_usage = psutil.cpu_percent(interval=1)
    system_info.append(f"CPU: {cpu_count} physical cores, {logical_cpu_count} logical cores")
    system_info.append(f"CPU Usage: {cpu_usage}%")
    
    # Memory information
    memory = psutil.virtual_memory()
    memory_total_gb = memory.total / (1024 ** 3)
    memory_available_gb = memory.available / (1024 ** 3)
    memory_used_percent = memory.percent
    system_info.append(f"Memory: {memory_total_gb:.2f} GB total, {memory_available_gb:.2f} GB available ({memory_used_percent}% used)")
    
    # Disk information
    disk = psutil.disk_usage('/')
    disk_total_gb = disk.total / (1024 ** 3)
    disk_free_gb = disk.free / (1024 ** 3)
    disk_used_percent = disk.percent
    system_info.append(f"Disk: {disk_total_gb:.2f} GB total, {disk_free_gb:.2f} GB free ({disk_used_percent}% used)")
    
    # Network information
    try:
        net_io = psutil.net_io_counters()
        bytes_sent_mb = net_io.bytes_sent / (1024 ** 2)
        bytes_recv_mb = net_io.bytes_recv / (1024 ** 2)
        system_info.append(f"Network: {bytes_sent_mb:.2f} MB sent, {bytes_recv_mb:.2f} MB received")
    except:
        system_info.append("Network information unavailable")
    
    # Return formatted information
    return "\n".join(system_info)

def main():
    """Entry point for direct script execution."""
    return get_system_info()

if __name__ == "__main__":
    print(main()) 
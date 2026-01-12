# Linux Administrator Cheat Sheet

Commonly used commands for system maintenance and backup.

## Log Management
```bash
# Clear bash history
cat /dev/null > ~/.bash_history && history -c && exit

# Clear specific log files
truncate -s 0 /var/log/syslog
```

## Backup & Compression
```bash
# Backup a directory with timestamp
tar -zcvf backup_$(date +%Y-%m-%d_%H-%M-%S).tar.gz /path/to/dir

# MySQL/MariaDB backup
mysqldump --user [username] --all-databases > all-databases.sql

# Decompress all .gz files in subdirectories
gzip -d $(find ./ -type f -name '*.gz')
```

## Disk Usage
```bash
# Check size of all files in current directory
ls -lh *

# Check size of specific directory (summary)
du -sh /var/www/
```

## VMware Edge (ESXi Console)
```bash
# List all VM world IDs
vm-support -x

# Force kill a stuck VM
vm-support -X [world-id]

# Rescan storage adapter
esxcfg-rescan [vmhba]
```

# Linux System Investigation & Health Check

## 1. OS & Kernel

### Command

```bash
uname -a
```

### Output

```text
Linux minipay 7.0.0-1006-aws #6-Ubuntu SMP PREEMPT Tue May 26 12:04:34 UTC 2026 x86_64 GNU/Linux
```

**Summary:**

* Hostname: `minipay`
* OS: Ubuntu Linux
* Kernel: `7.0.0-1006-aws`
* Architecture: `x86_64`
* AWS kernel build

---

## 2. CPU, Memory & Disk Utilization

### Command

```bash
lscpu
free -h
df -h
```

### CPU

```text
CPU(s):                 2
On-line CPU(s) list:    0,1
Vendor ID:              GenuineIntel
Model name:             Intel(R) Xeon(R) Platinum 8259CL CPU @ 2.50GHz
Thread(s) per core:     2
Core(s) per socket:     1
Socket(s):              1
```

**CPU Summary:**
The instance has **2 vCPUs** running on an Intel Xeon Platinum processor.

### Memory

```text
               total   used   free   shared   buff/cache   available
Mem:           908Mi   478Mi  100Mi  18Mi     475Mi        430Mi
Swap:             0B     0B    0B   0B          0B          0B
```

**Memory Summary:**

* Total RAM: ~908 MiB
* Used: ~478 MiB
* Available: ~430 MiB
* Swap: 0 B

### Disk

```text
Filesystem       Size  Used  Avail  Use%
/dev/root         30G   4.0G   26G   14%
/dev/nvme0n1p13  989M   163M  759M  18%
/dev/nvme0n1p15  105M   6.3M   99M   7%
```

**Disk Summary:**
The root filesystem has **30 GB total**, with approximately **4 GB used (14%)** and **26 GB available**.

---

## 3. Listening Ports & Relevant Processes

### Command

```bash
ss -tupln
```

### Listening TCP Ports

```text
0.0.0.0:22       SSH
0.0.0.0:8080     Nginx
0.0.0.0:5432     PostgreSQL
0.0.0.0:8000     FastAPI backend

[::]:22          SSH
[::]:8080        Nginx
[::]:5432        PostgreSQL
[::]:8000        FastAPI backend
```

### Summary

| Port | Service         | Purpose                      |
| ---: | --------------- | ---------------------------- |
|   22 | SSH             | Remote server administration |
| 8000 | FastAPI/Uvicorn | Backend API                  |
| 5432 | PostgreSQL      | Database                     |
| 8080 | Nginx           | Reverse proxy/web server     |

---

## 4. Highest Memory-Using Processes

### Command

```bash
ps aux --sort=-%mem | head
```

### Output

```text
USER   PID    %MEM   RSS    COMMAND
root   28559   7.3   68620  /usr/bin/dockerd
root   29607   5.2   48580  /usr/local/bin/python3.12 ... uvicorn main:app
root   28402   3.2   29928  /usr/bin/containerd
70     29505   2.8   26744  postgres
root   17341   2.7   25764  /usr/lib/snapd/snapd
```

**Observation:**
Docker daemon is the largest memory consumer at approximately **7.3%**, followed by the FastAPI/Uvicorn process at approximately **5.2%**.

No single process is consuming an unusually large portion of the available memory.

---

## 5. Disk Usage by Directory

### Command

```bash
du -sh */
```

### Output

```text
12K     database/
12K     starter/
16K     incidents/
28K     requirements/
18M     src/
```

**Observation:**
The `src/` directory is the largest listed application directory at approximately **18 MB**. The remaining directories use minimal disk space.

---

## 6. DNS & Network Connectivity

### Command

```bash
curl -I https://api.github.com
```

### Result

```text
HTTP/2 200
server: github.com
content-type: application/json
```

**Result:**
The server successfully resolved and connected to GitHub over HTTPS. The `HTTP/2 200` response confirms successful external network connectivity.

---

## 7. Application Logs

### Command

```bash
docker logs app-backend-1
```

### Output

```text
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Observation:**
The FastAPI application started successfully and is listening on port `8000`.

---

# 8. Application & Database Health Check

### Health-check Script

```bash
#!/usr/bin/env bash
set -e

echo "== OS =="
uname -a

echo "== Disk =="
df -h /

echo "== Memory =="
free -h

echo "== API =="
curl -sf http://localhost:8000/health || echo "API DOWN"

echo "== DB =="
docker exec app-db-1 pg_isready || echo "DB DOWN"
```

### Execution

```bash
./health-check.sh
```

### Output

```text
== OS ==
Linux minipay 7.0.0-1006-aws #6-Ubuntu SMP PREEMPT Tue May 26 12:04:34 UTC 2026 x86_64 GNU/Linux

== Disk ==
Filesystem      Size  Used  Avail  Use%
/dev/root        30G   4.0G   26G   14%

== Memory ==
               total   used   free   shared   buff/cache   available
Mem:           908Mi   478Mi  100Mi  18Mi     475Mi        430Mi
Swap:             0B     0B     0B    0B          0B          0B

== API ==
{"status":"ok"}

== DB ==
/var/run/postgresql:5432 - accepting connections
```

## Health Check Result

| Component  | Status  | Evidence                                 |
| ---------- | ------- | ---------------------------------------- |
| OS         | Healthy | Kernel information returned successfully |
| Disk       | Healthy | 14% used, 26 GB available                |
| Memory     | Healthy | ~430 MiB available                       |
| API        | Healthy | `{"status":"ok"}`                        |
| PostgreSQL | Healthy | `accepting connections`                  |
| Network    | Healthy | GitHub returned HTTP 200                 |
| Backend    | Healthy | Uvicorn startup completed successfully   |

**Overall:** The MiniPay server, backend API, PostgreSQL database, networking, and available system resources were successfully verified.



### Troubleshooting Approach

* **High CPU:** Use `top`, `htop`, or `ps aux --sort=-%cpu` to identify the process consuming CPU. Check its logs and recent changes, then determine whether the load is expected or caused by a runaway process.

* **Low disk space:** Run `df -h` to identify the full filesystem, then use `du -sh /*` or `du -xhd1 /` to locate large directories. Check logs, Docker images/containers, and temporary files before safely cleaning up.

* **Unreachable API:** Check whether the application/container is running with `docker ps` and inspect logs with `docker logs`. Verify the listening port using `ss -lntp`, test locally with `curl`, and then check Nginx/reverse-proxy configuration, security groups, and network connectivity.

* **Repeatedly terminating process:** Check `docker ps -a`, `docker logs`, and `journalctl` to determine why it exits. Check for application errors, configuration/environment problems, dependency failures, and **OOM (out-of-memory) kills** using `dmesg` or system logs.

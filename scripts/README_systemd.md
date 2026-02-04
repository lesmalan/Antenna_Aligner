Systemd unit for pi_tcp_server

1) Edit the unit file to set the correct paths for your Pi. Replace /home/pi/Antenna_Aligner with the repository path on your Pi if different.

File: [scripts/pi_tcp_server.service](scripts/pi_tcp_server.service)

2) Copy the unit to systemd and enable it:

```bash
sudo cp scripts/pi_tcp_server.service /etc/systemd/system/pi_tcp_server.service
sudo systemctl daemon-reload
sudo systemctl enable --now pi_tcp_server.service
sudo journalctl -u pi_tcp_server.service -f
```

3) Quick manual test (before enabling): run server in foreground

```bash
python3 scripts/pi_tcp_server.py
# then from another machine:
echo "PING" | nc PI_IP 8000
```

4) To stop/disable the service:

```bash
sudo systemctl stop pi_tcp_server.service
sudo systemctl disable pi_tcp_server.service
```

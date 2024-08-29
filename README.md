# bian-monitor

```powershell
pyinstaller .\main.py --onefile --noconsole --name crypto_monitor -i BTC.png --add-data "BTC.png;."
```


```shell
pyinstaller main_linux.py --onefile --noconsole --name crypto_monitor
chmod +x dist/crypto_monitor
mv dist/crypto_monitor /usr/local/bin
```

#!/bin/zsh
for i in 1 2 3 4 5; do
  ./venv/bin/python tts_generate.py 5000 >> logs/tts_generate.log 2>&1
  if grep -q "完成！成功合成" logs/tts_generate.log; then break; fi
  echo "[watchdog] 第${i}次退出，5秒后重启" >> logs/tts_generate.log
  sleep 5
done

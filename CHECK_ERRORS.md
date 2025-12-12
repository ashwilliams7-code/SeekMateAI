# How to Check for Errors

## Quick Error Check

In your SSH session, run:

```bash
# View last 50 lines of logs
sudo journalctl -u seekmateai -n 50

# Or view all errors
sudo journalctl -u seekmateai | grep -i error

# Or view recent logs with errors highlighted
sudo journalctl -u seekmateai --since "5 minutes ago"
```

## Check Service Status

```bash
sudo systemctl status seekmateai
```

Look for:
- Red error messages
- "failed" status
- Any exception/stack traces

## Check Bot Log Files

```bash
cd ~/seekmateai
cat continuous_runner.log
cat log.txt
```

## Common Issues

1. **Chrome not found** - Need to install Chrome
2. **Python dependencies missing** - Need to install requirements
3. **Config file issues** - Check config.json syntax
4. **Permission errors** - Check file permissions
5. **Chrome profile issues** - May need to create profile directory


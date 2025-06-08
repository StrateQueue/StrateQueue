# StrateQueue Quick-Start

Output quick-start.gif

Set FontSize 14
Set Width 1200
Set Height 600
Set Shell "bash"
Set TypingSpeed 50ms
Set PlaybackSpeed 1.0

# Start with a clean terminal
Hide
Type "export PS1=''"
Enter
Type "source ../venvs/zipline311/bin/activate"  # Activate your venv
Enter
Type "clear"  # Clear the screen to remove setup artifacts
Enter
Show

Type "# pip install stratequeue"
Enter
Sleep 1s

# Execute the deployment command
Type "stratequeue deploy \"
Enter
Type "  --strategy ../examples/strategies/backtestingpy/sma.py \"
Enter
Type "  --symbol AAPL \"
Enter
Type "  --timeframe 1m"
Enter

# Let it run for about 10 seconds to show live signals
Sleep 10s

# Stop the process
Ctrl+C
Sleep 5s

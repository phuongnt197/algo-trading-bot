@REM Create 10 window to automatically trade realtime with TWS 10 stocks as list below.
@REM To run it, command ./run_multi.bat in the terminal

setlocal EnableDelayedExpansion

set list=RTX AMD META INTC AAPL MSFT GOOG TSLA AMZN COST
set clientid=0
for %%a in (%list%) do (
    set /A "clientid=!clientid!+1"
    start python main.py --ticker %%a --client-id !clientid! 
)

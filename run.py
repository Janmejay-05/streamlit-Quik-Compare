import sys
import os
import uvicorn
import asyncio

if __name__ == "__main__":
    # Add the current directory to sys.path
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    # Force ProactorEventLoop on Windows for Playwright
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Run the application
    # reload=False because reload spawns a child process that loses the event loop policy
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=False)


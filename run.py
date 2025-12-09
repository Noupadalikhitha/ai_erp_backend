#!/usr/bin/env python
import os
import sys

# Add backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == '__main__':
    import uvicorn
    from app.main import app
    
    uvicorn.run(
        app,
        host='0.0.0.0',
        port=8000,
        reload=False
    )

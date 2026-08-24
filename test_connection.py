import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import text
from app.database.session import engine

async def test_connection():
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            row = result.fetchone()
            if row and row[0] == 1:
                print("POSTGRESQL CONNECTION: SUCCESS")
            else:
                print("POSTGRESQL CONNECTION: FAILED - Unexpected result")
    except Exception as e:
        error_str = str(e)
        if "authentication failed" in error_str.lower():
            database_url = os.getenv("DATABASE_URL", "")
            try:
                from urllib.parse import urlparse
                parsed = urlparse(database_url)
                username = parsed.username
                hostname = parsed.hostname
                print(f"POSTGRESQL CONNECTION: FAILED - Authentication failed for user '{username}' at '{hostname}'")
            except:
                print(f"POSTGRESQL CONNECTION: FAILED - Authentication failed")
        else:
            print(f"POSTGRESQL CONNECTION: FAILED - {error_str}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_connection())

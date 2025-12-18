import asyncio
import asyncpg
import os
from app.config import settings

async def init_db():
    print(f"Connecting to {settings.DATABASE_URL}...")
    try:
        conn = await asyncpg.connect(settings.DATABASE_URL)

        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        with open(schema_path, "r") as f:
            schema_sql = f.read()

        print("Applying schema...")
        await conn.execute(schema_sql)
        print("Schema applied successfully.")

        await conn.close()
    except Exception as e:
        print(f"Error initializing database: {e}")

if __name__ == "__main__":
    asyncio.run(init_db())

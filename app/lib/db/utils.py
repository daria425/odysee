import sqlite3
import sys
from app.lib.db.store import DB_PATH


def delete_trip(trip_id: str):
    with sqlite3.connect(DB_PATH) as conn:
        ml = conn.execute("DELETE FROM memory_log WHERE trip_id = ?", (trip_id,)).rowcount
        t = conn.execute("DELETE FROM trips WHERE trip_id = ?", (trip_id,)).rowcount

        # LangGraph SqliteSaver tables
        cp = conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (trip_id,)).rowcount
        cw = conn.execute("DELETE FROM checkpoint_writes WHERE thread_id = ?", (trip_id,)).rowcount
        cb = conn.execute("DELETE FROM checkpoint_blobs WHERE thread_id = ?", (trip_id,)).rowcount

    print(f"deleted: {t} trip, {ml} memory entries, {cp + cw + cb} checkpoint rows")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m app.lib.db.utils <trip_id>")
        sys.exit(1)
    delete_trip(sys.argv[1])

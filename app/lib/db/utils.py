import sqlite3
import sys
from app.lib.db.store import DB_PATH


def _delete_if_exists(conn, table, column, value):
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if exists:
        return conn.execute(f"DELETE FROM {table} WHERE {column} = ?", (value,)).rowcount
    return 0


def delete_trip(trip_id: str):
    with sqlite3.connect(DB_PATH) as conn:
        ml = conn.execute("DELETE FROM memory_log WHERE trip_id = ?", (trip_id,)).rowcount
        t = conn.execute("DELETE FROM trips WHERE trip_id = ?", (trip_id,)).rowcount

        cp = _delete_if_exists(conn, "checkpoints", "thread_id", trip_id)
        cw = _delete_if_exists(conn, "checkpoint_writes", "thread_id", trip_id)
        cb = _delete_if_exists(conn, "checkpoint_blobs", "thread_id", trip_id)

    print(f"deleted: {t} trip, {ml} memory entries, {cp + cw + cb} checkpoint rows")


def db_schema():
    with sqlite3.connect(DB_PATH) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        for (table,) in tables:
            print(f"\n-- {table} --")
            cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
            for col in cols:
                print(f"  {col[1]} ({col[2]})")
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  [{count} rows]")


def list_threads():
    with sqlite3.connect(DB_PATH) as conn:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='checkpoints'"
        ).fetchone()
        if not exists:
            print("no checkpoints table found — has the API been run yet?")
            return
        rows = conn.execute(
            "SELECT DISTINCT thread_id FROM checkpoints ORDER BY thread_id"
        ).fetchall()
        print(f"threads ({len(rows)}):")
        for (tid,) in rows:
            print(f"  {tid}")


def view_thread(thread_id: str):
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

    with SqliteSaver.from_conn_string(str(DB_PATH)) as saver:
        config = {"configurable": {"thread_id": thread_id}}
        tup = saver.get_tuple(config)

    if tup is None:
        print(f"no checkpoint found for thread '{thread_id}'")
        return

    messages = tup.checkpoint.get("channel_values", {}).get("messages", [])
    print(f"\n=== thread: {thread_id} ({len(messages)} messages) ===\n")

    for msg in messages:
        if isinstance(msg, HumanMessage):
            role = "USER"
        elif isinstance(msg, AIMessage):
            role = "ASSISTANT"
        elif isinstance(msg, SystemMessage):
            role = "SYSTEM"
        elif isinstance(msg, ToolMessage):
            role = "TOOL"
        else:
            role = type(msg).__name__.upper()

        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        snippet = content[:400] + ("..." if len(content) > 400 else "")
        print(f"[{role}]\n{snippet}\n")


USAGE = """usage:
  python -m app.lib.db.utils schema              — show all tables + row counts
  python -m app.lib.db.utils threads             — list all thread IDs
  python -m app.lib.db.utils view <thread_id>    — print messages for a thread
  python -m app.lib.db.utils delete <trip_id>    — delete trip + memory + checkpoints
"""

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "schema":
        db_schema()
    elif cmd == "threads":
        list_threads()
    elif cmd == "view" and len(sys.argv) == 3:
        view_thread(sys.argv[2])
    elif cmd == "delete" and len(sys.argv) == 3:
        delete_trip(sys.argv[2])
    else:
        print(USAGE)
        sys.exit(1)

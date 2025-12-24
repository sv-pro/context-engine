import os
import sys
import argparse
import logging
from db import Database

# Configure minimal logging
logging.basicConfig(level=logging.ERROR)

def get_db():
    # Ensure DATABASE_URL is set (usually passed by docker exec)
    if not os.environ.get("DATABASE_URL"):
        print("Error: DATABASE_URL not set. Run this inside the container.")
        sys.exit(1)
    return Database()

def cmd_search(db, query, limit=5):
    print(f"Searching for nodes matching: '{query}'...")
    # Use keyword search for finding nodes by title/content
    results = db.keyword_search(query, limit=limit)
    if not results:
        print("No results found.")
        return

    print(f"{'ID':<5} | {'Title':<40} | {'Type/Section':<20}")
    print("-" * 70)
    for row in results:
        # row: file_path, title, content, section, similarity
        file_path, title, content, section, _ = row
        # We don't have ID in this return format easily, but title is unique enough for display
        print(f"{'?':<5} | {title[:40]:<40} | {section or 'Doc':<20}")

def cmd_ls(db, title):
    print(f"Edges for node: '{title}'")
    with db.conn.cursor() as cur:
        # Get Node ID
        cur.execute("SELECT id FROM brain.notes WHERE title = %s", (title,))
        res = cur.fetchone()
        if not res:
            print(f"Node '{title}' not found.")
            return
        node_id = res[0]

        # Outgoing
        print("\nOutgoing Edges:")
        cur.execute("SELECT type, target_title FROM brain.edges WHERE source_id = %s", (node_id,))
        rows = cur.fetchall()
        for r in rows:
            print(f"  --[{r[0]}]--> {r[1]}")

        # Incoming (Need to search reverse)
        # Verify schema: target_title is text. To find incoming, we need to find edges where target_title = title.
        print("\nIncoming Edges:")
        cur.execute("""
            SELECT n.title, e.type 
            FROM brain.edges e 
            JOIN brain.notes n ON e.source_id = n.id 
            WHERE e.target_title = %s
        """, (title,))
        rows = cur.fetchall()
        for r in rows:
            print(f"  {r[0]} --[{r[1]}]--> (this)")

def cmd_read(db, title):
    with db.conn.cursor() as cur:
        cur.execute("SELECT content, metadata FROM brain.notes WHERE title = %s", (title,))
        res = cur.fetchone()
        if not res:
            print(f"Node '{title}' not found.")
            return
        
        content, metadata = res
        print(f"=== {title} ===")
        print(f"Metadata: {metadata}")
        print("-" * 40)
        print(content)

def main():
    parser = argparse.ArgumentParser(description="Graph Navigator")
    subparsers = parser.add_subparsers(dest="command")

    p_search = subparsers.add_parser("search", help="Search for nodes")
    p_search.add_argument("query", help="Search query")

    p_ls = subparsers.add_parser("ls", help="List edges for a node")
    p_ls.add_argument("title", help="Note title")

    p_read = subparsers.add_parser("read", help="Read node content")
    p_read.add_argument("title", help="Note title")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    db = get_db()
    
    if args.command == "search":
        cmd_search(db, args.query)
    elif args.command == "ls":
        cmd_ls(db, args.title)
    elif args.command == "read":
        cmd_read(db, args.title)

if __name__ == "__main__":
    main()

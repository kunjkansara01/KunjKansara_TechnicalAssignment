"""Check that the settings in .env can reach MySQL.

Run from the project folder with the venv active:
    python tools/check_db.py

It never prints the password. It only reports which user and database it
tried and whether MySQL accepted the connection.
"""

import sys
import os

# Allow "from app import ..." when running this file directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mysql.connector

from app.config import Config


def main():
    print("Trying to connect to MySQL with these settings from .env:")
    print("  host     :", Config.DB_HOST)
    print("  port     :", Config.DB_PORT)
    print("  user     :", Config.DB_USER)
    print("  database :", Config.DB_NAME)
    print("  password :", "(set, %d characters)" % len(Config.DB_PASSWORD) if Config.DB_PASSWORD else "(empty!)")
    print()

    try:
        connection = mysql.connector.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
        )
    except mysql.connector.Error as error:
        print("FAILED:", error)
        print()
        if error.errno == 1045:
            print("Meaning: MySQL rejected the user/password. The password in .env")
            print("does not match the one stored in MySQL for this user.")
        elif error.errno == 1049:
            print("Meaning: the database does not exist. Run sql/setup_database.sql.")
        elif error.errno == 2003:
            print("Meaning: nothing is listening on that host/port. Start the MySQL")
            print("Windows service (e.g. net start MySQL84 in an admin PowerShell).")
        return 1

    cursor = connection.cursor()
    cursor.execute("SELECT VERSION(), CURRENT_USER(), DATABASE()")
    version, current_user, database = cursor.fetchone()
    cursor.close()
    connection.close()

    print("OK: connected to MySQL", version)
    print("  logged in as :", current_user)
    print("  database     :", database)
    return 0


if __name__ == "__main__":
    sys.exit(main())

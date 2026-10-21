`db-init.bat`- Install for database, file that need to use:
  [PostgreSQL binary](https://sbp.enterprisedb.com/getfile.jsp?fileid=1260609) - PostgreSQL binary (unbox -> pgsql folder to the project main folder)
  .env - contains the configuration of database
  
`db-start.bat` - Start the database on 5432 port

`db-stop.bat` - Stop the database

```
PySide6 client  ──HTTP + JSON──>  FastAPI server  ──SQL──>  PostgreSQL
  (GUI)                            (port 8000)              (port 5432)
```

# First steps (Windows 11)

 ## Create the environment
1. pull `Projekt-labor-2026-27-1`
2. download [PostgreSQL binary](https://sbp.enterprisedb.com/getfile.jsp?fileid=1260609)
3. unbox `postgresql-18.6-4-windows-x64-binaries` into the `Projekt-labor-2026-27-1` main folder
4. run `db-init.bat` (to run u need .\pgsql and .env in the main folder)

 ## Create python virtual environments
1. Install python 3.13.* version
2. open Projekt-labor-2026-27-1 github project folder in cmd (terminal)
3. type `python -m venv .venv`
4. type `.venv\Scripts\activate`
5. type `pip install -r requirements.txt`

  ## Database migration for SQLAlchemy
1. (cmd still open from "Create python virtual environments")
2. run `db-start.bat`
3. type `alembic upgrade head`

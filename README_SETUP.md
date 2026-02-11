# Solar Mini-Grid Monitor - Setup Guide

## 1. Database Setup (MySQL)
Before running the system, you must create the database and tables.

1.  Open your **MySQL Workbench** or Command Line.
2.  Login as `root`.
3.  Open/Run the script located at: `database/schema.sql`.
4.  **Verify**: creating the database `solar_monitoring` and tables `solar_readings` and `system_alerts`.

## 2. Backend Configuration
1.  Open `backend/server.js`.
2.  Find the `db` configuration object (around line 15).
3.  Update the `password` field with your MySQL root password.
    ```javascript
    const db = mysql.createPool({
        host: 'localhost',
        user: 'root',
        password: 'YOUR_PASSWORD_HERE', // <--- Update this
        database: 'solar_monitoring',
        // ...
    });
    ```

## 3. Running the System
You need to run the Backend and Frontend in separate terminals.

### Terminal 1: Backend
```bash
cd backend
node server.js
```
*Expected Output*: `Server running on port 5000`

### Terminal 2: Frontend
```bash
cd frontend
npm run dev
```
*Expected Output*: `Local: http://localhost:5173/`

## 4. Testing with Simulated Data
To simulate the IoT Node sending data:
1.  Open a new terminal.
2.  Run the request simulator (using PowerShell):
    ```powershell
    Invoke-RestMethod -Uri 'http://localhost:5000/api/data' -Method Post -ContentType 'application/json' -Body '{"pv_voltage": 18.5, "pv_current": 4.2, "batt_voltage": 12.8, "load_current": 1.5, "temp": 35.0}'
    ```
3.  Check the **Dashboard** (http://localhost:5173/) to see the data update in real-time.

# Smart Canteen Ordering and Management System

A medium-difficulty Cloud Computing CA3 project built with Flask, MongoDB Atlas and Render.

## Features
- Student registration and login
- Food menu with quantities and order placement
- Student order history and status tracking
- Admin dashboard with order statistics
- Admin can add menu items, change availability and update order status
- Password hashing, CSRF protection, role-based authorization and secure session-cookie settings

## Architecture and cloud models
- **PaaS:** Flask web application deployed on Render
- **DBaaS:** MongoDB Atlas cloud database
- **Deployment model:** Public cloud
- **Data collections:** `users`, `menu`, `orders`

## Requirements
- Python 3.10 or later
- MongoDB Atlas account
- GitHub account
- Render account

## Run locally
1. Extract the project folder.
2. Create and activate a virtual environment:
   - Windows: `py -m venv .venv` then `.venv\Scripts\activate`
   - macOS/Linux: `python3 -m venv .venv` then `source .venv/bin/activate`
3. Install packages: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env`.
5. In MongoDB Atlas, create a cluster and database user. Copy the connection string into `MONGO_URI` in `.env`. Replace the username and password placeholders and URL-encode special characters in the password.
6. Set a long random `SECRET_KEY`, `ADMIN_EMAIL` and `ADMIN_PASSWORD` in `.env`.
7. In `app.py`, the initial admin is created when the app runs locally. For deployment, use the one-time bootstrap procedure below.
8. Start the app: `python app.py`
9. Open `http://127.0.0.1:5000`.

## Create the first admin
For a first local run, the app's `__main__` block calls `bootstrap_admin()` and creates the administrator from `ADMIN_EMAIL` and `ADMIN_PASSWORD`, if that email does not already exist.

For Render, run the one-time command from the project shell after setting `MONGO_URI`, `ADMIN_EMAIL` and `ADMIN_PASSWORD`:
`python -c "from app import bootstrap_admin; bootstrap_admin()"`

Do not share the admin password or commit `.env` to GitHub. After the first admin is created, the environment password is not used for login verification; the hashed password is stored in MongoDB.

## Deploy to Render
1. Push the project folder to a private or public GitHub repository. Do not commit `.env`.
2. In Render, choose **New + → Web Service** and connect the repository.
3. Runtime: Python.
4. Build command: `pip install -r requirements.txt`
5. Start command: `gunicorn app:app`
6. Add environment variables in Render:
   - `MONGO_URI` = Atlas connection string
   - `DB_NAME` = `smart_canteen`
   - `SECRET_KEY` = long random secret
   - `ADMIN_EMAIL` = your chosen admin email
   - `ADMIN_PASSWORD` = a strong temporary bootstrap password
   - `COOKIE_SECURE` = `true`
7. Deploy the service and wait for the public `onrender.com` URL.
8. Run the one-time admin bootstrap command using Render Shell if available. If your plan does not provide Shell, temporarily run the command using a trusted local terminal configured with the same Atlas URI and environment values.
9. Test student registration, login, placing an order and admin status updates.

## MongoDB Atlas network access
For a classroom demo, configure Atlas Network Access so the deployed Render service can reach the cluster. For a production system, use a restricted network configuration appropriate to the hosting setup rather than leaving broad access enabled. Use a database user with only the permissions the app needs.

## Demo sequence
1. Open the deployed URL.
2. Register a student account and log in.
3. Select food quantities and place an order.
4. Open My Orders and show the new order with `Received` status.
5. Log out and log in as the administrator.
6. Open Admin Dashboard and show the order.
7. Change status to `Preparing`, then `Ready`.
8. Add a new menu item or mark an item unavailable.
9. Return to the student menu and show the updated availability.

## CA3 presentation mapping
1. Title
2. Problem statement
3. Objectives
4. Cloud architecture (browser → Render Flask app → MongoDB Atlas)
5. Cloud services and tools
6. Workflow (register → browse → order → admin update → student tracking)
7. Security (password hashing, CSRF, role checks, HTTPS on Render, secrets in environment variables)
8. Results and live demo (screenshots and deployed URL)
9. Challenges and future scope
10. Conclusion and references

## Security notes
- Passwords are stored as Werkzeug password hashes, not plaintext.
- CSRF protection is enabled on forms.
- Admin-only routes check the user's role on the server.
- Session cookies are HttpOnly and SameSite=Lax; set `COOKIE_SECURE=true` when deployed over HTTPS.
- Keep `SECRET_KEY`, `MONGO_URI` and admin credentials out of source control.
- This is an academic demonstration project, not a production payment system. It does not collect card details or process real payments.

## Limitations and possible future improvements
- Add payment gateway sandbox integration.
- Add order pickup time slots and notifications.
- Add menu image uploads using cloud object storage.
- Add pagination, audit logs and automated tests.
- Add a dedicated admin creation/management workflow.

## Academic integrity
Understand and customize the code before submission. Acknowledge AI assistance and any external tutorials or documentation in your README and PPT references, as required by your course brief.

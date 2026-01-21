# NGO Registration and Donation Management System  
(NSS IIT Roorkee – Open Project 2026)

This project is a backend-driven web application built for the 
NSS IIT Roorkee Open Project 2026.

It allows users to register, donate to campaigns, and track donation status,
while providing administrators with complete monitoring and reporting tools.

#  User Features
- User registration and login
- View personal details
- Donate to active campaigns
- OTP-based sandbox payment verification
- View successful donation history
- Download donation receipt
- Retry Failed Donations & Cancel Ongoing Attempts::
The system displays only the most recent donation attempt.
If a donation fails or is cancelled, its status is shown to the user.
When the user starts a new donation, any previous failed or cancelled attempt is automatically reset.
If the new attempt also fails or is cancelled, it replaces the previous one on the screen.
At no time will more than one failed or cancelled attempt be visible.

#  Admin Features
- Admin login with role-based access
- View total registered users and total donations received
- Manage donation campaigns
    - Add new campaigns
    - View existing campaigns
    - View total money collected for each campaign
- View all registered users
    - Filter users by:
        - Top donors
        - Most active donors (max no. of donations)
        - Recent donors
        - Newest registered users
    - View and export user details and individual donation receipts
- Monitor all donation attempts (success / failed / pending)
- View  and export all successful donations sorted by most recent first


# Tech Stack
Backend: Python (Flask)  
Frontend: HTML with Jinja2 templates  
Database: SQLite  
Authentication: Session-based authentication  
Payment Simulation: OTP-based sandbox payment flow  
Version Control: Git and GitHub


# How to Run the Project

1️⃣ Clone the repository
git clone https://github.com/sanjanakp123/nss-donation-system.git
cd nss-donation-system

2️⃣ Install dependencies
pip install flask

3️⃣ Run the application
python app.py

4️⃣ Open in browser
http://127.0.0.1:5000/

The SQLite database is created automatically on first run.

#Admin Setup:
Admin accounts are created manually during deployment and are not exposed through the application interface for security reasons.

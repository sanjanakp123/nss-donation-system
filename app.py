from flask import Flask, render_template, request, redirect, session
import sqlite3
import csv
from flask import Response
from collections import defaultdict

from datetime import datetime
import os


app = Flask(__name__)
app.secret_key = "nss-secret-key"


def get_db():
    return sqlite3.connect("donations.db")

def init_db():
    db = get_db()

    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS user_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            phone TEXT
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)

    db.execute("""
       CREATE TABLE IF NOT EXISTS donations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    campaign_id INTEGER,
    amount INTEGER NOT NULL,
    status TEXT,
    attempt_no INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1,
    payment_method TEXT,
    payment_ref TEXT,
    otp TEXT,
    otp_verified INTEGER DEFAULT 0,
    created_at TEXT
)

    """)

    db.commit()
    db.close()
def migrate_donations_table():
    db = get_db()
    cols = [c[1] for c in db.execute("PRAGMA table_info(donations)")]

    def add(col, sql):
        if col not in cols:
            db.execute(sql)

    add("user_id", "ALTER TABLE donations ADD COLUMN user_id INTEGER")
    add("campaign_id", "ALTER TABLE donations ADD COLUMN campaign_id INTEGER")
    add("status", "ALTER TABLE donations ADD COLUMN status TEXT")
    add("attempt_no", "ALTER TABLE donations ADD COLUMN attempt_no INTEGER DEFAULT 1")
    add("is_active", "ALTER TABLE donations ADD COLUMN is_active INTEGER DEFAULT 1")
    add("payment_method", "ALTER TABLE donations ADD COLUMN payment_method TEXT")
    add("payment_ref", "ALTER TABLE donations ADD COLUMN payment_ref TEXT")

    db.commit()
    db.close()




@app.route("/")
def home():
    return render_template("home.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (email, password, role) VALUES (?, ?, ?)",
                (request.form["email"], request.form["password"], "user")
            )
            db.commit()
        except sqlite3.IntegrityError:
            return render_template("register.html", error="Email already registered")
        finally:
            db.close()
        return redirect("/details")
    return render_template("register.html")

@app.route("/details", methods=["GET", "POST"])
def details():
    if request.method == "POST":
        db = get_db()
        user_id = db.execute(
            "SELECT id FROM users ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]

        db.execute(
            "INSERT INTO user_details (user_id, name, phone) VALUES (?, ?, ?)",
            (user_id, request.form["name"], request.form["phone"])
        )
        db.commit()
        db.close()
        return redirect("/login")
    return render_template("details.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        db = get_db()
        user = db.execute(
            "SELECT id, role FROM users WHERE email=? AND password=?",
            (email, password)
        ).fetchone()
        db.close()

        if not user:
            return "Invalid credentials"

        session.clear()
        session["user_id"] = user[0]
        session["role"] = user[1]

        
        if user[1] == "admin":
            return redirect("/admin/dashboard")
        else:
            return redirect("/dashboard")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")
    if session.get("role") != "user":
        return redirect("/admin/dashboard")
    

    user_id = session["user_id"]
    db = get_db()

    user = db.execute(
        "SELECT email FROM users WHERE id=?",
        (user_id,)
    ).fetchone()

    details = db.execute(
        "SELECT name, phone FROM user_details WHERE user_id=?",
        (user_id,)
    ).fetchone()

    donations = db.execute("""
    SELECT c.name, d.amount, d.created_at, d.id
    FROM donations d
    JOIN campaigns c ON d.campaign_id = c.id
    WHERE d.user_id=? AND d.status='success'
    ORDER BY d.created_at DESC
""", (user_id,)).fetchall()


    retry = db.execute("""
    SELECT d.id, c.name, d.attempt_no
    FROM donations d
    JOIN campaigns c ON d.campaign_id=c.id
    WHERE d.user_id=? AND d.status='failed' AND d.is_active=1
""", (user_id,)).fetchone()


    db.close()

    return render_template(
    "dashboard.html",
    email=user[0],
    details=details,
    donations=donations,
    retry=retry
)
@app.route("/receipt/<int:donation_id>")
def user_receipt(donation_id):
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    db = get_db()

    receipt = db.execute("""
        SELECT 
            u.email,
            ud.name,
            c.name,
            d.amount,
            d.payment_method,
            d.payment_ref,
            d.created_at
        FROM donations d
        JOIN users u ON d.user_id = u.id
        LEFT JOIN user_details ud ON u.id = ud.user_id
        JOIN campaigns c ON d.campaign_id = c.id
        WHERE d.id=? AND d.user_id=? AND d.status='success'
    """, (donation_id, user_id)).fetchone()

    db.close()

    if not receipt:
        return "Invalid receipt request", 403

    return render_template("receipt.html", receipt=receipt)
@app.route("/admin/receipt/<int:donation_id>")
def admin_receipt(donation_id):
    if session.get("role") != "admin":
        return redirect("/login")

    db = get_db()
    data = db.execute("""
        SELECT 
            ud.name,
            u.email,
            c.name,
            d.amount,
            d.payment_method,
            d.payment_ref,
            d.created_at
        FROM donations d
        JOIN users u ON d.user_id = u.id
        JOIN user_details ud ON u.id = ud.user_id
        JOIN campaigns c ON d.campaign_id = c.id
        WHERE d.id=? AND d.status='success'
    """, (donation_id,)).fetchone()
    db.close()

    if not data:
        return "Receipt not found", 404

    receipt_text = f"""
NSS IIT ROORKEE
-------------------------
DONATION RECEIPT

Donor Name : {data[0]}
Email      : {data[1]}
Campaign   : {data[2]}
Amount     : ₹{data[3]}
Method     : {data[4]}
Reference  : {data[5]}
Date       : {data[6]}

(This is a sandbox receipt)
"""

    return Response(
        receipt_text,
        mimetype="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename=receipt_{donation_id}.txt"
        }
    )
@app.route("/dismiss/<int:donation_id>")
def dismiss(donation_id):
    if "user_id" not in session:
        return redirect("/login")

    db = get_db()
    db.execute("""
        UPDATE donations
        SET is_active=0
        WHERE id=?
    """, (donation_id,))
    db.commit()
    db.close()

    return redirect("/dashboard")

@app.route("/admin/campaigns", methods=["GET", "POST"])
def admin_campaigns():
    if session.get("role") != "admin":
        return redirect("/login")

    db = get_db()

    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description")

        db.execute(
            "INSERT INTO campaigns (name, description) VALUES (?, ?)",
            (name, description)
        )
        db.commit()

    campaigns = db.execute("""
    SELECT 
        c.id,
        c.name,
        c.description,
        c.is_active,
        COALESCE(SUM(d.amount), 0) AS total_collected
    FROM campaigns c
    LEFT JOIN donations d
        ON c.id = d.campaign_id
        AND d.status = 'success'
    GROUP BY c.id
    ORDER BY c.id ASC
""").fetchall()


    db.close()

    return render_template("admin_campaigns.html", campaigns=campaigns)


@app.route("/admin/users")
def admin_users():
    if session.get("role") != "admin":
        return redirect("/login")

    db = get_db()

    sort = request.args.get("sort", "")
    q = request.args.get("q", "")

    base_query = """
        SELECT 
            u.id,
            u.email,
            ud.name,
            ud.phone,
            COUNT(d.id) AS donations_count,
            COALESCE(SUM(d.amount), 0) AS total_amount,
            MAX(d.created_at) AS last_donation
        FROM users u
        LEFT JOIN user_details ud ON u.id = ud.user_id
        LEFT JOIN donations d
            ON u.id = d.user_id
            AND d.status = 'success'
        WHERE u.role = 'user'
          AND (u.email LIKE ? OR ud.name LIKE ?)
        GROUP BY u.id
    """

    
    if sort == "top_donors":
        order_by = " ORDER BY COALESCE(SUM(d.amount),0) DESC"

    elif sort == "most_active":
        order_by = " ORDER BY COUNT(d.id) DESC"

    elif sort == "recently_donated":
        order_by = """
            HAVING COUNT(d.id) > 0
            ORDER BY MAX(d.created_at) DESC
        """

    elif sort == "newest_accounts":
        order_by = " ORDER BY u.id DESC"

    else:
        order_by = " ORDER BY u.email ASC"

    users = db.execute(
        base_query + order_by,
        (f"%{q}%", f"%{q}%")
    ).fetchall()


    all_donations = db.execute("""
        SELECT 
            d.user_id,
            c.name,
            d.amount,
            d.status,
            d.created_at
        FROM donations d
        JOIN campaigns c ON d.campaign_id = c.id
        ORDER BY d.created_at DESC
    """).fetchall()

    db.close()

    donation_map = defaultdict(list)
    for d in all_donations:
        donation_map[d[0]].append(d)

    return render_template(
        "admin_users.html",
        users=users,
        donation_map=donation_map
    )


@app.route("/admin/dashboard")
def admin_dashboard():
    if session.get("role") != "admin":
        return redirect("/login")

    db = get_db()

    total_users = db.execute(
        "SELECT COUNT(*) FROM users WHERE role='user'"
    ).fetchone()[0]

    total_amount = db.execute(
        "SELECT SUM(amount) FROM donations WHERE status='success'"
    ).fetchone()[0] or 0

    db.close()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_amount=total_amount
    )

@app.route("/admin/user/<int:user_id>/donations")
def admin_user_donations(user_id):
    if session.get("role") != "admin":
        return redirect("/login")

    db = get_db()

    donations = db.execute("""
        SELECT 
            ud.name,
            c.name,
            d.amount,
            d.created_at,
            d.id
        FROM donations d
        JOIN campaigns c ON d.campaign_id = c.id
        JOIN user_details ud ON d.user_id = ud.user_id
        WHERE d.user_id = ? AND d.status = 'success'
        ORDER BY d.created_at DESC
    """, (user_id,)).fetchall()

    db.close()

    return render_template(
        "admin_donations.html",
        donations=donations
    )





@app.route("/admin/donations")
def admin_donations_view():
    if session.get("role") != "admin":
        return redirect("/login")

    period = request.args.get("period", "all")

    time_filter = ""
    if period == "today":
        time_filter = "AND DATE(d.created_at) = DATE('now')"
    elif period == "week":
        time_filter = "AND d.created_at >= DATE('now', '-7 days')"

    db = get_db()

    donations = db.execute("""
    SELECT 
        u.email,
        c.name,
        d.amount,
        d.created_at,
        d.id
    FROM donations d
    JOIN users u ON d.user_id = u.id
    JOIN campaigns c ON d.campaign_id = c.id
    WHERE d.status = 'success'
    ORDER BY datetime(d.created_at) DESC
""").fetchall()





    db.close()

    return render_template("admin_donations.html", donations=donations)
@app.route("/admin/donation-attempts")
def admin_donation_attempts():
    if session.get("role") != "admin":
        return redirect("/login")

    db = get_db()

    attempts = db.execute("""
        SELECT u.email,
               c.name,
               d.amount,
               d.status,
               d.attempt_no,
               d.created_at
        FROM donations d
        JOIN users u ON d.user_id = u.id
        JOIN campaigns c ON d.campaign_id = c.id
        ORDER BY d.created_at DESC
    """).fetchall()

    db.close()

    return render_template(
        "admin_donation_attempts.html",
        attempts=attempts
    )

@app.route("/user/export/details")
def export_user_details():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    db = get_db()

    data = db.execute("""
        SELECT 
            u.email,
            ud.name,
            ud.phone,
            COUNT(d.id),
            COALESCE(SUM(d.amount), 0)
        FROM users u
        JOIN user_details ud ON u.id = ud.user_id
        LEFT JOIN donations d 
            ON u.id = d.user_id AND d.status='success'
        WHERE u.id=?
        GROUP BY u.id
    """, (user_id,)).fetchone()

    db.close()

    if not data:
        return "No user data found", 404

    text = f"""
NSS IIT ROORKEE
-------------------------
USER DETAILS REPORT

Name   : {data[1]}
Email  : {data[0]}
Phone  : {data[2]}

Total Successful Donations : {data[3]}
Total Amount Donated       : ₹{data[4]}

(This is a sandbox export)
"""

    return Response(
        text,
        mimetype="text/plain",
        headers={
            "Content-Disposition": "attachment; filename=user_details.txt"
        }
    )

@app.route("/admin/export/user/text/<int:user_id>")
def admin_export_user_text(user_id):
    if session.get("role") != "admin":
        return redirect("/login")

    db = get_db()

    data = db.execute("""
        SELECT 
            u.email,
            ud.name,
            ud.phone,
            COUNT(d.id),
            COALESCE(SUM(d.amount), 0)
        FROM users u
        LEFT JOIN user_details ud ON u.id = ud.user_id
        LEFT JOIN donations d 
            ON u.id = d.user_id AND d.status='success'
        WHERE u.id = ?
        GROUP BY u.id
    """, (user_id,)).fetchone()

    db.close()

    if not data:
        return "User not found", 404

    text = f"""
NSS IIT ROORKEE
----------------------------
USER DONATION REPORT (ADMIN)

Email        : {data[0]}
Name         : {data[1]}
Phone        : {data[2]}

No. of Donations : {data[3]}
Total Donated    : ₹{data[4]}

(Generated from Admin Panel)
"""

    return Response(
        text,
        mimetype="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename=user_{user_id}_details.txt"
        }
    )






@app.route("/donate", methods=["GET", "POST"])
def donate():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    db = get_db()

    if request.method == "GET":
        campaigns = db.execute(
            "SELECT id, name FROM campaigns WHERE is_active=1"
        ).fetchall()
        db.close()
        return render_template("donate.html", campaigns=campaigns)

    campaign_id = request.form["campaign_id"]
    amount = request.form["amount"]

    db.execute("""
    UPDATE donations
    SET is_active=0,
        attempt_no=0
    WHERE user_id=? AND status='failed'
""", (user_id,))


    db.execute("""
        INSERT INTO donations
        (user_id, campaign_id, amount, status, attempt_no, is_active, created_at)
        VALUES (?, ?, ?, 'pending', 1, 1, ?)
    """, (
        user_id,
        campaign_id,
        amount,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    donation_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.commit()
    db.close()

    return redirect(f"/payment/{donation_id}")


@app.route("/payment/<int:donation_id>")
def payment_page(donation_id):
    if "user_id" not in session:
        return redirect("/login")

    db = get_db()
    donation = db.execute("""
        SELECT c.name,
               d.amount,
               d.attempt_no,
               d.otp,
               d.payment_method
        FROM donations d
        JOIN campaigns c ON d.campaign_id = c.id
        WHERE d.id=?
    """, (donation_id,)).fetchone()

    if not donation:
        db.close()
        return "Invalid payment request"

    campaign, amount, attempt, otp, method = donation

    
    if method is not None and otp is None:
        import random
        otp = str(random.randint(100000, 999999))
        db.execute("""
            UPDATE donations
            SET otp=?, otp_verified=0
            WHERE id=?
        """, (otp, donation_id))
        db.commit()
        print("OTP GENERATED:", otp)

    db.close()

    return render_template(
        "payment.html",
        donation_id=donation_id,
        campaign=campaign,
        amount=amount,
        attempt=attempt,
        otp=otp,
        method=method
    )



@app.route("/payment/process", methods=["POST"])
def payment_process():
    donation_id = request.form["donation_id"]
    method = request.form["method"]

    db = get_db()
    db.execute("""
        UPDATE donations
        SET payment_method=?
        WHERE id=?
    """, (method, donation_id))
    db.commit()
    db.close()

    return redirect(f"/payment/{donation_id}")



@app.route("/payment/otp/<int:donation_id>")
def payment_otp(donation_id):
    db = get_db()

    row = db.execute(
        "SELECT otp FROM donations WHERE id=?",
        (donation_id,)
    ).fetchone()

    
    if not row or not row[0]:
        import random
        otp = str(random.randint(100000, 999999))

        db.execute("""
            UPDATE donations
            SET otp=?, otp_verified=0
            WHERE id=?
        """, (otp, donation_id))
        db.commit()
    else:
        otp = row[0]

    db.close()

    print("SANDBOX OTP:", otp)

    return render_template(
        "otp.html",
        donation_id=donation_id,
        otp=otp
    )

@app.route("/payment/otp/verify", methods=["POST"])
def verify_otp():
    donation_id = request.form["donation_id"]
    user_otp = request.form["otp"]

    db = get_db()
    row = db.execute(
        "SELECT otp FROM donations WHERE id=?",
        (donation_id,)
    ).fetchone()

    # wrong otp
    if not row or user_otp != row[0]:
        db.execute("""
            UPDATE donations
            SET attempt_no = attempt_no + 1,
                status='failed'
            WHERE id=?
        """, (donation_id,))
        db.commit()
        db.close()

        from urllib.parse import urlencode
        return redirect("/dashboard?" + urlencode({"error": "wrong_otp"}))

   #correct otp
    db.execute("""
        UPDATE donations
        SET otp_verified=1
        WHERE id=?
    """, (donation_id,))
    db.commit()
    db.close()

    return redirect(f"/payment/processing/{donation_id}")
@app.route("/receipt/download/<int:donation_id>")
def download_receipt(donation_id):
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    db = get_db()

    data = db.execute("""
        SELECT 
            ud.name,
            u.email,
            c.name,
            d.amount,
            d.created_at
        FROM donations d
        JOIN users u ON d.user_id = u.id
        JOIN user_details ud ON u.id = ud.user_id
        JOIN campaigns c ON d.campaign_id = c.id
        WHERE d.id=? AND d.user_id=? AND d.status='success'
    """, (donation_id, user_id)).fetchone()

    db.close()

    if not data:
        return "Invalid receipt request", 403

    text = f"""
NSS IIT ROORKEE
----------------------------
DONATION RECEIPT (Sandbox)

Donor Name : {data[0]}
Email      : {data[1]}
Campaign   : {data[2]}
Amount     : ₹{data[3]}
Date       : {data[4]}
"""

    return Response(
        text,
        mimetype="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename=receipt_{donation_id}.txt"
        }
    )



@app.route("/payment/processing/<int:donation_id>")
def payment_processing(donation_id):
    db = get_db()
    ok = db.execute("""
        SELECT otp_verified FROM donations WHERE id=?
    """, (donation_id,)).fetchone()
    db.close()

    if not ok or ok[0] != 1:
        return "OTP verification required", 403

    return render_template("processing.html", donation_id=donation_id)


@app.route("/payment/result", methods=["POST"])
def payment_result():
    donation_id = request.form["donation_id"]

    db = get_db()
    ok = db.execute("""
        SELECT otp_verified FROM donations WHERE id=?
    """, (donation_id,)).fetchone()

    if not ok or ok[0] != 1:
        db.close()
        return "OTP verification required", 403

    db.execute("""
        UPDATE donations
        SET status='success',
            is_active=0,
            attempt_no=0,
            otp_verified=0,
            payment_ref=?
        WHERE id=?
    """, (f"SBX{donation_id}", donation_id))

    db.commit()
    db.close()

    return redirect(f"/payment/success/{donation_id}")


@app.route("/payment/success/<int:donation_id>")
def payment_success(donation_id):
    return render_template("payment_success.html", donation_id=donation_id)

@app.route("/payment/fail", methods=["POST"])
def payment_fail():
    donation_id = request.form["donation_id"]

    db = get_db()
    db.execute("""
        UPDATE donations
        SET status='failed',
            attempt_no = attempt_no + 1,
            is_active = 1
        WHERE id=?
    """, (donation_id,))
    db.commit()
    db.close()

    return redirect("/dashboard?error=payment_failed")


@app.route("/payment/cancel", methods=["POST"])
def payment_cancel():
    donation_id = request.form["donation_id"]

    db = get_db()
    db.execute("""
        UPDATE donations
        SET status='failed',
            attempt_no = attempt_no + 1,
            is_active = 1
        WHERE id=?
    """, (donation_id,))
    db.commit()
    db.close()

    return redirect("/dashboard")




if __name__ == "__main__":
    init_db()
    app.run(debug=True)

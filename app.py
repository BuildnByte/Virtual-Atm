import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def init_db():
    conn = sqlite3.connect('atm.db')
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        password TEXT NOT NULL,
        gov_id TEXT NOT NULL UNIQUE,
        balance REAL DEFAULT 0,
        dob TEXT NOT NULL,
        age INTEGER NOT NULL,
        gender TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT NOT NULL,
        address TEXT NOT NULL,
        state TEXT NOT NULL,
        security_question TEXT NOT NULL,
        secanswer TEXT NOT NULL
    );''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        type TEXT,
        date TEXT,
        FOREIGN KEY(user_id) REFERENCES accounts(id)
    );''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        dob = request.form['dob']
        age = request.form['age']
        gender = request.form['gender']
        email = request.form['email']
        phone = request.form['phone']
        address = request.form['address']
        state = request.form['state']
        security = request.form['security_question_1']
        secanswer = request.form['answer_1']
        gov_id = request.form['gov_id']  
        initial_deposit = float(request.form['balance'])

        if not username or not password or not gov_id:
            flash('All fields are required.', 'danger')
            return redirect(url_for('register'))

        conn = sqlite3.connect('atm.db')
        c = conn.cursor()
        c.execute('SELECT id FROM accounts WHERE gov_id = ?', (gov_id,))
        if c.fetchone():
            flash("Government ID Already Registered. Please use a different Government ID", 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)

        try:
            c.execute('INSERT INTO accounts (username, password, gov_id, balance, dob, age, gender, email, phone, address, state, security_question, secanswer) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                      (username, hashed_password, gov_id, initial_deposit, dob, age, gender, email, phone, address, state, security, secanswer))
            conn.commit()
            flash('Account created successfully! You can now log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            conn.rollback()
            flash(f'Error occurred during registration: {str(e)}', 'danger')
        finally:
            conn.close()

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('atm.db')
        c = conn.cursor()
        c.execute('SELECT id, password FROM accounts WHERE username = ?', (username,))
        user = c.fetchone()

        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            flash("Login Successful!", "success")
            return redirect(url_for('atm'))
        else:
            flash("Invalid credentials, please try again.", "danger")
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/atm', methods=['GET', 'POST'])
def atm():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('atm.db')
    c = conn.cursor()
    c.execute('SELECT balance FROM accounts WHERE id = ?', (session['user_id'],))
    balance = c.fetchone()[0]

    c.execute('SELECT date, amount FROM transactions WHERE user_id = ? AND type = "Deposit" ORDER BY date DESC LIMIT 5', (session['user_id'],))
    deposit_transactions = c.fetchall()

    c.execute('SELECT date, amount FROM transactions WHERE user_id = ? AND type = "Withdraw" ORDER BY date DESC LIMIT 5', (session['user_id'],))
    withdrawal_transactions = c.fetchall()

    conn.close()

    if request.method == 'POST':
        action = request.form['action']
        amount = float(request.form['amount'])

        conn = sqlite3.connect('atm.db')
        c = conn.cursor()

        if action == 'Deposit':
            new_balance = balance + amount
            c.execute('UPDATE accounts SET balance = ? WHERE id = ?', (new_balance, session['user_id']))
            c.execute('INSERT INTO transactions (user_id, amount, type, date) VALUES (?, ?, "Deposit", datetime("now"))', (session['user_id'], amount))
            flash(f'Successfully deposited {amount}!', 'success')

        elif action == 'Withdraw':
            if amount > balance:
                flash(f'Error: Insufficient funds! You tried to withdraw {amount}, but your balance is only {balance}.', 'danger')
            else:
                new_balance = balance - amount
                c.execute('UPDATE accounts SET balance = ? WHERE id = ?', (new_balance, session['user_id']))
                c.execute('INSERT INTO transactions (user_id, amount, type, date) VALUES (?, ?, "Withdraw", datetime("now"))', (session['user_id'], amount))
                flash(f'Successfully withdrew {amount}!', 'success')

        conn.commit()
        conn.close()

        return redirect(url_for('atm'))

    return render_template('atm.html', balance=balance, deposit_transactions=deposit_transactions, withdrawal_transactions=withdrawal_transactions)

@app.route('/remove_account', methods=['GET', 'POST'])
def remove_account():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = sqlite3.connect('atm.db')
    c = conn.cursor()
    c.execute('SELECT balance FROM accounts WHERE id = ?', (user_id,))
    balance_row = c.fetchone()
    balance = balance_row[0] if balance_row else 0

    if request.method == 'POST':
        target_username = request.form['transfer_account_username']
        target_password = request.form['transfer_account_password']
        target_gov_id = request.form['transfer_account_gov_id']

        c.execute('SELECT id, balance FROM accounts WHERE username = ? AND password = ? AND gov_id = ?', (target_username, target_password, target_gov_id))
        target_account = c.fetchone()

        if not target_account:
            flash('Target account information is incorrect. Please try again.', 'danger')
            conn.close()
            return redirect(url_for('remove_account'))

        target_account_id, target_balance = target_account
        new_target_balance = target_balance + balance
        c.execute('UPDATE accounts SET balance = ? WHERE id = ?', (new_target_balance, target_account_id))
        c.execute('DELETE FROM transactions WHERE user_id = ?', (user_id,))
        c.execute('DELETE FROM accounts WHERE id = ?', (user_id,))

        conn.commit()
        conn.close()

        session.pop('user_id', None)
        flash('Your account has been removed and balance transferred successfully.', 'success')
        return redirect(url_for('index'))

    conn.close()
    return render_template('remove_account.html', balance=balance)

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form['username']
        conn = sqlite3.connect('atm.db')
        c = conn.cursor()
        c.execute('SELECT security_question FROM accounts WHERE username = ?', (username,))
        question = c.fetchone()
        conn.close()

        if question:
            return render_template('security_question.html', question=question[0], username=username)
        else:
            flash("Username not found.", 'danger')
            return redirect(url_for('forgot_password'))

    return render_template('forgot_password.html')

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        username = request.form['username']
        answer = request.form['answer']
        new_password = request.form['new_password']

        conn = sqlite3.connect('atm.db')
        c = conn.cursor()
        c.execute('SELECT secanswer FROM accounts WHERE username = ?', (username,))
        stored_answer = c.fetchone()

        if stored_answer and stored_answer[0] == answer:
            hashed_password = generate_password_hash(new_password)
            c.execute('UPDATE accounts SET password = ? WHERE username = ?', (hashed_password, username))
            conn.commit()
            flash('Password reset successfully! You can now log in.', 'success')
        else:
            flash('Incorrect answer to the security question.', 'danger')

        conn.close()
        return redirect(url_for('login'))

    return render_template('reset_password.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out', 'success')
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
